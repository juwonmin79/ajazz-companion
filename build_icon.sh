#!/bin/bash
# build_icon.sh — SVG → ICNS 변환
# sips + iconutil 만 사용 (macOS native, 추가 설치 불필요)
set -e

SVG="ajazz/ajazz_icon.svg"
ICONSET="build/AjazzIcon.iconset"
ICNS="ajazz/ajazz_icon.icns"

if [ ! -f "$SVG" ]; then
    echo "❌ $SVG 없음"
    exit 1
fi

echo "🎨 SVG → ICNS 빌드"
echo "   source: $SVG"

mkdir -p "$ICONSET"

# 1) 1024 PNG 한 번 렌더 (마스터)
MASTER="/tmp/ajazz_icon_1024.png"
sips -s format png "$SVG" --out "$MASTER" -z 1024 1024 >/dev/null

# 2) Apple iconset 표준 사이즈 (10개)
#    16/32/128/256/512 + 각각 @2x
sips -z 16  16   "$MASTER" --out "$ICONSET/icon_16x16.png"      >/dev/null
sips -z 32  32   "$MASTER" --out "$ICONSET/icon_16x16@2x.png"   >/dev/null
sips -z 32  32   "$MASTER" --out "$ICONSET/icon_32x32.png"      >/dev/null
sips -z 64  64   "$MASTER" --out "$ICONSET/icon_32x32@2x.png"   >/dev/null
sips -z 128 128  "$MASTER" --out "$ICONSET/icon_128x128.png"    >/dev/null
sips -z 256 256  "$MASTER" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256 256  "$MASTER" --out "$ICONSET/icon_256x256.png"    >/dev/null
sips -z 512 512  "$MASTER" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512 512  "$MASTER" --out "$ICONSET/icon_512x512.png"    >/dev/null
cp "$MASTER"                       "$ICONSET/icon_512x512@2x.png"

# 3) .iconset → .icns
iconutil -c icns "$ICONSET" -o "$ICNS"

echo "✓ $ICNS 생성 완료 ($(ls -la "$ICNS" | awk '{print $5}') bytes)"
