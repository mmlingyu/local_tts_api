"""Worker environment and recovery. No model download."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "piper-zh-service"))

from pocket_local.bridge import PocketBridge, worker_env
from pocket_local.catalog import BUILTIN_VOICES


def test_worker_env_keeps_system_paths_and_drops_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEMROOT", r"C:\Windows")
    monkeypatch.setenv("PATH", r"C:\Windows\System32")
    monkeypatch.setenv("TEMP", r"C:\Temp")
    monkeypatch.setenv("TMP", r"C:\Temp")
    monkeypatch.setenv("HF_TOKEN", "should-not-pass")
    monkeypatch.setenv("HUGGING_FACE_HUB_TOKEN", "should-not-pass")
    monkeypatch.setenv("HF_HOME", r"D:\piper-cache")
    monkeypatch.setenv("HF_HUB_CACHE", r"D:\piper-hub")
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    env = worker_env(Path("/tmp/pocket-ready.json"))
    assert env["SYSTEMROOT"] == r"C:\Windows"
    assert env["PATH"] == r"C:\Windows\System32"
    assert env["TEMP"] == r"C:\Temp"
    assert env["TMP"] == r"C:\Temp"
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["HF_HOME"].endswith("models/hf-home") or env["HF_HOME"].endswith("models\\hf-home")
    assert env["POCKET_READY"].endswith("pocket-ready.json")
    assert "HF_TOKEN" not in env
    assert "HUGGING_FACE_HUB_TOKEN" not in env
    assert "HF_HUB_CACHE" not in env
    assert all("should-not-pass" not in value for value in env.values())
    assert r"D:\piper-cache" not in env["HF_HOME"]


def test_failed_worker_is_discarded_and_the_next_request_starts_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SYSTEMROOT", r"C:\Windows")
    monkeypatch.setenv("PATH", r"C:\Windows\System32")
    monkeypatch.setenv("TEMP", r"C:\Temp")
    monkeypatch.setenv("HF_TOKEN", "should-not-pass")
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    seen: list[dict[str, str]] = []
    real = subprocess.Popen

    def spy(*args, **kwargs):
        seen.append(kwargs.get("env") or {})
        return real(*args, **kwargs)

    monkeypatch.setattr("pocket_local.bridge.subprocess.Popen", spy)
    marker = tmp_path / "ready.json"
    marker.write_text(
        json.dumps(
            {
                "markerVersion": 3,
                "variant": "english_18m_2026-10",
                "modelPrepared": True,
                "voices": list(BUILTIN_VOICES),
                "sampleRate": 24000,
            }
        ),
        encoding="utf-8",
    )
    bridge = PocketBridge(program=Path(sys.executable), ready_path=marker)
    from piper_zh.catalog import RequestError

    try:
        with pytest.raises(RequestError) as first:
            bridge.synthesize("Hello.", "english", "alba", "english_18m_2026-10")
        assert first.value.status == 500
        assert first.value.code == "worker_failed"
        assert "initialized once" not in first.value.message
        status = bridge.status()
        assert status["prepared"] is True
        assert status["modelReady"] is True
        assert status["voicesComplete"] is True
        assert status["loaded"] is False
        assert status["inferenceReady"] is False
        assert status["code"] == "inference_failed"
        assert status["lastError"]
        with pytest.raises(RequestError) as second:
            bridge.synthesize("Hello.", "english", "alba", "english_18m_2026-10")
        assert second.value.code == "worker_failed"
        assert "initialized once" not in second.value.message
    finally:
        bridge.close()
    assert len(seen) == 2
    env = seen[0]
    assert env["SYSTEMROOT"] == r"C:\Windows"
    assert "System32" in env["PATH"]
    assert env["TEMP"] == r"C:\Temp"
    assert env["HF_HUB_OFFLINE"] == "1"
    assert "hf-home" in env["HF_HOME"]
    assert "HF_TOKEN" not in env
    assert all("should-not-pass" not in value for value in env.values())


def test_missing_voice_does_not_start_a_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[object] = []
    real = subprocess.Popen

    def spy(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr("pocket_local.bridge.subprocess.Popen", spy)
    marker = tmp_path / "ready.json"
    marker.write_text(
        '{"markerVersion":2,"variant":"english_18m_2026-10","voice":"alba","sampleRate":24000}',
        encoding="utf-8",
    )
    bridge = PocketBridge(program=Path(sys.executable), ready_path=marker)
    from piper_zh.catalog import RequestError

    with pytest.raises(RequestError) as caught:
        bridge.synthesize("Hello.", "english", "marius", "english_18m_2026-10")
    assert caught.value.status == 503
    assert caught.value.code == "voices_incomplete"
    assert calls == []
    status = bridge.status()
    assert status["prepared"] is True
    assert status["voicesComplete"] is False
    assert status["inferenceReady"] is False
    assert "alba" in status["preparedVoices"]
    assert "marius" in status["missingVoices"]
