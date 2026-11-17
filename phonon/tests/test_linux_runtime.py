"""Checks for the pinned Linux ptts runtime. These tests do not synthesize speech."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from linux_runtime import (  # noqa: E402
    ARCHIVE_NAME,
    ARCHIVE_SHA256,
    BINARY_SHA256,
    EMBEDDING_BYTES,
    MANIFEST_PATH,
    SUMS_PATH,
    Layout,
    RuntimeError_,
    cpu_flags_supported,
    glibc_supported,
    is_windows_executable,
    official_archive_digest,
    probe_version,
    readiness,
    synthesis_argv,
    validate_text,
    verify_bytes,
)


def test_upstream_sums_match_the_pinned_linux_archive():
    text = SUMS_PATH.read_text(encoding="utf-8")
    assert official_archive_digest(text) == ARCHIVE_SHA256
    assert f"{ARCHIVE_SHA256}  {ARCHIVE_NAME}" in text
    assert "ptts-0.7.0-x86_64-pc-windows-msvc.zip" in text


def test_cpu_and_glibc_requirements():
    assert glibc_supported((2, 39))
    assert glibc_supported((2, 35))
    assert not glibc_supported((2, 34))
    assert not glibc_supported(None)
    assert cpu_flags_supported({"avx2", "fma", "f16c", "sse2"})
    assert not cpu_flags_supported({"avx2", "sse2"})


def test_http_request_accepts_zoey_and_rejects_chinese():
    from linux_runtime import parse_http_request

    text, voice_id, name = parse_http_request({"text": "Hello.", "voice": "Zoey", "language": "en"})
    assert text == "Hello."
    assert name == "Zoey"
    assert voice_id == "NbpkqMVS3CJeq2j8"
    with pytest.raises(RuntimeError_) as caught:
        parse_http_request({"text": "你好。", "voice": "Zoey"})
    assert caught.value.code == "han_text"
    with pytest.raises(RuntimeError_) as caught:
        parse_http_request({"text": "Hello.", "language": "fr", "voice": "Zoey"})
    assert caught.value.code == "unsupported_language"


def test_text_and_voice_reject_paths_and_chinese():
    with pytest.raises(RuntimeError_) as caught:
        validate_text("你好")
    assert caught.value.code == "han_text"
    layout = Layout(
        binary=Path("ptts"),
        model_dir=Path("models"),
        voices_dir=Path("voices"),
        voice_catalog=Path("voices/voices.jsonl"),
        cache_dir=Path("cache"),
    )
    for voice in ("../x", "hf://gradium/phonon-voices", r"C:\voice.safetensors", "https://example.invalid/a"):
        with pytest.raises(RuntimeError_) as caught:
            from linux_runtime import resolve_voice

            resolve_voice(layout, voice)
        assert caught.value.code == "bad_voice"


def test_catalog_is_the_37_english_embeddings():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert len(manifest["voices"]) == 37
    assert sum(row["bytes"] for row in manifest["voices"]) == 9_477_032
    jsonl = [json.loads(line) for line in (MANIFEST_PATH.parent / "voices.jsonl").read_text().splitlines() if line]
    assert len(jsonl) == 102
    assert sum(1 for row in jsonl if row["language"] == "en") == 37


def test_argv_is_fixed_cpu_and_refuses_windows_exe(tmp_path: Path):
    voices = tmp_path / "voices"
    voices.mkdir()
    model = tmp_path / "model"
    model.mkdir()
    cache = tmp_path / "cache"
    cache.mkdir()
    voice = voices / "NbpkqMVS3CJeq2j8.safetensors"
    voice.write_bytes(b"\x00" * EMBEDDING_BYTES)
    binary = tmp_path / "ptts"
    binary.write_bytes(b"not a real runtime")
    layout = Layout(
        binary=binary,
        model_dir=model,
        voices_dir=voices,
        voice_catalog=MANIFEST_PATH.parent / "voices.jsonl",
        cache_dir=cache,
        threads=2,
    )
    argv = synthesis_argv(layout, "Hello.", "Zoey", cache / "out.wav")
    assert argv[0].endswith("/ptts")
    assert "--device" in argv and argv[argv.index("--device") + 1] == "cpu"
    assert argv[argv.index("--quant") + 1] == "q8"
    assert argv[argv.index("--weights") + 1] == "model.q8.gguf"
    assert "hf://" not in " ".join(argv)
    assert "--" in argv
    assert argv[argv.index("--") + 1] == "Hello."
    exe = tmp_path / "ptts.exe"
    exe.write_bytes(b"MZ")
    refused = Layout(
        binary=exe,
        model_dir=model,
        voices_dir=voices,
        voice_catalog=layout.voice_catalog,
        cache_dir=cache,
    )
    with pytest.raises(RuntimeError_) as caught:
        synthesis_argv(refused, "Hello.", "Zoey", cache / "out.wav")
    assert caught.value.code == "windows_runtime"
    assert is_windows_executable(exe)


def test_missing_runtime_is_not_reported_as_ready(tmp_path: Path):
    layout = Layout(
        binary=tmp_path / "ptts",
        model_dir=tmp_path / "model",
        voices_dir=tmp_path / "voices",
        voice_catalog=MANIFEST_PATH.parent / "voices.jsonl",
        cache_dir=tmp_path / "cache",
    )
    report = readiness(layout)
    assert report["runtimePresent"] is False
    assert report["runtimeAuthentic"] is False
    assert report["inferenceReady"] is False
    assert report["executed"] is False
    assert report["modelReady"] is False
    with pytest.raises(RuntimeError_) as caught:
        probe_version(layout)
    assert caught.value.code == "runtime_not_authentic"


def test_checksum_mismatch_does_not_count_as_the_official_binary(tmp_path: Path):
    archive = tmp_path / "archive.tar.gz"
    archive.write_bytes(b"not the release")
    with pytest.raises(RuntimeError_) as caught:
        verify_bytes(archive, ARCHIVE_SHA256, 12)
    assert caught.value.code in {"checksum_mismatch", "size_mismatch"}
    binary = tmp_path / "ptts"
    binary.write_bytes(b"MZ-not-really-but-short")
    layout = Layout(
        binary=binary,
        model_dir=tmp_path / "model",
        voices_dir=tmp_path / "voices",
        voice_catalog=MANIFEST_PATH.parent / "voices.jsonl",
        cache_dir=tmp_path / "cache",
    )
    report = readiness(layout)
    assert report["runtimeAuthentic"] is False
    assert report["inferenceReady"] is False


def test_real_binary_version_when_present():
    raw = os.environ.get("PTTS_BIN")
    if not raw:
        pytest.skip("PTTS_BIN is not set")
    binary = Path(raw)
    assert verify_bytes(binary, BINARY_SHA256, 30_323_496) == BINARY_SHA256
    layout = Layout(
        binary=binary,
        model_dir=Path("models/phonon-31m-en"),
        voices_dir=Path("voices"),
        voice_catalog=Path("voices/voices.jsonl"),
        cache_dir=Path("cache"),
    )
    assert probe_version(layout) == "ptts 0.7.0"
    report = readiness(layout)
    assert report["runtimeAuthentic"] is True
    assert report["inferenceReady"] is False
    assert report["modelReady"] is False
