"""Official Phonon/ptts 0.7.0 Linux x86_64 runtime checks.

The executable is not stored in git. ``fetch-ptts-linux.sh`` downloads the
release archive and this module checks it against the upstream SHA256SUMS.
A Windows ``ptts.exe`` is never executed. This module does not synthesize
audio and does not invent a WAV when the checkpoint is absent.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

VERSION = "0.7.0"
ARCHIVE_NAME = "ptts-0.7.0-x86_64-unknown-linux-gnu.tar.gz"
ARCHIVE_URL = (
    "https://github.com/gradium-ai/xn-ptts/releases/download/v0.7.0/" + ARCHIVE_NAME
)
SUMS_URL = "https://github.com/gradium-ai/xn-ptts/releases/download/v0.7.0/SHA256SUMS"
ARCHIVE_SHA256 = "5c0b2b3da0a1e1d64337df865754cefd480102d24c0438f80e3043c8a2bbbcc6"
ARCHIVE_BYTES = 9_366_828
SUMS_SHA256 = "7d401d0a2326b75cea671bbe4a9a4f4e750718f7b2ad22f2ba98279c4e643023"
SUMS_BYTES = 712
BINARY_SHA256 = "0ce7735f7c5c6c27de30268a30d1e1f825cd1344e1786935148598f8f09aa555"
BINARY_BYTES = 30_323_496
# Default checkpoint revision printed by this exact binary's --help.
MODEL_REVISION = "92741c5b07d085ff840e26fea8ce43110b87852f"
# Local catalog the Windows tree already pinned. The binary's own default catalog
# revision is newer and is not used.
VOICE_CATALOG_REVISION = "0ee17205f254b5abc43b266c8a0f215565c352f7"
EXPECTED_CATALOG_VOICES = 37
EXPECTED_CATALOG_BYTES = 9_477_032
EMBEDDING_BYTES = 256_136
MODEL_FILENAMES = (
    "config.json",
    "tokenizer.json",
    "model.q8.gguf",
    "default-voice.safetensors",
)
MIN_GLIBC = (2, 35)
REQUIRED_CPU_FLAGS = frozenset({"avx2", "fma", "f16c"})
DEFAULT_THREADS = 2
MAX_THREADS = 4
MAX_TEXT_CHARS = 1000
SOURCE_BUILD = "cargo install --path ptts --locked --features cli"

PHONON_ROOT = Path(__file__).resolve().parent
SUMS_PATH = PHONON_ROOT / "upstream" / "ptts-0.7.0-SHA256SUMS"
MANIFEST_PATH = PHONON_ROOT / "voices" / "manifest.json"

_BLOB_NAME = re.compile(r"^[0-9a-fA-F]{16,64}$")
_HAN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002fffd]")


class RuntimeError_(Exception):
    """Named with a trailing underscore so it does not hide the builtin."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_sha256sums(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        # Official lines are "<64 hex>  <filename>" or "<64 hex> *<filename>".
        name = name.strip()
        if name.startswith("*"):
            name = name[1:]
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
            raise RuntimeError_("SHA256SUMS 里有无法识别的行。", "bad_checksum_file")
        found[name] = digest.lower()
    return found


def official_archive_digest(sums_text: str) -> str:
    found = parse_sha256sums(sums_text)
    digest = found.get(ARCHIVE_NAME)
    if digest is None:
        raise RuntimeError_(f"SHA256SUMS 没有 {ARCHIVE_NAME}。", "checksum_missing")
    if digest != ARCHIVE_SHA256:
        raise RuntimeError_("SHA256SUMS 与仓库里钉住的 Linux 压缩包校验和不一致。", "checksum_mismatch")
    return digest


def verify_bytes(path: Path, expected_sha256: str, expected_size: int | None = None) -> str:
    if not path.is_file():
        raise RuntimeError_(f"找不到文件：{path.name}", "file_missing")
    size = path.stat().st_size
    if expected_size is not None and size != expected_size:
        raise RuntimeError_(f"{path.name} 大小是 {size}，不是 {expected_size}。", "size_mismatch")
    digest = sha256_file(path)
    if digest != expected_sha256:
        raise RuntimeError_(f"{path.name} 的 SHA256 与官方钉住值不一致。", "checksum_mismatch")
    return digest


def is_windows_executable(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(".exe"):
        return True
    if not path.is_file():
        return False
    with path.open("rb") as handle:
        return handle.read(2) == b"MZ"


def glibc_tuple(text: str) -> tuple[int, int] | None:
    match = re.search(r"(\d+)\.(\d+)", text)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def glibc_supported(version: tuple[int, int] | None) -> bool:
    return version is not None and version >= MIN_GLIBC


def cpu_flags_supported(flags: set[str]) -> bool:
    return REQUIRED_CPU_FLAGS <= {flag.lower() for flag in flags}


@dataclass(frozen=True)
class Layout:
    binary: Path
    model_dir: Path
    voices_dir: Path
    voice_catalog: Path
    cache_dir: Path
    threads: int = DEFAULT_THREADS

    def voice_index(self) -> dict[str, tuple[str, str, Path]]:
        import json

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if manifest.get("revision") != VOICE_CATALOG_REVISION:
            raise RuntimeError_("voices/manifest.json 的 revision 变了。", "catalog_revision")
        rows = manifest.get("voices")
        if not isinstance(rows, list) or len(rows) != EXPECTED_CATALOG_VOICES:
            raise RuntimeError_("英文音色清单不是 37 条。", "catalog_count")
        index: dict[str, tuple[str, str, Path]] = {
            "default": ("default", "default", self.model_dir / "default-voice.safetensors")
        }
        total = 0
        for row in rows:
            filename = row["filename"]
            if filename != Path(filename).name or "/" in filename or "\\" in filename:
                raise RuntimeError_("清单里的文件名必须是单个文件名。", "catalog_filename")
            if not filename.endswith(".safetensors"):
                raise RuntimeError_("清单里只接受 .safetensors。", "catalog_filename")
            total += int(row["bytes"])
            choice = (row["id"], row["name"], self.voices_dir / filename)
            for key in (row["id"].lower(), row["name"].lower()):
                if key in index and index[key] != choice:
                    raise RuntimeError_(f"音色键冲突：{key}", "catalog_conflict")
                index[key] = choice
        if total != EXPECTED_CATALOG_BYTES:
            raise RuntimeError_("37 个嵌入的字节数与清单不一致。", "catalog_bytes")
        return index


def layout_from_env(env: dict[str, str] | None = None) -> Layout:
    source = os.environ if env is None else env
    threads = _threads(source.get("PHONON_THREADS", str(DEFAULT_THREADS)))
    return Layout(
        binary=_path_setting(source, "PHONON_PTTS", PHONON_ROOT / "runtime" / "ptts-0.7.0-x86_64-unknown-linux-gnu" / "ptts"),
        model_dir=_path_setting(source, "PHONON_MODEL_DIR", PHONON_ROOT / "models" / "phonon-31m-en"),
        voices_dir=_path_setting(source, "PHONON_VOICES_DIR", PHONON_ROOT / "voices"),
        voice_catalog=_path_setting(source, "PHONON_VOICE_CATALOG", PHONON_ROOT / "voices" / "voices.jsonl"),
        cache_dir=_path_setting(source, "PHONON_CACHE_DIR", PHONON_ROOT / "cache"),
        threads=threads,
    )


def _path_setting(env: dict[str, str], key: str, default: Path) -> Path:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    if "\n" in raw or "\x00" in raw or raw.strip().startswith(("http://", "https://", "hf://")):
        raise RuntimeError_(f"{key} 不接受 URL。", "bad_path")
    return Path(raw).expanduser()


def _threads(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError_("PHONON_THREADS 必须是整数。", "bad_threads") from exc
    if value < 1 or value > MAX_THREADS:
        raise RuntimeError_(f"PHONON_THREADS 只能是 1 到 {MAX_THREADS}。", "bad_threads")
    return value


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    base = root.resolve()
    if resolved != base and base not in resolved.parents:
        raise RuntimeError_("路径超出配置目录。", "path_escape")
    return resolved


def validate_text(text: object) -> str:
    if not isinstance(text, str) or "\x00" in text:
        raise RuntimeError_("请输入 1–1000 个字符的英文文本。", "bad_text")
    if not text.strip() or len(text) > MAX_TEXT_CHARS:
        raise RuntimeError_("请输入 1–1000 个字符的英文文本。", "bad_text")
    if _HAN.search(text):
        raise RuntimeError_("此模型仅支持英文，请使用其他引擎合成中文。", "han_text")
    return text.strip()


def resolve_voice(layout: Layout, voice: object) -> tuple[str, str, Path]:
    if voice is None:
        key = "default"
    elif not isinstance(voice, str):
        raise RuntimeError_("voice 必须是清单里的名字或 ID。", "bad_voice")
    else:
        key = voice.strip().lower()
    if (
        any(mark in key for mark in ("/", "\\", ":", "?", "#"))
        or ".." in key
        or key.startswith(("hf://", "http://", "https://"))
    ):
        raise RuntimeError_("voice 不接受路径、URL 或 hf://。", "bad_voice")
    try:
        return layout.voice_index()[key]
    except KeyError as exc:
        raise RuntimeError_("未知英文音色。只接受清单里的 37 个名字或 ID，或 default。", "unknown_voice") from exc


def parse_http_request(payload: dict) -> tuple[str, str, str]:
    """Validate a Phonon JSON object. Returns text, voice id, and voice name.

    The caller cannot supply a model path, command, or URL. File presence is
    checked later, when a real process would be started.
    """
    if not isinstance(payload, dict):
        raise RuntimeError_("请求必须是 JSON 对象。", "bad_request")
    if "speaker" in payload:
        raise RuntimeError_("Phonon 没有 Piper 的 speaker。", "speaker_not_allowed")
    if "variant" in payload:
        raise RuntimeError_("variant 只用于 Pocket。Phonon 不会改用别的模型。", "bad_request")
    raw_language = payload.get("language", "en")
    if raw_language is None:
        raw_language = "en"
    if not isinstance(raw_language, str):
        raise RuntimeError_("Phonon 只合成英语，不会改用 Piper 或 Pocket。", "unsupported_language")
    key = raw_language.strip().lower().replace("-", "_")
    if key not in {"en", "en_us", "english"}:
        raise RuntimeError_("Phonon 只合成英语，不会改用 Piper 或 Pocket。", "unsupported_language")
    text = validate_text(payload.get("text"))
    voice_id, name, _path = resolve_voice(layout_from_env(), payload.get("voice", "default"))
    return text, voice_id, name


def public_voices(layout: Layout | None = None) -> dict:
    layout = layout or layout_from_env()
    import json

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    rows = [
        {
            "id": "default",
            "voice": "default",
            "name": "default",
            "label": "默认 · default",
            "locale": "en",
            "gender": None,
            "language": "en",
            "present": _voice_file_ok(layout.model_dir / "default-voice.safetensors", default=True),
            "official": True,
        }
    ]
    for row in manifest["voices"]:
        filename = row["filename"]
        rows.append(
            {
                "id": row["id"],
                "voice": row["name"],
                "name": row["name"],
                "label": row.get("label") or row["name"],
                "locale": row.get("locale"),
                "gender": row.get("gender"),
                "language": "en",
                "present": _voice_file_ok(layout.voices_dir / filename, default=False),
                "official": True,
            }
        )
    present = sum(1 for row in rows if row["present"])
    return {
        "engine": "phonon",
        "repo": manifest.get("repo"),
        "revision": manifest.get("revision"),
        "count": len(rows),
        "presentCount": present,
        "voices": rows,
        "note": "只列出清单里的 default 和 37 个英语音色。没有下载地址，请求不能提交路径。",
    }


def _voice_file_ok(path: Path, default: bool) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if default:
        return True
    return path.stat().st_size == EMBEDDING_BYTES


def synthesis_argv(layout: Layout, text: str, voice: object, output: Path) -> list[str]:
    """Build the fixed CPU q8 command. The request cannot change the binary or model."""
    spoken = validate_text(text)
    voice_id, _name, voice_file = resolve_voice(layout, voice)
    binary = layout.binary
    if binary.name != "ptts" or is_windows_executable(binary):
        raise RuntimeError_("只运行官方 Linux 可执行文件 ptts，不运行 ptts.exe。", "windows_runtime")
    output_ok = _inside(output, layout.cache_dir)
    model_dir = _inside(layout.model_dir, layout.model_dir)
    voice_ok = _inside(voice_file, layout.model_dir if voice_id == "default" else layout.voices_dir)
    catalog = _inside(layout.voice_catalog, layout.voice_catalog.parent)
    if not voice_ok.is_file():
        raise RuntimeError_(f"本地音色文件不存在：{voice_ok.name}", "voice_file_missing")
    return [
        str(binary.resolve()),
        "--model",
        str(model_dir),
        "--lang",
        "en",
        "--quant",
        "q8",
        "--device",
        "cpu",
        "--threads",
        str(layout.threads),
        "--weights",
        "model.q8.gguf",
        "--voice",
        str(voice_ok),
        "--voice-catalog",
        str(catalog),
        "-o",
        str(output_ok),
        "--",
        spoken,
    ]


def worker_env(layout: Layout, base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    for key in list(env):
        if key.upper() in {
            "HF_TOKEN",
            "HUGGING_FACE_HUB_TOKEN",
            "HUGGINGFACE_HUB_TOKEN",
            "HF_HUB_TOKEN",
        }:
            del env[key]
    cache = layout.cache_dir
    env["HF_HOME"] = str(cache)
    env["HF_HUB_OFFLINE"] = "1"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["TEMP"] = str(cache)
    env["TMP"] = str(cache)
    return env


def readiness(layout: Layout | None = None) -> dict:
    """Report files that are actually on disk. Does not run synthesis."""
    layout = layout or layout_from_env()
    binary = layout.binary
    windows = is_windows_executable(binary) if binary.exists() else binary.name.lower().endswith(".exe")
    authentic = False
    binary_error = None
    if windows:
        binary_error = "这是 Windows 可执行文件，Linux 上不会运行。"
    elif binary.is_file():
        digest = sha256_file(binary)
        authentic = digest == BINARY_SHA256 and binary.stat().st_size == BINARY_BYTES
        if not authentic:
            binary_error = "ptts 的 SHA256 与官方 0.7.0 Linux 压缩包里的可执行文件不一致。"
    else:
        binary_error = "还没有官方 Linux ptts。不会用 Windows 的 ptts.exe 代替。"
    model_files = {
        name: (layout.model_dir / name).is_file() and (layout.model_dir / name).stat().st_size > 0
        for name in MODEL_FILENAMES
    }
    voice_rows = []
    missing = []
    try:
        index = layout.voice_index()
    except RuntimeError_ as exc:
        index = {}
        binary_error = binary_error or exc.message
    seen: set[Path] = set()
    for voice_id, name, path in index.values():
        if path in seen:
            continue
        seen.add(path)
        present = path.is_file()
        size_ok = present and path.stat().st_size > 0 and (
            voice_id == "default" or path.stat().st_size == EMBEDDING_BYTES
        )
        if not present or not size_ok:
            missing.append(name)
        voice_rows.append({"id": voice_id, "name": name, "present": present, "sizeOk": size_ok})
    model_ready = all(model_files.values())
    return {
        "engine": "phonon",
        "versionExpected": VERSION,
        "runtimePresent": binary.is_file() and not windows,
        "runtimeAuthentic": authentic,
        "runtimeError": binary_error,
        "executed": False,
        "inferenceReady": False,
        "modelReady": model_ready,
        "modelRevision": MODEL_REVISION,
        "modelFiles": model_files,
        "voiceCatalogRevision": VOICE_CATALOG_REVISION,
        "voiceCountExpected": EXPECTED_CATALOG_VOICES + 1,
        "voicesPresent": sum(1 for row in voice_rows if row["present"] and row["sizeOk"]),
        "missingVoices": missing,
        "offline": True,
        "device": "cpu",
        "quant": "q8",
        "threads": layout.threads,
    }


def probe_version(layout: Layout) -> str:
    """Run ``ptts --version`` only when the file matches the pinned binary."""
    report = readiness(layout)
    if not report["runtimeAuthentic"]:
        raise RuntimeError_(report["runtimeError"] or "运行时未就绪。", "runtime_not_authentic")
    completed = subprocess.run(
        [str(layout.binary), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=worker_env(layout),
    )
    if completed.returncode != 0:
        raise RuntimeError_(completed.stderr.strip()[:300] or "ptts --version 失败。", "version_failed")
    text = completed.stdout.strip()
    if text != f"ptts {VERSION}":
        raise RuntimeError_(f"版本输出是 {text!r}，不是 ptts {VERSION}。", "version_mismatch")
    return text
