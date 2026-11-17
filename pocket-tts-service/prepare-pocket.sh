#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  echo "复用已有 .venv，不重新安装 torch。"
else
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  # PyPI 上的 torch 是 CUDA 轮。只从 CPU 索引安装，并且先装 torch。
  # 不用 --extra-index-url：那个参数仍会让 pip 选中版本更高的 CUDA 轮。
  .venv/bin/python -m pip install 'torch>=2.5.0' --index-url https://download.pytorch.org/whl/cpu
  .venv/bin/python -m pip install --upgrade-strategy only-if-needed -r requirements.txt
  .venv/bin/python -m pocket_local.torch_policy
  echo "Pocket venv is ready. The HTTP server is still python -m piper_zh."
fi
echo "已有 models/hf-home 会复用。只有缓存里没有权重时才需要登录 Hugging Face。"
if [ "${1:-}" = "--confirm" ]; then
  .venv/bin/python -m pocket_local.prepare --confirm --variant english_18m_2026-10
fi
