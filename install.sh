#!/bin/bash
# install.sh — AJAZZ Companion macOS 설치 스크립트
# 실행: bash install.sh

set -e

echo "🔧 AJAZZ Companion 설치 시작"
echo "================================"

# 1. Python 버전 확인
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 필요: brew install python"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PY_VER 확인"

# 2. venv 생성
if [ ! -d ".venv" ]; then
    echo "📦 .venv 생성 중..."
    python3 -m venv .venv
fi
echo "✓ .venv 준비됨"

# 3. Python 패키지 설치 (hidapi PyPI 패키지가 hidapi C 라이브러리 포함)
echo "📦 의존성 설치 중..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
echo "✓ 패키지 설치 완료"

echo ""
echo "✅ 설치 완료!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  첫 실행 전 필수: macOS 권한 부여"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  시스템 설정 → 개인 정보 보호 및 보안"
echo "  → 입력 모니터링 → + 버튼"
echo "  → 다음 파일 추가:"
echo "    $(pwd)/.venv/bin/python3"
echo ""
echo "▶  실행: .venv/bin/python3 main.py"
echo ""
