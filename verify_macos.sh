#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

APP_PATH="${1:-dist/FastAPI-Service.app}"
PORT="${2:-18092}"
EXECUTABLE="$APP_PATH/Contents/MacOS/FastAPI-Service"

if [[ ! -x "$EXECUTABLE" ]]; then
    echo "[ERROR] App executable not found: $EXECUTABLE" >&2
    echo "Run ./build_macos.sh first." >&2
    exit 1
fi

"$EXECUTABLE" --headless --no-browser --port "$PORT" &
APP_PID=$!

cleanup() {
    if kill -0 "$APP_PID" 2>/dev/null; then
        kill "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

HEALTH_RESPONSE=""
for _ in {1..60}; do
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        echo "[ERROR] App exited before the service became ready." >&2
        wait "$APP_PID"
        exit 1
    fi

    HEALTH_RESPONSE="$(curl -fsS "http://127.0.0.1:${PORT}/health" 2>/dev/null || true)"
    if [[ "$HEALTH_RESPONSE" == *'"status":"ok"'* ]]; then
        break
    fi
    sleep 0.5
done

if [[ "$HEALTH_RESPONSE" != *'"status":"ok"'* ]]; then
    echo "[ERROR] Health check failed or timed out." >&2
    exit 1
fi

PING_RESPONSE="$(curl -fsS "http://127.0.0.1:${PORT}/api/v1/examples/ping")"
if [[ "$PING_RESPONSE" != *'"message":"pong"'* ]]; then
    echo "[ERROR] Ping check returned an unexpected response: $PING_RESPONSE" >&2
    exit 1
fi

echo "[PASS] macOS app started successfully."
echo "[PASS] /health returned status=ok."
echo "[PASS] /api/v1/examples/ping returned pong."
