"""
ajazz/app.py
──────────────────────────────────────────────────────────
AJAZZ Companion — macOS 메뉴바 앱

메뉴바 아이콘:
  NN% — 배터리 잔량 (연결 시)
  ✓   — 연결됨, 배터리 미수신
  ⌛  — 미연결

드롭다운:
  🕐 HH:MM:SS                  ↻    ← 클릭 시 시계 즉시 동기화
  ─────────────────
  🔋 Battery: NN%              ↻    ← 클릭 시 배터리 즉시 갱신
                                      (≤20%는 🪫로 경고)
  ─────────────────
  Quit
"""

import logging
import signal
import threading
from datetime import datetime

import rumps
from AppKit import (
    NSAttributedString,
    NSMutableParagraphStyle,
    NSTextTab,
    NSTextAlignmentRight,
    NSParagraphStyleAttributeName,
)

from .clock_sync import ClockSyncer
from .battery import BatteryMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


TITLE_CONNECTED      = "✓"
TITLE_DISCONNECTED   = "⌛"
LOW_BATTERY_THRESH   = 20
ICON_TAB_STOP_PT     = 200.0   # 우측 아이콘이 정렬될 픽셀 위치 (포인트 단위)


def _set_row(rumps_item, left: str, icon: str = ""):
    """
    rumps MenuItem에 좌측 텍스트 + 우측 정렬 아이콘 라벨을 적용.
    NSAttributedString의 우측 정렬 탭 스톱을 써서 이모지 폭이 달라도
    아이콘 위치가 정확히 같은 픽셀에 맞춰짐 (공백 패딩 대비 정확).
    """
    if not icon:
        rumps_item._menuitem.setTitle_(left)
        return

    style = NSMutableParagraphStyle.alloc().init()
    tab = NSTextTab.alloc().initWithTextAlignment_location_options_(
        NSTextAlignmentRight, ICON_TAB_STOP_PT, {}
    )
    style.setTabStops_([tab])

    title = f"{left}\t{icon}"
    attr_str = NSAttributedString.alloc().initWithString_attributes_(
        title,
        {NSParagraphStyleAttributeName: style},
    )
    rumps_item._menuitem.setAttributedTitle_(attr_str)


class AjazzCompanionApp(rumps.App):
    def __init__(self):
        super().__init__(
            name="AjazzCompanion",
            title=TITLE_DISCONNECTED,
            quit_button=None,
        )

        self._clock_connected: bool = False
        self._battery_level: int | None = None

        self._clock   = ClockSyncer(on_status_change=self._on_clock_status)
        self._battery = BatteryMonitor(on_update=self._on_battery_update)

        self._shutdown_lock = threading.Lock()
        self._shutdown_done = False

        # ── 메뉴 항목 ──────────────────────────────
        # 메뉴 dict 키는 생성자의 title로 결정되므로 안정적인 ID 문자열 사용.
        # 실제 표시 텍스트는 _set_row() 가 attributedTitle 로 덮어씀.
        self._item_clock = rumps.MenuItem("clock_row",   callback=self.on_clock_click)
        self._item_battery = rumps.MenuItem("battery_row", callback=self.on_battery_click)
        self._item_quit  = rumps.MenuItem("Quit", callback=self._on_quit_click)

        # 초기 라벨
        _set_row(self._item_clock,   "🕐 --:--:--",  "↻")
        _set_row(self._item_battery, "🔋 Battery: –", "↻")

        self.menu = [
            self._item_clock,
            None,
            self._item_battery,
            None,
            self._item_quit,
        ]

    # ─────────────────────────────────────────────
    #  앱 시작
    # ─────────────────────────────────────────────

    def launch(self):
        self._install_signal_handlers()
        self._clock.start()
        self._battery.start()
        self.run()

    # ─────────────────────────────────────────────
    #  종료 처리 (SIGTERM/SIGINT → HID 워커 stop → quit)
    # ─────────────────────────────────────────────

    def _install_signal_handlers(self):
        # launchd/터미널 종료 시 HID 패킷이 도중에 전송되지 않도록
        # 모니터를 먼저 stop하고 앱을 내린다.
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, self._on_signal)
            except (ValueError, OSError):
                # 메인 스레드가 아니거나 핸들 불가한 시그널이면 스킵
                pass

    def _on_signal(self, signum, *_):
        logger.info(f"Received signal {signum} → shutting down")
        self._shutdown()

    def _on_quit_click(self, _):
        logger.info("Quit menu clicked → shutting down")
        self._shutdown()

    def _shutdown(self):
        with self._shutdown_lock:
            if self._shutdown_done:
                return
            self._shutdown_done = True

        try:
            self._clock.stop()
        except Exception as e:
            logger.warning(f"ClockSyncer stop failed: {e}")
        try:
            self._battery.stop()
        except Exception as e:
            logger.warning(f"BatteryMonitor stop failed: {e}")

        rumps.quit_application()

    # ─────────────────────────────────────────────
    #  메뉴 클릭 핸들러
    # ─────────────────────────────────────────────

    def on_clock_click(self, _):
        """시계 항목 클릭 → 즉시 도크 시계 재동기화."""
        ok = self._clock.sync_now()
        rumps.notification(
            title="AJAZZ Companion",
            subtitle="Clock Synced" if ok else "Sync Failed",
            message="도크 시계 동기화 완료" if ok else "마우스 연결 확인",
        )

    def on_battery_click(self, _):
        """배터리 항목 클릭 → 즉시 배터리 재읽기."""
        level = self._battery.read_now()
        if level is not None:
            rumps.notification(
                title="AJAZZ Companion",
                subtitle="Battery",
                message=f"{level}%",
            )
        else:
            rumps.notification(
                title="AJAZZ Companion",
                subtitle="Battery Read Failed",
                message="마우스 연결 확인",
            )

    # ─────────────────────────────────────────────
    #  라이브 시계 타이머 (1초 주기)
    # ─────────────────────────────────────────────

    @rumps.timer(1)
    def _tick_clock(self, _):
        if self._clock_connected:
            label = f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        else:
            label = "🕐 Not Connected"
        _set_row(self._item_clock, label, "↻")

    # ─────────────────────────────────────────────
    #  백그라운드 상태 콜백
    # ─────────────────────────────────────────────

    def _on_clock_status(self, connected: bool):
        self._clock_connected = connected
        # 시계 라벨은 _tick_clock 타이머가 알아서 갱신
        self._refresh_menubar_title()

    def _on_battery_update(self, level: int):
        self._battery_level = level
        icon = "🪫" if level <= LOW_BATTERY_THRESH else "🔋"
        _set_row(self._item_battery, f"{icon} Battery: {level}%", "↻")
        self._refresh_menubar_title()

    def _refresh_menubar_title(self):
        """메뉴바 아이콘: 배터리 % 우선, 없으면 연결 상태."""
        if not self._clock_connected:
            self.title = TITLE_DISCONNECTED
        elif self._battery_level is not None:
            self.title = f"{self._battery_level}%"
        else:
            self.title = TITLE_CONNECTED
