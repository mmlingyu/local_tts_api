#!/usr/bin/env bash
# Start the unified loopback service. Does not choose ports 3080 or 8080.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${TTS_PORT:-8800}"
case "$PORT" in
  80|443|3080|8080)
    echo "拒绝监听 ${PORT}。不会改动已有的 DeepSeek 或 Caddy。" >&2
    exit 2
    ;;
esac
python3 "$ROOT/deploy/check-host.py" --require-flags >/dev/null
PY="${PIPER_PYTHON:-$ROOT/piper-zh-service/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "缺少 $PY。先为 Piper 建单独的虚拟环境，不要把 Pocket 的 torch 装进去。" >&2
  exit 1
fi
cd "$ROOT/piper-zh-service"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export HF_HUB_DISABLE_TELEMETRY="${HF_HUB_DISABLE_TELEMETRY:-1}"
export PHONON_THREADS="${PHONON_THREADS:-2}"
exec "$PY" -m piper_zh --host 127.0.0.1 --port "$PORT" --device cpu --cache-limit "${PIPER_CACHE_LIMIT:-2}"
