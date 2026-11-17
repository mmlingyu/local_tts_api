#!/usr/bin/env bash
# Download the official ptts 0.7.0 Linux x86_64 archive and check its SHA256.
# Does not start a service, does not read a model, and does not run ptts.exe.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
ARCHIVE_NAME="ptts-0.7.0-x86_64-unknown-linux-gnu.tar.gz"
URL="https://github.com/gradium-ai/xn-ptts/releases/download/v0.7.0/${ARCHIVE_NAME}"
DEST_DIR="${PHONON_RUNTIME_DIR:-$ROOT/runtime}"
ARCHIVE="$DEST_DIR/$ARCHIVE_NAME"
EXTRACTED="$DEST_DIR/ptts-0.7.0-x86_64-unknown-linux-gnu"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$DEST_DIR"
if [[ -e "$DEST_DIR/ptts.exe" || -e "$EXTRACTED/ptts.exe" ]]; then
  echo "发现 ptts.exe。Linux 部署不使用 Windows 可执行文件。" >&2
  exit 2
fi
if [[ ! -f "$ARCHIVE" ]]; then
  echo "下载 $URL"
  curl -fL --retry 3 -o "$ARCHIVE.partial" "$URL"
  mv "$ARCHIVE.partial" "$ARCHIVE"
fi
python3 - "$ARCHIVE" "$ROOT/upstream/ptts-0.7.0-SHA256SUMS" <<'PY'
import sys
from pathlib import Path

from linux_runtime import (
    ARCHIVE_BYTES,
    ARCHIVE_SHA256,
    SUMS_BYTES,
    SUMS_SHA256,
    official_archive_digest,
    verify_bytes,
)

verify_bytes(Path(sys.argv[2]), SUMS_SHA256, SUMS_BYTES)
official_archive_digest(Path(sys.argv[2]).read_text(encoding="utf-8"))
verify_bytes(Path(sys.argv[1]), ARCHIVE_SHA256, ARCHIVE_BYTES)
print("archive sha256 ok")
PY
rm -rf "$EXTRACTED"
tar -xzf "$ARCHIVE" -C "$DEST_DIR"
if [[ ! -f "$EXTRACTED/ptts" || -e "$EXTRACTED/ptts.exe" ]]; then
  echo "压缩包里没有 Linux 的 ptts。" >&2
  exit 2
fi
python3 - "$EXTRACTED/ptts" <<'PY'
import sys
from pathlib import Path

from linux_runtime import BINARY_BYTES, BINARY_SHA256, Layout, probe_version, verify_bytes

binary = Path(sys.argv[1])
verify_bytes(binary, BINARY_SHA256, BINARY_BYTES)
text = probe_version(
    Layout(
        binary=binary,
        model_dir=Path("models/phonon-31m-en"),
        voices_dir=Path("voices"),
        voice_catalog=Path("voices/voices.jsonl"),
        cache_dir=Path("cache"),
    )
)
print(text)
PY
echo "已放到 $EXTRACTED/ptts。未启动 HTTP，也未加载模型。"
