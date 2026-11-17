"""Explicit download of the chaowen voice and the g2pW frontend.

Nothing in the HTTP server calls this module. A page click cannot start a download.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import tarfile
import urllib.request
from pathlib import Path

from .catalog import BY_ID, DEFAULT_BY_LANGUAGE, LANGUAGE_ALIASES, VOICES, VoiceSpec
from .engine import DEFAULT_G2P_DIR, DEFAULT_HF_HOME, DEFAULT_MODEL, LICENSE_INFO

ROOT = DEFAULT_MODEL.parent
ONNX_NAME = DEFAULT_MODEL.name
JSON_NAME = ONNX_NAME + ".json"
CARD_NAME = "MODEL_CARD"
ARCHIVE_NAME = "g2pw.tar.gz"

# Sizes and SHA-256 checked against the Hugging Face LFS objects on 2026-11-16.
FILES = {
    ONNX_NAME: {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/chaowen/medium/zh_CN-chaowen-medium.onnx",
        "size": 63_221_984,
        "sha256": "83a5268616ad0aa2d3e2b67158824b5e23b24e0973473ce28859c059457b824e",
    },
    JSON_NAME: {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/chaowen/medium/zh_CN-chaowen-medium.onnx.json",
        "size": 3157,
        "sha256": "57cf9bf947aa74a4e2ba41e5653b80564061c2f2d47525e8aa28c24817c19f75",
    },
    CARD_NAME: {
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/chaowen/medium/MODEL_CARD",
        "size": 472,
        "sha256": "4f9386b738601ccfdcca09ba34deef9b976e60930a010c7d5444716d3cfdb0ef",
    },
    ARCHIVE_NAME: {
        "url": "https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/main/zh/zh_CN/_resources/g2pw.tar.gz?download=true",
        "size": 112_991_734,
        "sha256": "252c6f561c11014fbb243d70aec993a816d82109887b91edcda0261ab9967060",
    },
}

BERT_REPO = "bert-base-chinese"
BERT_FILES = (
    "vocab.txt",
    "tokenizer_config.json",
    "config.json",
    "special_tokens_map.json",
    "tokenizer.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    temporary.replace(destination)


def _ensure_file(name: str) -> Path:
    spec = FILES[name]
    path = ROOT / name
    if path.is_file() and path.stat().st_size == spec["size"] and _sha256(path) == spec["sha256"]:
        print(f"already present {path}")
        return path
    print(f"downloading {name}")
    _download(spec["url"], path)
    actual_size = path.stat().st_size
    actual_hash = _sha256(path)
    if actual_size != spec["size"] or actual_hash != spec["sha256"]:
        path.unlink(missing_ok=True)
        raise RuntimeError(
            f"{name} 校验失败：size {actual_size} sha256 {actual_hash}。"
            "没有保留这个文件。"
        )
    print(f"verified {path} ({actual_size} bytes)")
    return path


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if not (member.isfile() or member.isdir()):
                raise RuntimeError(f"g2pW 压缩包含有不允许的成员：{member.name}")
            target = (destination / member.name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"g2pW 压缩包路径越界：{member.name}")
        try:
            tar.extractall(destination, filter="data")
        except TypeError:
            tar.extractall(destination)
    onnx = destination / "g2pw.onnx"
    if not onnx.is_file() or onnx.stat().st_size < 1_000_000:
        raise RuntimeError(f"解压后没有找到有效的 {onnx}")


def _prefetch_tokenizer(hf_home: Path) -> None:
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "0"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from huggingface_hub import snapshot_download

    snapshot_download(BERT_REPO, allow_patterns=list(BERT_FILES))
    print(f"tokenizer cache ready under {hf_home}")


def _ensure_voice(spec: VoiceSpec) -> None:
    for path, part in spec.files():
        if path.is_file() and path.stat().st_size == part.size and _md5(path) == part.md5:
            print(f"already present {path}")
            continue
        filename = "MODEL_CARD" if part.name == "MODEL_CARD" else part.name
        print(f"downloading {spec.voice_id} {filename}")
        _download(spec.huggingface_url(filename), path)
        if path.stat().st_size != part.size or _md5(path) != part.md5:
            path.unlink(missing_ok=True)
            raise RuntimeError(f"{spec.voice_id} 的 {filename} 与 voices.json 的大小或 MD5 不一致，已删除。")
        print(f"verified {path}")


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _selected(voice: str | None, language: str | None) -> list[VoiceSpec]:
    if voice is None and language is None:
        return [DEFAULT_BY_LANGUAGE["zh"]]
    spec = None
    if voice is not None:
        spec = BY_ID.get(voice.strip())
        if spec is None:
            raise SystemExit(f"拒绝下载白名单以外的音色：{voice}")
    if language is not None:
        key = LANGUAGE_ALIASES.get(language.strip().lower())
        if key is None:
            raise SystemExit(f"没有这个语言的官方白名单音色：{language}")
        chosen = DEFAULT_BY_LANGUAGE[key]
        if spec is not None and spec.language != key:
            raise SystemExit(f"{spec.voice_id} 不属于 {language}")
        spec = spec or chosen
    assert spec is not None
    return [spec]


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download one whitelisted Piper voice. Never downloads every language.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required before any file is fetched. Without it, the command only prints the plan.",
    )
    parser.add_argument("--hf-home", type=Path, default=DEFAULT_HF_HOME)
    parser.add_argument("--voice", help="Whitelist voice id, for example en_US-joe-medium")
    parser.add_argument("--language", help="zh, en, ja, ko, or fr. Downloads that language's default voice only.")
    parser.add_argument("--list", action="store_true", help="Print the whitelist and exit without downloading.")
    args = parser.parse_args(argv)
    if args.list:
        for spec in VOICES:
            print(
                f"{spec.language}\t{spec.voice_id}\t{spec.phoneme_type}\t{spec.dataset_license}\t"
                f"{spec.onnx_size}\tvoices.md={spec.documented_in_voices_md}"
            )
        print("未下载。")
        return 0
    try:
        selected = _selected(args.voice, args.language)
    except SystemExit as exc:
        print(exc)
        return 2
    for spec in selected:
        print(spec.voice_id, spec.dataset_license)
        print(spec.training)
        print(spec.commercial_note)
    print("引擎许可证：", LICENSE_INFO["engine"])
    print("一次只准备上面列出的音色，不会下载全部语言。")
    if not args.confirm:
        print("未下载。确认许可后，再执行同一条命令并加上 --confirm")
        return 2
    for spec in selected:
        spec.directory.mkdir(parents=True, exist_ok=True)
        _ensure_voice(spec)
        if spec.phoneme_type == "pinyin":
            for name in (ONNX_NAME, JSON_NAME, CARD_NAME, ARCHIVE_NAME):
                _ensure_file(name)
            _safe_extract(ROOT / ARCHIVE_NAME, DEFAULT_G2P_DIR)
            _prefetch_tokenizer(args.hf_home.expanduser().resolve())
        elif spec.phoneme_type == "japanese":
            print("日语合成还需要已安装的 pyopenjtalk-plus。这条命令不会改用 g2pW。")
    print("所选资源已处理。页面点击不会触发下载。")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
