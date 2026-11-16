#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  echo "复用已有 .venv，不重新安装 torch。"
else
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  # Linux PyPI torch is the CUDA build. The CPU index avoids the NVIDIA wheels.
  .venv/bin/python -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
  echo "Pocket venv is ready. The HTTP server is still python -m piper_zh."
fi
echo "已有 models/hf-home 会复用。只有缓存里没有权重时才需要登录 Hugging Face。"
if [ "${1:-}" = "--confirm" ]; then
  .venv/bin/python -m pocket_local.prepare --confirm --variant english_18m_2026-10
fi
