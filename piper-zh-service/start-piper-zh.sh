#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PY="${PIPER_PYTHON:-$PWD/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "未找到 $PY" >&2
  echo "请先执行：python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt" >&2
  exit 1
fi
export HF_HOME="${HF_HOME:-$PWD/models/hf-home}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
PORT="${PORT:-8791}"
if ! python3 -c 'import socket,sys; s=socket.socket();
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()' "$PORT"; then
  echo "端口 ${PORT} 已被占用。8791 可能是 Cursor，不要结束它。请改用空闲端口，例如 PORT=8800 ./start-piper-zh.sh。本脚本不会自动换端口。" >&2
  exit 1
fi
exec "$PY" -m piper_zh --host 127.0.0.1 --port "${PORT}" --device "${PIPER_DEVICE:-cpu}"
