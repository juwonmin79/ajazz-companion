#!/bin/bash
# uninstall_launchagent.sh — 자동 시작 등록 해제
set -e

PLIST="$HOME/Library/LaunchAgents/com.ajazz.companion.plist"

if [ ! -f "$PLIST" ]; then
    echo "ℹ️  LaunchAgent 등록 안 됨 ($PLIST 없음)"
    exit 0
fi

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"

echo "✅ LaunchAgent 제거됨: $PLIST"
echo "   (실행 중인 앱은 그대로 — 닫으려면 메뉴 → Quit)"
