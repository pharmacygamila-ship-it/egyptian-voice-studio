#!/usr/bin/env bash
# تشغيل سيرفر الـ API على الـ GPU.
# الاستخدام:  bash deploy/run_server.sh        (PORT=8000 افتراضياً)
set -euo pipefail

cd "$(dirname "$0")/.."

export TTS_ENGINE="${TTS_ENGINE:-local}"
export HF_HOME="${HF_HOME:-/workspace/models}"
export TTS_OUTPUT_DIR="${TTS_OUTPUT_DIR:-/workspace/outputs}"
export PORT="${PORT:-8000}"

mkdir -p "$HF_HOME" "$TTS_OUTPUT_DIR"

echo "TTS_ENGINE=$TTS_ENGINE  HF_HOME=$HF_HOME  PORT=$PORT"
if [ -n "${TTS_SERVER_TOKEN:-}" ]; then
  echo "🔐 الحماية بالتوكن مفعّلة"
else
  echo "⚠️  TTS_SERVER_TOKEN مش متعيّن — السيرفر مفتوح لأي حد. عيّنه للإنتاج!"
fi

exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT"
