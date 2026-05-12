# 🐭 AJAZZ Companion

macOS 메뉴바 앱 — AJAZZ 2.4G 8K 무선 마우스 도크용

| 기능 | v1 | v2 |
|---|:---:|:---:|
| 🕒 **Clock Sync** — 도크 시계 자동 동기화 (15초 주기) | ✅ | ✅ |
| 🔍 **Device Scanner** — 메뉴에서 HID 장치 확인 | ✅ | ✅ |
| 🔋 **Battery** — 메뉴바에 잔량 표시 | ⏳ pending | ✅ |
| 🎞️ **GIF Upload** — GIF → 도크 스크린 | ⏳ pending | ✅ |

⏳ pending 항목은 Wireshark 캡처 후 활성화 예정 (메뉴엔 placeholder로 표시).

---

## 설치

```bash
# 1. venv 생성 + 의존성 설치
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. macOS 권한 부여 (필수!)
#    시스템 설정 → 개인 정보 보호 및 보안
#    → 입력 모니터링 → + 버튼 → .venv 내부 python3 추가

# 3. 실행
.venv/bin/python3 main.py
```

## 확인된 동작 환경

- Jake AJAZZ 2.4G 8K (VID `0x3151` / PID `0x5007`)
- macOS Darwin 25.x
- Python 3.13 + `hidapi` 0.15.0

다른 AJAZZ 모델(AJ179, AJ199, AJ159 등)은 `mstoiakevych/ajazz-clock-sync`에서 검증된 프로토콜을 그대로 사용하므로 호환 가능성이 높음.

---

## 프로젝트 구조

```
ajazz_apex/
├── main.py              # 진입점
├── battery_probe.py     # 배터리 프로토콜 발견 도구 (v2 작업용)
├── requirements.txt
├── install.sh
└── ajazz/
    ├── __init__.py
    ├── protocol.py      # HID 패킷 정의
    ├── clock_sync.py    # 시계 동기화 서비스
    ├── battery.py       # 배터리 (v1: 스텁)
    ├── gif_uploader.py  # GIF 업로드 (v2: 미검증)
    └── app.py           # rumps 메뉴바 앱
```

---

## v2 로드맵 — 배터리/GIF 활성화

배터리와 GIF 프로토콜은 Wireshark + USBPcap (Windows VM)으로 정품 AJAZZ 소프트웨어의 USB 트래픽 캡처가 필요합니다:

1. Windows VM에서 공식 AJAZZ 드라이버 실행
2. Wireshark + USBPcap으로 동글 트래픽 캡처
3. 배터리 표시 갱신 / GIF 업로드 트리거 후 패킷 확인
4. `ajazz/protocol.py`의 미검증 상수 채우기
5. `battery.py` / `gif_uploader.py` 본 구현 활성화

## 참고 레퍼런스

- [mstoiakevych/ajazz-clock-sync](https://github.com/mstoiakevych/ajazz-clock-sync) — Clock sync 프로토콜 (검증됨)
- [Rockeyxx/AJ179-linux-battery](https://github.com/Rockeyxx/AJ179-linux-battery) — AJ179 배터리 (Jake 모델엔 미호환 확인)
- [aar-rafi/aks075-linux](https://github.com/aar-rafi/aks075-linux) — AJAZZ 키보드 스크린 (vendor HID 패턴 참고)

---

## License: MIT
