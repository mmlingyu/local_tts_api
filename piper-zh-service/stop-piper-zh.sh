#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
STATE="service-state.json"
if [[ ! -f "$STATE" ]]; then
  echo "No service state"
  exit 0
fi
PID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pid"])' "$STATE")"
if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  rm -f "$STATE"
  echo "Stopped PID $PID"
else
  echo "Recorded process is absent; nothing stopped"
fi
