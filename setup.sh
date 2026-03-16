#!/bin/bash
# STT MCP 서버 자동 설치 스크립트

set -e

echo "🚀 STT MCP 서버 설치를 시작합니다..."
echo ""

find_python() {
    if [ -n "$PYTHON" ] && command -v "$PYTHON" >/dev/null 2>&1; then
        echo "$PYTHON"
        return 0
    fi
    for cmd in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$cmd" >/dev/null 2>&1; then
            VERSION=$("$cmd" --version 2>&1 | awk '{print $2}')
            MAJOR=$(echo "$VERSION" | cut -d. -f1)
            MINOR=$(echo "$VERSION" | cut -d. -f2)
            if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

echo "✅ Python 버전 확인 중..."
PYTHON_CMD=$(find_python)

if [ $? -ne 0 ]; then
    echo "❌ Python 3.10 이상을 찾을 수 없습니다."
    echo "  macOS: brew install python@3.11"
    echo "  또는: PYTHON=python3.11 ./setup.sh"
    exit 1
fi

echo "   사용할 Python: $PYTHON_CMD ✓"
echo ""

if [ ! -d ".venv" ]; then
    echo "📦 가상환경 생성 중..."
    "$PYTHON_CMD" -m venv .venv
    echo "   가상환경 생성 완료 ✓"
else
    echo "📦 기존 가상환경 사용"
fi
echo ""

echo "🔧 가상환경 활성화 중..."
source .venv/bin/activate
echo ""

echo "⬆️  pip 업그레이드 중..."
python -m pip install --upgrade pip -q
echo ""

echo "📥 의존성 설치 중 (faster-whisper 포함, 첫 설치 시 모델 다운로드 가능)..."
python -m pip install -r requirements.txt -q
echo "   의존성 설치 완료 ✓"
echo ""

if ! command -v mcpo >/dev/null 2>&1; then
    echo "   mcpo 설치 중..."
    python -m pip install mcpo -q
fi
echo "   mcpo 확인 완료 ✓"
echo ""

echo "✅ 설치 완료!"
echo ""
echo "📌 서버 시작: ./start.sh"
echo "   또는: source .venv/bin/activate && mcpo --port 8001 -- python stt_mcp.py"
echo ""
echo "🌐 Open Web UI: Admin → External Tools → OpenAPI → http://localhost:8001"
echo ""
