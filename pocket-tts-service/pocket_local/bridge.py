"""Start the Pocket worker as a child process. No listening port and no torch import."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

from .catalog import (
    DEFAULT_PARAMETERS,
    DEFAULT_VARIANT,
    PUBLISHED_SAMPLE_RATE,
    languages,
    not_ready_reason,
    ready_is_current,
    voices,
)

ROOT = Path(__file__).resolve().parents[1]
READY_MARKER = ROOT / "models" / "ready.json"


def python_path() -> Path | None:
    if sys.platform == "win32":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else None


class PocketBridge:
    def __init__(self, program: Path | None = None, ready_path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._program = program
        self._ready_path = ready_path or READY_MARKER

    def _interpreter(self) -> Path | None:
        if self._program is not None:
            return self._program if self._program.is_file() else None
        return python_path()

    def _ready_data(self) -> dict | None:
        if not self._ready_path.is_file():
            return None
        try:
            data = json.loads(self._ready_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"variant": None}
        return data if isinstance(data, dict) else {"variant": None}

    def _readiness(self) -> tuple[bool, str | None]:
        program = self._interpreter()
        ready = self._ready_data()
        return program is not None and ready_is_current(ready), not_ready_reason(program is not None, ready)

    def status(self) -> dict:
        program = self._interpreter()
        ready = self._ready_data()
        current, reason = self._readiness()
        return {
            "installed": program is not None,
            "python": str(program) if program else None,
            "prepared": current,
            "preparedVariant": None if ready is None else ready.get("variant"),
            "loaded": self._proc is not None and self._proc.poll() is None,
            "modelReady": current,
            "code": None if current else "model_not_ready",
            "reason": reason,
            "variant": DEFAULT_VARIANT,
            "parameters": DEFAULT_PARAMETERS,
            "gated": True,
            "gateUrl": "https://huggingface.co/kyutai/pocket-tts",
            "languages": [item["language"] for item in languages()],
            "defaultVoice": "alba",
            "defaultLanguage": "english",
            "sampleRate": PUBLISHED_SAMPLE_RATE,
            "sampleRateSource": "pocket_tts/config/english_18m_2026-10.yaml mimi.sample_rate",
            "package": "pocket-tts==4.0.1",
            "unsupported": ["zh", "ja", "ko"],
            "notEnabled": ["english", "english_7m_2026-10", "english_2m_2026-10"],
        }

    def voices(self) -> dict:
        current, reason = self._readiness()
        return {
            "engine": "pocket",
            "voices": voices(),
            "languages": languages(),
            "variant": DEFAULT_VARIANT,
            "modelReady": current,
            "code": None if current else "model_not_ready",
            "reason": reason,
        }

    def _not_ready(self, message: str):
        from piper_zh.catalog import RequestError

        raise RequestError(message, 503, "model_not_ready")

    def synthesize(self, text: str, language: str, voice: str, variant: str):
        program = self._interpreter()
        reason = not_ready_reason(program is not None, self._ready_data())
        if program is None:
            self._not_ready(reason or "Pocket 虚拟环境还没装。")
        if variant != DEFAULT_VARIANT:
            self._not_ready("worker 只加载 english_18m_2026-10。")
        from piper_zh.engine import Synthesis
        import time

        started = time.perf_counter()
        payload = self._request(
            {"cmd": "tts", "text": text, "language": language, "voice": voice, "variant": variant}
        )
        wav = bytes.fromhex(payload["wav_hex"])
        elapsed = time.perf_counter() - started
        rate = int(payload["sample_rate"])
        frames = int(payload["frames"])
        return Synthesis(
            wav=wav,
            sample_rate=rate,
            duration_seconds=frames / rate if rate else 0,
            synth_seconds=elapsed,
            phoneme_type="pocket",
            model_id=variant,
            language=language,
            speaker_id=None,
            engine_header="Pocket-TTS",
            voice_name=voice,
        )

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return
        if proc.stdin:
            proc.stdin.close()
        proc.kill()

    def _request(self, message: dict) -> dict:
        with self._lock:
            proc = self._ensure()
            assert proc.stdin and proc.stdout
            proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            proc.stdin.flush()
            line = proc.stdout.readline()
        if not line:
            self.close()
            raise RuntimeError("Pocket worker 没有返回结果。")
        payload = json.loads(line.decode("utf-8"))
        if not payload.get("ok"):
            from piper_zh.catalog import RequestError

            code = payload.get("code") or "pocket_failed"
            status = 503 if code == "model_not_ready" else 500
            raise RequestError(payload.get("error") or "Pocket worker 失败。", status, code)
        return payload

    def _ensure(self) -> subprocess.Popen:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        program = self._interpreter()
        if program is None:
            self._not_ready("Pocket 虚拟环境还没装。")
        self._proc = subprocess.Popen(
            [str(program), "-m", "pocket_local.worker"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                "PYTHONPATH": str(ROOT),
                "HF_HOME": str(ROOT / "models" / "hf-home"),
                "HF_HUB_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "POCKET_READY": str(self._ready_path),
            },
        )
        return self._proc
