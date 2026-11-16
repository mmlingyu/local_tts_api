#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
# Linux PyPI torch is the CUDA build. The CPU index avoids the NVIDIA wheels.
.venv/bin/python -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
echo "Pocket venv is ready. The HTTP server is still python -m piper_zh."
echo "Accept https://huggingface.co/kyutai/pocket-tts before prepare --confirm."
if [ "${1:-}" = "--confirm" ]; then
  .venv/bin/python -m pocket_local.prepare --confirm
fi
