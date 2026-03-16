#!/bin/bash
# STT MCP 서버 + 음성 업로드 API 동시 실행 (Open Web UI 연동)

set -e

echo "🎤 STT MCP 서버를 시작합니다..."
echo ""

if [ ! -d ".venv" ]; then
    echo "❌ 가상환경이 없습니다. 먼저 ./setup.sh 를 실행하세요."
    exit 1
fi

source .venv/bin/activate

if ! command -v mcpo >/dev/null 2>&1; then
    echo "❌ mcpo를 찾을 수 없습니다."
    echo "   pip install mcpo 후 다시 실행하세요."
    exit 1
fi

MCP_PORT="${MCP_PORT:-8001}"
UPLOAD_PORT="${UPLOAD_PORT:-8002}"

for p in $MCP_PORT $UPLOAD_PORT; do
  if lsof -Pi :$p -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  포트 $p 가 이미 사용 중입니다."
    echo "   MCP_PORT=8003 UPLOAD_PORT=8004 ./start.sh 처럼 다른 포트를 쓰세요."
    exit 1
  fi
done

# 업로드 서버 백그라운드 (음성 파일 업로드 → URL 발급)
echo "📤 업로드 API 시작 (음성 파일 업로드용): http://localhost:$UPLOAD_PORT"
uvicorn upload_server:app --host 0.0.0.0 --port "$UPLOAD_PORT" &
UPID=$!
trap "kill $UPID 2>/dev/null || true" EXIT
sleep 2
if ! curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$UPLOAD_PORT/" 2>/dev/null | grep -q 200; then
  echo "⚠️  업로드 서버($UPLOAD_PORT)가 응답하지 않습니다. 브라우저에서는 반드시 http://localhost:$UPLOAD_PORT 로 열어주세요."
else
  echo "   ✓ 업로드 페이지 준비됨 → 브라우저에서 http://localhost:$UPLOAD_PORT 로 열기"
fi

echo "📡 MCP 서버 시작 (STT 도구): http://localhost:$MCP_PORT"
echo ""
echo "  Open Web UI에서 MCP 도구 URL: http://localhost:$MCP_PORT"
echo "  음성 업로드 후 URL 받기:      http://localhost:$UPLOAD_PORT"
echo "  → 받은 URL을 채팅에 붙여넣고 '이 음성 STT해줘' 라고 하세요."
echo ""
echo "🛑 종료: Ctrl+C"
echo ""

mcpo --port "$MCP_PORT" -- python stt_mcp.py
