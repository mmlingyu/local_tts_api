#!/usr/bin/env bash
# Pointer only. The installer that writes files is install-local-tts.sh.
set -euo pipefail
if [[ $# -ne 0 ]]; then
  echo "请改用 deploy/install-local-tts.sh。这个文件不接受参数。" >&2
  exit 2
fi
echo "安装请运行 deploy/install-local-tts.sh --check，确认后再 --render 或 --apply。"
echo "它不会占用 3080 或 8080，也不会启动已有的 DeepSeek 或 Caddy。"
