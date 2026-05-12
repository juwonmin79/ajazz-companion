"""
ajazz/battery.py
──────────────────────────────────────────────
HID로 배터리 잔량 읽기 (검증된 프로토콜).

프로토콜 (Jake AJAZZ 2.4G 8K — VID 0x3151 / PID 0x5007 검증):
  OUT: send_feature_report([0x00, 0xf7] + [0x00]*63)
        Report ID 0 (implicit, vendor iface 미선언) + marker 0xf7 + zero pad
  IN:  get_feature_report(0, 65)
        hidapi가 RID byte prepend → resp[3] = 배터리 %
        (wire-level data[2] 와 동일)

인터페이스: usage_page == 0xFFFF (vendor-specific) 의 iface#2
"""

import hid
import threading
import logging

from .protocol import find_devices

logger = logging.getLogger(__name__)

POLL_INTERVAL    = 30        # 폴링 주기 (초)
QUERY_MARKER     = 0xf7      # 배터리 쿼리 magic byte
FEATURE_BUF_SIZE = 65        # RID 1 + data 64
BATTERY_RESP_IDX = 3         # hidapi 응답에서 % 위치 (RID + data[0..1] + data[2])


def _open_vendor_iface():
    """usage_page == 0xFFFF 인 첫 열림 가능한 vendor 인터페이스 핸들."""
    for d in find_devices():
        if d.get("usage_page", 0) < 0xFF00:
            continue
        try:
            dev = hid.device()
            dev.open_path(d["path"])
            return dev
        except Exception:
            continue   # macOS가 점유한 vendor iface는 건너뜀
    return None


def read_battery() -> int | None:
    """매칭 디바이스의 배터리 % (0~100) 반환. 실패 시 None."""
    dev = _open_vendor_iface()
    if dev is None:
        return None
    try:
        out_buf = bytes([0x00, QUERY_MARKER] + [0x00] * 63)
        n = dev.send_feature_report(out_buf)
        if n is None or n < 0:
            logger.debug(f"send_feature_report 거부 (n={n})")
            return None

        resp = dev.get_feature_report(0, FEATURE_BUF_SIZE)
        if not resp or len(resp) <= BATTERY_RESP_IDX:
            logger.debug(f"응답 길이 부족: {len(resp) if resp else 0}")
            return None

        level = resp[BATTERY_RESP_IDX]
        if not 0 <= level <= 100:
            logger.warning(f"배터리 응답 범위 밖: {level}, raw={list(resp[:8])}")
            return None
        return level
    except Exception as e:
        logger.warning(f"Battery read failed: {e}")
        return None
    finally:
        try: dev.close()
        except Exception: pass


class BatteryMonitor:
    """배터리 백그라운드 폴링. on_update(level: int) 콜백으로 UI 통보."""

    def __init__(self, on_update=None):
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_update = on_update
        self._level: int | None = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("BatteryMonitor started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def read_now(self) -> int | None:
        """즉시 1회 읽기 + 변화 시 콜백."""
        level = read_battery()
        if level is not None and level != self._level:
            logger.info(f"Battery: {level}%")
            self._level = level
            if self._on_update:
                self._on_update(level)
        return level

    @property
    def level(self) -> int | None:
        return self._level

    def _loop(self):
        while self._running:
            self.read_now()
            for _ in range(POLL_INTERVAL * 2):
                if not self._running:
                    break
                threading.Event().wait(0.5)
