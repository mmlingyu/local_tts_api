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
exec "$PY" -m piper_zh --host 127.0.0.1 --port "${PORT:-8791}" --device "${PIPER_DEVICE:-cpu}"
