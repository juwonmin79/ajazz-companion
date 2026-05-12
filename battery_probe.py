#!/usr/bin/env python3
"""
battery_probe.py — Battery Probe v2 (C→B 우선순위)
─────────────────────────────────────────────────
브리핑 v2 기반. 이전 dead-end는 모두 스킵하고 미탐색 영역만:

  Stage C: iface#1 (macOS 점유 4개 인터페이스) — pyusb로 우회 시도
  Stage B: iface#0 (Mouse Interrupt IN) + iface#2 (Vendor) 동시 청취
           + 마우스 movement 노이즈 필터 + baseline diff

실행: .venv/bin/python3 battery_probe.py
"""

import hid
import time
import importlib.util
from datetime import datetime

# pyusb는 Stage C에서만 필요 — 없어도 Stage B는 동작
try:
    import usb.core
    import usb.util
    PYUSB_OK = True
except ImportError:
    PYUSB_OK = False

spec = importlib.util.spec_from_file_location("protocol", "ajazz/protocol.py")
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)

VID = protocol.VENDOR_ID    # 0x3151
PID = protocol.PRODUCT_ID   # 0x5007

# 이전 Stage A에서 안 시도한 신규 Report ID 후보
# (0x28 = 시계, 0x1B = AJ179 → 둘 다 dead-end 확인됨)
NEW_RID_CANDIDATES = [
    # 0x28 인접 (clock 근처)
    0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
    # 0x1B 인접 (AJ179 근처)
    0x1A, 0x1C, 0x1D, 0x1E, 0x1F,
    # 광역 vendor 범위
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35,
    0x40, 0x50, 0x60, 0x70, 0x80, 0x81, 0x82,
    0x90, 0xA0, 0xB0, 0xC0, 0xC1,
]


# ─────────────────────────────────────────────
#  공통 유틸
# ─────────────────────────────────────────────

def hexdump(data, n=16) -> str:
    if data is None:
        return "(None)"
    return " ".join(f"{b:02X}" for b in list(data)[:n])


def iface_label(d: dict) -> str:
    up = d.get("usage_page", 0)
    us = d.get("usage", 0)
    ifn = d.get("interface_number", "?")
    if up >= 0xFF00:
        kind = "VENDOR"
    elif up == 0x01:
        kind = "GenericDesktop"
    else:
        kind = f"page=0x{up:04X}"
    return f"iface#{ifn} {kind} us=0x{us:04X}"


def is_mouse_movement(pkt) -> bool:
    """
    iface#0 mouse movement 패턴 판정:
      [0x00, X_lo, X_hi, Y_lo, Y_hi, 0x00, 0x00] — 7바이트 리포트
    노이즈 필터링용 — 이 형태는 배터리 응답이 아님.
    """
    if len(pkt) < 7 or pkt[0] != 0:
        return False
    if pkt[5] != 0 or pkt[6] != 0:
        return False
    # 7바이트 초과 시 그 이후도 모두 0이어야 마우스 movement
    if any(pkt[i] != 0 for i in range(7, min(len(pkt), 16))):
        return False
    return True


def looks_like_battery(pkt) -> list[tuple[int, int]]:
    """패킷에서 배터리 % 후보 (byte_idx, value) — 1~100 범위 + 0/FF 제외."""
    return [(i, v) for i, v in enumerate(pkt[:16]) if 1 <= v <= 100]


# ─────────────────────────────────────────────
#  STAGE C — iface#1 (macOS 점유) 접근 시도 via libusb
# ─────────────────────────────────────────────

def stage_c():
    print("\n" + "═"*70)
    print("  STAGE C — iface#1 (macOS 점유) 접근 시도 via pyusb/libusb")
    print("═"*70)

    if not PYUSB_OK:
        print("\n  ✗ pyusb 미설치. 설치 후 재실행:")
        print("    brew install libusb")
        print("    .venv/bin/pip install pyusb")
        print("\n  → Stage C 스킵, Stage B로 이동")
        return None

    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print(f"\n  ✗ USB 디바이스 못 찾음 (VID=0x{VID:04X} PID=0x{PID:04X})")
        return None

    print(f"\n  ✓ USB 디바이스 발견")
    try:
        mfr = usb.util.get_string(dev, dev.iManufacturer) if dev.iManufacturer else "?"
        prod = usb.util.get_string(dev, dev.iProduct) if dev.iProduct else "?"
        print(f"    Manufacturer: {mfr!r}")
        print(f"    Product:      {prod!r}")
    except Exception as e:
        print(f"    (string descriptors 읽기 실패: {e})")

    # 인터페이스/엔드포인트 토폴로지 출력
    try:
        cfg = dev.get_active_configuration()
    except Exception as e:
        print(f"  ✗ active configuration 못 가져옴: {e}")
        return None

    print(f"    Configuration: bConfigurationValue={cfg.bConfigurationValue}, "
          f"interfaces={cfg.bNumInterfaces}")

    iface1_alts = []
    for iface in cfg:
        print(f"    iface#{iface.bInterfaceNumber} "
              f"alt={iface.bAlternateSetting} "
              f"class=0x{iface.bInterfaceClass:02X} "
              f"endpoints={iface.bNumEndpoints}")
        for ep in iface:
            direction = "IN" if ep.bEndpointAddress & 0x80 else "OUT"
            print(f"      ep 0x{ep.bEndpointAddress:02X} {direction} "
                  f"type=0x{ep.bmAttributes & 0x03:02X} "
                  f"maxpkt={ep.wMaxPacketSize}")
        if iface.bInterfaceNumber == 1:
            iface1_alts.append(iface)

    if not iface1_alts:
        print("\n  ✗ iface#1 인터페이스 디스크립터가 없음.")
        return None

    captured = []
    for iface in iface1_alts:
        print(f"\n  → iface#1 alt={iface.bAlternateSetting} claim 시도…")
        try:
            if dev.is_kernel_driver_active(1):
                try:
                    dev.detach_kernel_driver(1)
                    print(f"    ✓ kernel driver detach 성공")
                except Exception as e:
                    print(f"    ✗ detach 실패: {e}")
                    print(f"    (macOS는 시스템 HID 인터페이스의 detach를 차단)")
                    continue

            usb.util.claim_interface(dev, 1)
            print(f"    ✓ claim 성공! Interrupt IN 청취 시작…")

            in_ep = next((ep for ep in iface if ep.bEndpointAddress & 0x80), None)
            if in_ep is None:
                print("    ✗ Interrupt IN 엔드포인트 없음")
                usb.util.release_interface(dev, 1)
                continue

            print(f"    ep 0x{in_ep.bEndpointAddress:02X} maxpkt={in_ep.wMaxPacketSize}")
            deadline = time.time() + 1.5
            while time.time() < deadline:
                try:
                    data = dev.read(in_ep.bEndpointAddress, in_ep.wMaxPacketSize, timeout=100)
                    if data:
                        captured.append(bytes(data))
                except usb.core.USBError as e:
                    # ETIMEDOUT은 정상 (데이터 없음)
                    if "timeout" in str(e).lower() or getattr(e, "errno", 0) in (60, 110):
                        continue
                    print(f"    read 오류: {e}")
                    break

            usb.util.release_interface(dev, 1)
            try:
                dev.attach_kernel_driver(1)
            except Exception:
                pass

            if captured:
                print(f"\n  🎯 iface#1 alt={iface.bAlternateSetting} 에서 "
                      f"{len(captured)}개 패킷 수신:")
                seen = set()
                for pkt in captured:
                    sig = bytes(pkt[:16])
                    if sig in seen:
                        continue
                    seen.add(sig)
                    cands = looks_like_battery(list(pkt))
                    hint = f"  배터리 후보: {cands}" if cands else ""
                    print(f"      [{hexdump(pkt)}]{hint}")
                return captured
            else:
                print("    (수신 없음 — 마우스 클릭/이동 유도하거나 길게 청취 필요)")

        except usb.core.USBError as e:
            print(f"    ✗ USB 오류: {e}")
            print(f"    macOS는 시스템 HID 인터페이스를 독점하므로 claim 거의 불가능")
        except Exception as e:
            print(f"    ✗ 예외: {e}")

    print("\n  Stage C 결론: macOS 권한 벽으로 iface#1 차단됨 (예상된 결과)")
    return None


# ─────────────────────────────────────────────
#  STAGE B — iface#0 (Mouse) + iface#2 (Vendor) 동시 청취
# ─────────────────────────────────────────────

def stage_b():
    print("\n" + "═"*70)
    print("  STAGE B — iface#0 + iface#2 동시 청취 + 노이즈 필터")
    print("═"*70)

    devs = protocol.find_devices()
    sender_info = next(
        (d for d in devs if d.get("usage_page", 0) >= 0xFF00
                          and d.get("interface_number") == 2),
        None
    )
    if sender_info is None:
        print("\n  ✗ iface#2 vendor 못 찾음")
        return None

    # 청취용 핸들 (송신용 제외, 열 수 있는 것만)
    listeners = []
    for d in devs:
        if d["path"] == sender_info["path"]:
            continue
        try:
            ld = hid.device()
            ld.open_path(d["path"])
            ld.set_nonblocking(True)
            listeners.append((d, ld))
        except Exception:
            pass

    print(f"\n  송신: {iface_label(sender_info)}")
    print(f"  청취: 송신측 자체 + {len(listeners)}개 다른 인터페이스")
    for d, _ in listeners:
        print(f"        ├ {iface_label(d)}")

    try:
        sender = hid.device()
        sender.open_path(sender_info["path"])
        sender.set_nonblocking(True)
    except Exception as e:
        print(f"  ✗ sender 못 엶: {e}")
        for _, ld in listeners:
            try: ld.close()
            except: pass
        return None

    def all_handles():
        """(label, dev) 튜플 시퀀스로 모든 청취 핸들 yield."""
        yield ("send-iface", sender, sender_info)
        for d, ld in listeners:
            yield (iface_label(d), ld, d)

    # ─── 1) 베이스라인 청취 (쿼리 없이 노이즈 시그니처 수집) ───
    print("\n  [1/3] 베이스라인 2초 청취 (마우스 가만히 두세요)…")
    baseline = set()
    deadline = time.time() + 2.0
    while time.time() < deadline:
        for _, dev, _ in all_handles():
            try:
                d = dev.read(64)
            except Exception:
                d = None
            if d:
                baseline.add(tuple(d[:16]))
        time.sleep(0.003)
    print(f"        {len(baseline)}개 노이즈 시그니처 수집됨")

    # ─── 2) 후보 RID 스윕: SET_FEATURE → 양쪽 청취 → diff ───
    print(f"\n  [2/3] {len(NEW_RID_CANDIDATES)}개 신규 RID 후보 스윕")
    print(f"        (각 RID 당 SET_FEATURE 후 500ms 청취, 마우스 노이즈 필터링)\n")

    hits = []
    for rid in NEW_RID_CANDIDATES:
        # 페이로드: 첫 바이트 = RID, 나머지 0
        payload = bytearray(64)
        payload[0] = rid

        try:
            n = sender.send_feature_report(bytes(payload))
            if n is None or n < 0:
                # SET이 거부되면 그 RID는 스킵
                print(f"     RID 0x{rid:02X}: SET 거부 (n={n})")
                continue
        except Exception as e:
            print(f"     RID 0x{rid:02X}: SET 예외 — {e}")
            continue

        novel = []
        deadline = time.time() + 0.5
        while time.time() < deadline:
            for label, dev, _ in all_handles():
                try:
                    d = dev.read(64)
                except Exception:
                    d = None
                if not d:
                    continue
                sig = tuple(d[:16])
                if sig in baseline:
                    continue
                if is_mouse_movement(d):
                    baseline.add(sig)   # 새 마우스 frame도 노이즈로 흡수
                    continue
                novel.append((label, list(d)))
                baseline.add(sig)
            time.sleep(0.003)

        if novel:
            print(f"  🎯 RID 0x{rid:02X}: 신규 {len(novel)}개 패킷")
            for label, pkt in novel[:3]:
                cands = looks_like_battery(pkt)
                hint = f"  배터리 후보: {cands}" if cands else ""
                print(f"      {label}: [{hexdump(pkt)}]{hint}")
            if len(novel) > 3:
                print(f"      … +{len(novel)-3}개")
            hits.append((rid, novel))
        else:
            print(f"     RID 0x{rid:02X}: 신규 없음")

    # ─── 3) 정리 ───
    try: sender.close()
    except: pass
    for _, ld in listeners:
        try: ld.close()
        except: pass

    print(f"\n  [3/3] 요약: {len(hits)}개 RID가 신규 응답 유발")
    if hits:
        print(f"        후속 분석 대상: {[f'0x{r:02X}' for r, _ in hits]}")
    return hits


# ─────────────────────────────────────────────
#  메인
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n🐙 Battery Probe v2 — C→B 순서")
    print(f"   시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   타깃: VID=0x{VID:04X} PID=0x{PID:04X}")

    devs = protocol.find_devices()
    if not devs:
        print("\n❌ AJAZZ 장치 못 찾음. 동글 연결 확인.")
        raise SystemExit(1)
    print(f"   매칭 인터페이스: {len(devs)}개")

    # Stage C 먼저 (가장 유망하지만 차단 가능성 높음)
    c_result = stage_c()

    print("\n" + "─"*70)
    if c_result:
        print("Stage C에서 iface#1 진입 성공 → 추가 정보 수집을 위해 Stage B도 실행")
    else:
        print("Stage C 차단 (예상). Stage B로 진행…")
    print("─"*70)

    # Stage B 항상 실행 (C가 성공해도 보조 정보)
    b_result = stage_b()

    # 최종 요약
    print("\n" + "━"*70)
    print("🐙 Battery Probe v2 완료")
    print("━"*70)
    if c_result:
        print(f"  Stage C: iface#1에서 {len(c_result)}개 패킷 캡처 → 분석 필요")
    else:
        print(f"  Stage C: 차단 (macOS HID 점유 — 정상)")
    if b_result:
        print(f"  Stage B: 🎯 {len(b_result)}개 RID 응답 유발 → 후속 분석")
        print(f"           ({[f'0x{r:02X}' for r, _ in b_result]})")
    else:
        print(f"  Stage B: 후보 RID 모두 무응답")
    print()
    print("다음 단계:")
    if c_result or b_result:
        print("  → 후보 패킷의 byte 위치별로 배터리 % (1~100) 추적")
        print("  → 마우스 충전/방전 상태 변화시키며 값 변화 확인")
    else:
        print("  → Wireshark + Windows VM 캡처 (가장 확실한 마지막 카드)")
    print("━"*70 + "\n")
