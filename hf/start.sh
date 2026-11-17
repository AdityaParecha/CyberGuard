#!/usr/bin/env bash
# Container entrypoint: start Ollama, make sure the model is present,
# then run the CyberGuard API (which also serves the UI) on $PORT.
set -euo pipefail

MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"

echo "==> Starting Ollama"
ollama serve > /tmp/ollama.log 2>&1 &

ready=0
for _ in $(seq 1 120); do
    if curl -fsS http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done

if [ "${ready}" -ne 1 ]; then
    echo "!! Ollama did not start. Its log:"
    cat /tmp/ollama.log
    exit 1
fi

echo "==> Pulling ${MODEL} (first start only takes a few minutes)"
ollama pull "${MODEL}"

echo "==> Starting CyberGuard on port ${PORT:-7860}"
exec python -m uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-7860}" \
    --timeout-keep-alive 120
