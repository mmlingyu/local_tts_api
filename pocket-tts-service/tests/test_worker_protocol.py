"""Talk to the real Pocket worker process. No model download and no torch import."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ask(ready: Path | None) -> dict:
    env = {
        "PYTHONPATH": str(ROOT),
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "POCKET_READY": str(ready or ROOT / "models" / "does-not-exist.json"),
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "pocket_local.worker"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.stdin and proc.stdout and proc.stderr
    try:
        proc.stdin.write(
            json.dumps(
                {
                    "text": "Hello.",
                    "language": "en",
                    "voice": "alba",
                    "variant": "english_18m_2026-10",
                }
            ).encode("utf-8")
            + b"\n"
        )
        proc.stdin.flush()
        line = proc.stdout.readline()
        err = proc.stderr.read() if False else b""
    finally:
        proc.kill()
        err = proc.stderr.read()
    assert line
    payload = json.loads(line.decode("utf-8"))
    assert b"huggingface.co" not in err.lower()
    assert b"pocket_tts" not in err.lower()
    return payload


def test_missing_marker_is_model_not_ready():
    payload = _ask(None)
    assert payload["ok"] is False
    assert payload["code"] == "model_not_ready"
    assert "ready.json" in payload["error"]


def test_old_marker_is_model_not_ready():
    path = Path("/tmp/pocket-protocol-old-ready.json")
    path.write_text('{"languages":["english"]}', encoding="utf-8")
    payload = _ask(path)
    assert payload["ok"] is False
    assert payload["code"] == "model_not_ready"
    assert "english_18m_2026-10" in payload["error"]
