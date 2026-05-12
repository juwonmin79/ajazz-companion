"""
ajazz/protocol.py
─────────────────────────────────────────────────────────
AJAZZ 마우스 HID 프로토콜 정의 및 패킷 빌더

✅ Clock Sync: mstoiakevych/ajazz-clock-sync 원본 로직
   Jake AJAZZ 2.4G 8K (VID 0x3151 / PID 0x5007) 도크에서 동작 확인.
⚠️  Battery / Image upload: 미검증 — Wireshark 캡처 필요
"""

from datetime import datetime
import hid

# ──────────────────────────────────────────────
#  디바이스 식별
#  product_string 매칭이 VID/PID 하드코딩보다 안전 (모델 무관)
# ──────────────────────────────────────────────
VENDOR_ID  = 0x3151   # Jake AJAZZ 2.4G 8K (참고용)
PRODUCT_ID = 0x5007

DEVICE_NAME_KEYWORDS = ("AJAZZ", "2.4G")   # 두 키워드 모두 포함 (AND)


def is_target_device(device_dict: dict) -> bool:
    """product_string에 'AJAZZ'와 '2.4G'가 모두 포함되는지 판정."""
    prod = (device_dict.get("product_string") or "").upper()
    return all(k in prod for k in DEVICE_NAME_KEYWORDS)


def find_devices() -> list[dict]:
    """
    매칭 AJAZZ 디바이스의 모든 HID 인터페이스 반환.
    하나의 USB 동글이 여러 인터페이스(키보드/마우스/벤더)를 노출하므로
    호출자는 모든 인터페이스에 순차 전송하고 실패는 무시해야 함.
    """
    return [d for d in hid.enumerate() if is_target_device(d)]


def open_device(path: bytes):
    """디바이스 path로 열기. 호출자가 .close() 책임짐."""
    device = hid.device()
    device.open_path(path)
    return device


# ──────────────────────────────────────────────
#  Clock Sync (검증됨)
#  Feature Report 0x28 / cmd 0xd7 @ index 7
#  year big-endian raw @ [8..9], month/day/H/M/S raw @ [10..14]
# ──────────────────────────────────────────────
FEATURE_REPORT_SIZE = 64
CLOCK_REPORT_ID     = 0x28
CLOCK_CMD_INDEX     = 7
CLOCK_CMD_VALUE     = 0xd7


def build_clock_packet(t: datetime | None = None) -> list[int]:
    """
    Feature Report payload (64 바이트 list[int]).
    호출 측에서 hid.device().send_feature_report(packet) 으로 전송.

    레이아웃:
      [0]  = 0x28 (Report ID)
      [7]  = 0xd7 (Command)
      [8]  = year >> 8        (big-endian, raw binary)
      [9]  = year & 0xFF
      [10] = month
      [11] = day
      [12] = hour
      [13] = minute
      [14] = second
    """
    if t is None:
        t = datetime.now()

    payload = [0x00] * FEATURE_REPORT_SIZE
    payload[0]  = CLOCK_REPORT_ID
    payload[7]  = CLOCK_CMD_VALUE
    payload[8]  = t.year >> 8
    payload[9]  = t.year & 0xFF
    payload[10] = t.month
    payload[11] = t.day
    payload[12] = t.hour
    payload[13] = t.minute
    payload[14] = t.second
    return payload


# ──────────────────────────────────────────────
#  Battery / Image — 미검증 (Wireshark 캡처 필요)
#  아래 함수는 추정 포맷. 동작 확인 안 됨.
# ──────────────────────────────────────────────
BATTERY_REPORT_ID  = 0x06
CMD_GET_BATTERY    = 0x09
BATTERY_BYTE_IDX   = 3

IMAGE_REPORT_ID    = 0x04
CMD_IMG_START      = 0x01
CMD_IMG_DATA       = 0x02
CMD_IMG_END        = 0x03
SCREEN_WIDTH       = 128
SCREEN_HEIGHT      = 128
IMG_CHUNK_SIZE     = 56


def _legacy_packet(report_id: int, cmd: int, payload: list[int]) -> bytes:
    pkt = [0x00, report_id, cmd] + payload
    pkt += [0x00] * (65 - len(pkt))
    return bytes(pkt[:65])


def build_battery_query() -> bytes:
    return _legacy_packet(BATTERY_REPORT_ID, CMD_GET_BATTERY, [])


def build_image_start(frame_idx: int, total_frames: int, width: int, height: int) -> bytes:
    payload = [
        frame_idx & 0xFF,
        total_frames & 0xFF,
        (width >> 8) & 0xFF,
        width & 0xFF,
        (height >> 8) & 0xFF,
        height & 0xFF,
    ]
    return _legacy_packet(IMAGE_REPORT_ID, CMD_IMG_START, payload)


def build_image_chunk(chunk_idx: int, data: bytes) -> bytes:
    payload = [
        (chunk_idx >> 8) & 0xFF,
        chunk_idx & 0xFF,
        len(data),
    ] + list(data)
    return _legacy_packet(IMAGE_REPORT_ID, CMD_IMG_DATA, payload)


def build_image_end(frame_idx: int) -> bytes:
    return _legacy_packet(IMAGE_REPORT_ID, CMD_IMG_END, [frame_idx & 0xFF])
