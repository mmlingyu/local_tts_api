#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
node sync-compare.cjs
if [[ ! -d node_modules/@uzen/kokoro-js ]]; then
  echo "请先在 zh-web-service 执行 npm install" >&2
  exit 1
fi
if [[ ! -f public/app.js || ! -f public/kokoro-client.js ]]; then
  node build.cjs
fi
export PORT="${PORT:-8787}"
if [[ -f service-state.json ]]; then
  old_pid="$(node -e 'const s=require("./service-state.json"); process.stdout.write(String(s.pid||""))')"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    kill "$old_pid" || true
    sleep 0.4
  fi
fi
if command -v ss >/dev/null && ss -ltn | grep -q ":${PORT} "; then
  echo "端口 ${PORT} 仍被占用，没有改到别的端口。请先停掉旧的 node server.cjs。" >&2
  exit 1
fi
exec node server.cjs
