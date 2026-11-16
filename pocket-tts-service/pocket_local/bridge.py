"""Start the Pocket worker as a child process. No listening port and no torch import."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

from .catalog import DEFAULT_PARAMETERS, DEFAULT_VARIANT, PUBLISHED_SAMPLE_RATE, languages, ready_is_current, voices

ROOT = Path(__file__).resolve().parents[1]
READY_MARKER = ROOT / "models" / "ready.json"


def python_path() -> Path | None:
    if sys.platform == "win32":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else None


class PocketBridge:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None

    def _ready_data(self) -> dict | None:
        if not READY_MARKER.is_file():
            return None
        try:
            data = json.loads(READY_MARKER.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def status(self) -> dict:
        program = python_path()
        ready = self._ready_data()
        current = ready_is_current(ready)
        return {
            "installed": program is not None,
            "python": str(program) if program else None,
            "prepared": current,
            "preparedVariant": None if ready is None else ready.get("variant"),
            "loaded": self._proc is not None and self._proc.poll() is None,
            "modelReady": program is not None and current,
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
        return {"engine": "pocket", "voices": voices(), "languages": languages()}

    def synthesize(self, text: str, language: str, voice: str, variant: str):
        program = python_path()
        if program is None:
            raise RuntimeError("Pocket 虚拟环境还没装。请在 pocket-tts-service 里运行准备脚本，不要装进 Piper 的虚拟环境。")
        if not READY_MARKER.is_file():
            raise RuntimeError(
                "Pocket 权重还没准备。请在该虚拟环境执行 python -m pocket_local.prepare --confirm。"
                "页面点击不会下载。模型仓库 kyutai/pocket-tts 需要先在 Hugging Face 接受许可。"
            )
        if not ready_is_current(self._ready_data()):
            raise RuntimeError(
                "准备标记不是 english_18m_2026-10。旧的 ready.json 不能沿用。"
                "请重新执行 python -m pocket_local.prepare --confirm --variant english_18m_2026-10。"
            )
        if variant != DEFAULT_VARIANT:
            raise RuntimeError("worker 只加载 english_18m_2026-10。")
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
            raise RuntimeError(payload.get("error") or "Pocket worker 失败。")
        return payload

    def _ensure(self) -> subprocess.Popen:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        program = python_path()
        if program is None:
            raise RuntimeError("Pocket 虚拟环境还没装。")
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
                "POCKET_READY": str(READY_MARKER),
            },
        )
        return self._proc
