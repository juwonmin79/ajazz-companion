"""
ajazz/clock_sync.py
──────────────────────────────────────────────
HID Feature Report로 시스템 시각을 마우스 도크로 전송.

연결 감지 → 즉시 동기화 → 15초 주기 유지
(맥 수면/복귀 시에도 자동 재동기화)

프로토콜: mstoiakevych/ajazz-clock-sync 원본 패턴
  - 매칭 디바이스의 모든 인터페이스에 send_feature_report 시도
  - 받지 않는 인터페이스(키보드/마우스)는 자연스럽게 예외 발생 → 무시
  - 하나라도 성공하면 OK
"""

import hid
import threading
import logging
from datetime import datetime

from .protocol import find_devices, build_clock_packet

logger = logging.getLogger(__name__)

SYNC_INTERVAL = 15  # 초
POLL_INTERVAL = 0.5  # 초 (연결 대기 중 enumerate 폴링 주기)


class ClockSyncer:
    def __init__(self, on_status_change=None):
        """
        on_status_change(bool): 디바이스 연결 상태 콜백
        """
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_status_change = on_status_change
        self._connected = False

    # ─────────────────────────────
    #  퍼블릭 API
    # ─────────────────────────────

    def start(self):
        """백그라운드 동기화 시작."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("ClockSyncer started")

    def stop(self):
        """동기화 정지."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("ClockSyncer stopped")

    def sync_now(self) -> bool:
        """수동 즉시 동기화. 성공 여부 반환."""
        return self._sync_once()

    @property
    def connected(self) -> bool:
        return self._connected

    # ─────────────────────────────
    #  내부 로직
    # ─────────────────────────────

    def _loop(self):
        # 연결 대기 중에는 POLL_INTERVAL로 빠르게 enumerate.
        # 디바이스 감지되는 순간 즉시 sync 1회 → 이후 SYNC_INTERVAL 주기.
        while self._running:
            if find_devices():
                self._sync_once()
                self._interruptible_wait(SYNC_INTERVAL)
            else:
                self._set_connected(False)
                self._interruptible_wait(POLL_INTERVAL)

    def _interruptible_wait(self, seconds: float):
        steps = max(1, int(seconds / 0.5))
        step = seconds / steps
        for _ in range(steps):
            if not self._running:
                return
            threading.Event().wait(step)

    def _sync_once(self) -> bool:
        """
        매칭된 모든 인터페이스에 Feature Report 전송 시도.
        하나라도 성공하면 OK.
        """
        devices = find_devices()
        if not devices:
            self._set_connected(False)
            logger.debug("No Ajazz device found")
            return False

        payload = build_clock_packet(datetime.now())
        success = False

        for device_dict in devices:
            device = None
            try:
                device = hid.device()
                device.open_path(device_dict["path"])
                device.send_feature_report(payload)
                success = True
            except Exception:
                # Feature report를 받지 않는 인터페이스(키보드/마우스)는 정상적으로 실패
                continue
            finally:
                if device is not None:
                    try:
                        device.close()
                    except Exception:
                        pass

        if success:
            self._set_connected(True)
            logger.info(f"Clock synced → {datetime.now().strftime('%H:%M:%S')}")
        else:
            self._set_connected(False)
            logger.warning("Clock sync failed: no interface accepted feature report")
        return success

    def _set_connected(self, state: bool):
        if state != self._connected:
            self._connected = state
            if self._on_status_change:
                self._on_status_change(state)
