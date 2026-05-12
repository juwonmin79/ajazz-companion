# 🐭 AJAZZ Companion

macOS menu bar app for AJAZZ 2.4G 8K wireless mouse dock.

| Feature | Status |
|---|:---:|
| 🕒 **Clock Sync** — Auto-sync dock clock (15s interval) | ✅ |
| 🔋 **Battery** — Live battery % in menu bar | ✅ |
| 🎞️ **GIF Upload** — GIF → dock screen | 🚧 v3 planned |

---

## Install (packaged app)

```bash
# 1. Build icon
./build_icon.sh

# 2. Build .app
.venv/bin/python3 setup.py py2app

# 3. Install + register login item
cp -R dist/AjazzCompanion.app /Applications/
./install_launchagent.sh /Applications/AjazzCompanion.app
```

## Run in dev mode

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 main.py
```

> **macOS permission required**  
> System Settings → Privacy & Security → **Input Monitoring** → click `+` → add `python3` from `.venv/bin/`

---

## Confirmed environment

- AJAZZ 2.4G 8K (VID `0x3151` / PID `0x5007`)
- macOS Darwin 25.x (Apple Silicon)
- Python 3.13 + `hidapi` 0.15.0, `rumps`, `Pillow`

Other AJAZZ models (AJ179, AJ199, AJ159, etc.) likely compatible as they share the same vendor HID protocol.

---

## How the battery protocol was discovered

No Wireshark or USBPcap needed — reverse engineered via **WebHID hooking** in Chrome DevTools:

```
Hook HIDDevice.prototype in Chrome DevTools
→ Capture 0xf7 polling magic byte (OUT)
→ IN response byte[2] = battery %
  (hidapi prepends Report ID, so actual index is resp[3])
```

---

## Project structure

```
ajazz_apex/
├── main.py
├── setup.py                  # py2app packaging
├── build_icon.sh             # SVG → ICNS
├── install_launchagent.sh
├── uninstall_launchagent.sh
├── battery_probe.py          # protocol discovery tool
└── ajazz/
    ├── protocol.py           # HID packet definitions
    ├── clock_sync.py         # clock sync service
    ├── battery.py            # battery monitor (30s poll)
    ├── gif_uploader.py       # v3 planned
    └── app.py                # rumps menu bar app
```

---

## References

- [mstoiakevych/ajazz-clock-sync](https://github.com/mstoiakevych/ajazz-clock-sync) — clock protocol
- [Rockeyxx/AJ179-linux-battery](https://github.com/Rockeyxx/AJ179-linux-battery) — AJ179 battery (incompatible with our model)
- [aar-rafi/aks075-linux](https://github.com/aar-rafi/aks075-linux) — AJAZZ vendor HID patterns

---

## License

MIT
