#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
node sync-compare.cjs
if [[ ! -f public/app.js || ! -f public/kokoro-client.js ]]; then
  if [[ -d node_modules/@uzen/kokoro-js ]]; then
    node build.cjs
  else
    echo "尚未构建 Kokoro。对照页仍可启动。需要 Kokoro 时再执行 npm ci 和 node build.cjs。" >&2
  fi
fi
export PORT="${PORT:-8787}"
if [[ -f service-state.json ]]; then
  old_pid="$(node -e 'const s=require("./service-state.json"); process.stdout.write(String(s.pid||""))')"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    kill "$old_pid" || true
    sleep 0.4
  fi
fi
if ! python3 -c 'import socket,sys; s=socket.socket();
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()' "$PORT"; then
  echo "端口 ${PORT} 仍被占用，没有改到别的端口。请先停掉旧的 node server.cjs。" >&2
  exit 1
fi
exec node server.cjs
