#!/usr/bin/env bash
# Install the unified TTS service into its own directory and systemd unit.
# --check and --render do not need root and do not call the service manager.
# --apply is what an operator runs on the target host. It never starts or
# stops units other than local-tts-api.service, and it refuses ports 3080 and 8080.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
MODE="check"
PREFIX="/opt/local-tts-api"
PORT="${TTS_PORT:-8800}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) MODE="check" ;;
    --render)
      MODE="render"
      PREFIX="${2:?缺少目录}"
      shift
      ;;
    --apply) MODE="apply" ;;
    --port)
      PORT="${2:?缺少端口}"
      shift
      ;;
    *)
      echo "只接受 --check、--render DIR、--apply、--port N。" >&2
      exit 2
      ;;
  esac
  shift
done
case "$PORT" in
  80|443|3080|8080)
    echo "端口 ${PORT} 不能给 TTS。不会改 3080 或 8080 上的服务。" >&2
    exit 2
    ;;
esac
export TTS_PORT="$PORT"
python3 "$SOURCE/deploy/check-host.py" --require-flags >/tmp/local-tts-host-check.json
if [[ "$MODE" == "check" ]]; then
  cat /tmp/local-tts-host-check.json
  echo "检查完成。没有安装，也没有启动。"
  exit 0
fi
STAGE="$PREFIX"
mkdir -p "$STAGE"
tar -C "$SOURCE" \
  --exclude .git \
  --exclude .venv \
  --exclude venv \
  --exclude node_modules \
  --exclude models \
  --exclude runtime \
  --exclude __pycache__ \
  --exclude '*.wav' \
  --exclude '*.onnx' \
  --exclude '*.gguf' \
  --exclude '*.safetensors' \
  --exclude '.env' \
  --exclude '.env.*' \
  -cf - . | tar -C "$STAGE" -xf -
mkdir -p "$STAGE/phonon/cache" "$STAGE/phonon/models" "$STAGE/phonon/voices" \
  "$STAGE/piper-zh-service/models" "$STAGE/pocket-tts-service/models"
ENV_FILE="$STAGE/local-tts-api.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cat >"$ENV_FILE" <<EOF
TTS_BIND=127.0.0.1
TTS_PORT=${PORT}
TTS_EXTRA_ORIGINS=
TTS_PUBLIC_BASE=
TTS_API_TOKEN=
PHONON_THREADS=2
PHONON_PTTS=${STAGE}/phonon/runtime/ptts-0.7.0-x86_64-unknown-linux-gnu/ptts
PHONON_MODEL_DIR=${STAGE}/phonon/models/phonon-31m-en
PHONON_VOICES_DIR=${STAGE}/phonon/voices
PHONON_VOICE_CATALOG=${STAGE}/phonon/voices/voices.jsonl
PHONON_CACHE_DIR=${STAGE}/phonon/cache
HF_HUB_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
PIPER_DEVICE=cpu
PIPER_CACHE_LIMIT=2
EOF
  chmod 600 "$ENV_FILE"
fi
UNIT_BODY=$(cat <<EOF
[Unit]
Description=Local unified TTS API (loopback only)
After=network.target

[Service]
Type=simple
WorkingDirectory=${STAGE}/piper-zh-service
EnvironmentFile=${ENV_FILE}
ExecStart=${STAGE}/deploy/run-local-tts.sh
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
MemoryMax=2G
CPUQuota=350%

[Install]
WantedBy=multi-user.target
EOF
)
printf '%s\n' "$UNIT_BODY" >"$STAGE/local-tts-api.service"
if [[ "$MODE" == "render" ]]; then
  echo "已写入 $STAGE。没有调用服务管理器，也没有启动进程。"
  exit 0
fi
if [[ "$(id -u)" -ne 0 ]]; then
  echo "--apply 需要 root。这次没有改系统单元。" >&2
  exit 1
fi
if ! command -v systemctl >/dev/null 2>&1; then
  echo "没有 systemctl，未安装单元。" >&2
  exit 1
fi
install -d -m 0755 /etc/systemd/system
if [[ -f /etc/systemd/system/local-tts-api.service ]]; then
  install -d -m 0755 /var/backups
  cp -a /etc/systemd/system/local-tts-api.service /var/backups/local-tts-api.service.prev
fi
if [[ ! -f /etc/local-tts-api.env ]]; then
  install -m 0600 "$ENV_FILE" /etc/local-tts-api.env
fi
# The unit must point at the installed env file, not the prefix copy.
sed "s#EnvironmentFile=${ENV_FILE}#EnvironmentFile=/etc/local-tts-api.env#" \
  "$STAGE/local-tts-api.service" >/etc/systemd/system/local-tts-api.service
systemctl daemon-reload
systemctl disable local-tts-api.service >/dev/null 2>&1 || true
echo "单元已写入但没有 enable，也没有启动。确认模型就位后再：systemctl enable --now local-tts-api.service"
echo "回滚只处理这个单元：deploy/rollback-local-tts.sh --apply"
