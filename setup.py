"""
setup.py — py2app 빌드 스크립트
─────────────────────────────────────────────────
빌드: .venv/bin/python setup.py py2app
결과: dist/AjazzCompanion.app

옵션:
  - LSUIElement=True → 메뉴바 전용 (Dock 아이콘 없음)
  - argv_emulation=False → rumps와 호환 위해 비활성
  - iconfile → SVG에서 빌드한 ICNS
"""

from setuptools import setup

APP_NAME = "AjazzCompanion"
APP = ["main.py"]
ICON = "ajazz/ajazz_icon.icns"

PLIST = {
    "CFBundleName":             APP_NAME,
    "CFBundleDisplayName":      "AJAZZ Companion",
    "CFBundleIdentifier":       "com.ajazz.companion",
    "CFBundleVersion":          "0.2.0",
    "CFBundleShortVersionString": "0.2.0",
    "LSUIElement":              True,   # 메뉴바 전용
    "LSMinimumSystemVersion":   "12.0",
    "NSHumanReadableCopyright": "© 2026 Jake — MIT License",
    "NSHighResolutionCapable":  True,
}

OPTIONS = {
    "iconfile": ICON,
    "plist":    PLIST,
    "argv_emulation": False,
    # 명시 패키지 — py2app이 자동 탐지 못하는 것 보강
    "packages": ["rumps", "PIL", "ajazz"],
    "includes": [
        "hid",          # cython-hidapi extension
        "objc",
        "Foundation",
        "AppKit",
    ],
    # 추가 데이터 파일 (코드 외)은 ajazz/ 안에 있으면 packages로 따라 옴
}

setup(
    app=APP,
    name=APP_NAME,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
