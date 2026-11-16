"""Build a lightweight Windows test zip from the current tree.

The zip is not an offline, no-install bundle. It excludes virtualenvs,
node_modules, browser profiles, logs, secrets, and model weights.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("/opt/cursor/artifacts/local-tts-api-windows-test.zip")
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "models",
    "__pycache__",
    ".pytest_cache",
    "test-output",
    "browser-profile",
    "public/ort",
    "public/kokoro",
}
SKIP_NAMES = {
    "service-state.json",
    "server.log",
    "server-error.log",
}
SKIP_SUFFIXES = {".onnx", ".bin", ".wasm", ".wav", ".log", ".pyc"}


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    parts = set(path.relative_to(ROOT).parts)
    if parts & {".git", ".venv", "node_modules", "models", "__pycache__", ".pytest_cache", "test-output", "browser-profile"}:
        return False
    if rel.startswith("phonon/"):
        return False
    if "/public/ort/" in f"/{rel}/" or rel.startswith("zh-web-service/public/ort/"):
        return False
    if rel.startswith("zh-web-service/public/kokoro/"):
        return False
    if path.name in {"app.js", "kokoro-client.js"} and "public" in path.parts:
        return False
    if path.name in SKIP_NAMES or path.suffix.lower() in SKIP_SUFFIXES:
        return False
    if path.name.startswith(".env"):
        return False
    return True


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = [path for path in ROOT.rglob("*") if path.is_file() and included(path)]
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(f"path {OUTPUT}")
    print(f"bytes {OUTPUT.stat().st_size}")
    print(f"sha256 {digest}")
    print(f"files {len(files)}")


if __name__ == "__main__":
    main()
