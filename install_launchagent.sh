#!/bin/bash
# install_launchagent.sh — 로그인 시 자동 시작 등록
# 사용:
#   ./install_launchagent.sh                          # dist/AjazzCompanion.app
#   ./install_launchagent.sh /Applications/AjazzCompanion.app
set -e

DEFAULT_APP="$(pwd)/dist/AjazzCompanion.app"
APP_PATH="${1:-$DEFAULT_APP}"

# 절대 경로로 정규화
APP_PATH="$(cd "$(dirname "$APP_PATH")" && pwd)/$(basename "$APP_PATH")"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ .app 번들을 찾을 수 없음: $APP_PATH"
    echo "   먼저 빌드: .venv/bin/python setup.py py2app"
    exit 1
fi

EXEC="$APP_PATH/Contents/MacOS/AjazzCompanion"
if [ ! -x "$EXEC" ]; then
    echo "❌ 실행 파일 없음: $EXEC"
    exit 1
fi

PLIST="$HOME/Library/LaunchAgents/com.ajazz.companion.plist"
mkdir -p "$(dirname "$PLIST")"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ajazz.companion</string>
    <key>ProgramArguments</key>
    <array>
        <string>$EXEC</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ajazz_companion.out.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ajazz_companion.err.log</string>
</dict>
</plist>
EOF

# 이미 로드돼 있으면 재로드
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ LaunchAgent 등록 완료"
echo "   plist : $PLIST"
echo "   target: $EXEC"
echo "   로그   : /tmp/ajazz_companion.{out,err}.log"
echo
echo "다음 로그인 시 자동 실행됩니다 (지금도 launchctl load로 즉시 실행됨)."
echo "제거: ./uninstall_launchagent.sh"
