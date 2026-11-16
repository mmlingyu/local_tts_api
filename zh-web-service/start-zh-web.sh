#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -d node_modules/@uzen/kokoro-js ]]; then
  echo "请先在 zh-web-service 执行 npm install" >&2
  exit 1
fi
if [[ ! -f public/app.js || ! -f public/kokoro-client.js ]]; then
  node build.cjs
fi
export PORT="${PORT:-8787}"
exec node server.cjs
