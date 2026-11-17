#!/usr/bin/env bash
# Build a source archive with no models, secrets, virtualenvs, or audio.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
SHA="$(git -C "$SOURCE" rev-parse HEAD)"
OUT_DIR="${1:-/opt/cursor/artifacts}"
mkdir -p "$OUT_DIR"
ARCHIVE="$OUT_DIR/local-tts-api-${SHA}.tar.gz"
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
  --exclude service-state.json \
  -czf "$ARCHIVE" .
sha256sum "$ARCHIVE" | tee "$ARCHIVE.sha256"
echo "$ARCHIVE"
