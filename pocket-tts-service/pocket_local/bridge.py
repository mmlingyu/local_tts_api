"""Start the Pocket worker as a child process. No listening port and no torch import."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from .catalog import (
    BUILTIN_VOICES,
    DEFAULT_PARAMETERS,
    DEFAULT_VARIANT,
    PUBLISHED_SAMPLE_RATE,
    incomplete_reason,
    languages,
    missing_voice_names,
    not_ready_reason,
    prepared_voice_names,
    ready_is_current,
    voice_gap,
    voices,
    voices_complete,
)

# Replaced outright so a Piper HF_HOME or hub cache cannot point this worker
# elsewhere. Tokens are removed so the offline worker neither needs nor logs them.
_DROPPED_ENV = {
    "HF_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
    "HUGGINGFACE_HUB_TOKEN",
    "HF_HUB_TOKEN",
    "HUGGINGFACE_HUB_CACHE",
    "HF_HUB_CACHE",
    "TRANSFORMERS_CACHE",
    "HF_DATASETS_CACHE",
}
_KEEP_WORKER_CODES = {"model_not_ready", "voices_incomplete"}

ROOT = Path(__file__).resolve().parents[1]
READY_MARKER = ROOT / "models" / "ready.json"


def worker_env(ready_path: Path) -> dict[str, str]:
    """Copy the parent environment, then apply only the Pocket overrides."""
    env = os.environ.copy()
    for key in list(env):
        if key.upper() in _DROPPED_ENV:
            del env[key]
    env["PYTHONPATH"] = str(ROOT)
    env["HF_HOME"] = str(ROOT / "models" / "hf-home")
    env["HF_HUB_OFFLINE"] = "1"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["POCKET_READY"] = str(ready_path)
    return env


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
        self._inference_ready = False
        self._last_error: str | None = None

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

    def _classify(self) -> dict:
        program = self._interpreter()
        data = self._ready_data()
        file_ready = program is not None and ready_is_current(data)
        prepared = prepared_voice_names(data) if file_ready else []
        missing = missing_voice_names(data) if file_ready else list(BUILTIN_VOICES)
        complete = file_ready and voices_complete(data)
        alive = self._proc is not None and self._proc.poll() is None
        if not alive:
            self._inference_ready = False
        inference = bool(self._inference_ready and alive)
        if program is None or not ready_is_current(data):
            code = "model_not_ready"
            reason = not_ready_reason(program is not None, data)
        elif not complete:
            code = "voices_incomplete"
            reason = incomplete_reason(data)
            if self._last_error:
                reason += " 另外，上次推理失败，worker 已废弃，不是推理就绪：" + self._last_error
        elif self._last_error:
            code = "inference_failed"
            reason = (
                "上次 Pocket 推理失败，worker 已停掉，下次请求会重新启动。"
                "prepared 只表示 ready.json，不是推理就绪。已有 hf-home 不用重新登录或重下。"
                + self._last_error
            )
        else:
            code = None
            reason = None
        return {
            "installed": program is not None,
            "python": str(program) if program else None,
            "data": data,
            "fileReady": file_ready,
            "preparedVoices": prepared,
            "missingVoices": missing,
            "voicesComplete": complete,
            "inferenceReady": inference,
            "code": code,
            "reason": reason,
        }

    def status(self) -> dict:
        info = self._classify()
        data = info["data"]
        return {
            "installed": info["installed"],
            "python": info["python"],
            "prepared": info["fileReady"],
            "preparedVariant": None if data is None else data.get("variant"),
            "loaded": info["inferenceReady"],
            "inferenceReady": info["inferenceReady"],
            "modelReady": info["fileReady"],
            "voicesComplete": info["voicesComplete"],
            "preparedVoices": info["preparedVoices"],
            "missingVoices": info["missingVoices"],
            "voiceCount": len(BUILTIN_VOICES),
            "code": info["code"],
            "reason": info["reason"],
            "lastError": self._last_error,
            "readinessNote": "prepared 和 modelReady 只表示 ready.json 里的 18.2M 标记。loaded 和 inferenceReady 只在 worker 成功合成过且进程仍在时为 true。失败后两者回到 false。",
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
            "unsupported": ["zh", "ja", "ko", "fr"],
            "notEnabled": ["english", "english_7m_2026-10", "english_2m_2026-10"],
        }

    def voices(self) -> dict:
        info = self._classify()
        prepared = set(info["preparedVoices"])
        rows = []
        for row in voices():
            item = dict(row)
            item["prepared"] = row["voice"] in prepared
            rows.append(item)
        return {
            "engine": "pocket",
            "voices": rows,
            "languages": languages(),
            "variant": DEFAULT_VARIANT,
            "modelReady": info["fileReady"],
            "voicesComplete": info["voicesComplete"],
            "preparedVoices": info["preparedVoices"],
            "missingVoices": info["missingVoices"],
            "inferenceReady": info["inferenceReady"],
            "code": info["code"],
            "reason": info["reason"],
            "readinessNote": "prepared 为 false 的音色还没写入标记。页面不能为此下载。",
        }

    def _not_ready(self, message: str):
        from piper_zh.catalog import RequestError

        raise RequestError(message, 503, "model_not_ready")

    def synthesize(self, text: str, language: str, voice: str, variant: str):
        program = self._interpreter()
        data = self._ready_data()
        reason = not_ready_reason(program is not None, data)
        if program is None or reason:
            self._not_ready(reason or "Pocket 虚拟环境还没装。")
        if variant != DEFAULT_VARIANT:
            self._not_ready("worker 只加载 english_18m_2026-10。")
        gap = voice_gap(data, voice)
        if gap:
            from piper_zh.catalog import RequestError

            raise RequestError(gap[1], 503, gap[0])
        from piper_zh.engine import Synthesis
        import time

        started = time.perf_counter()
        payload = self._request(
            {"cmd": "tts", "text": text, "language": language, "voice": voice, "variant": variant}
        )
        try:
            wav = bytes.fromhex(payload["wav_hex"])
        except ValueError as exc:
            self._discard_worker("worker 返回的音频无法解析。")
            raise RuntimeError("worker 返回的音频无法解析。") from exc
        self._inference_ready = True
        self._last_error = None
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
        if proc is None:
            return
        if proc.poll() is None:
            if proc.stdin:
                proc.stdin.close()
            proc.kill()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

    def _request(self, message: dict) -> dict:
        with self._lock:
            proc = self._ensure()
            assert proc.stdin and proc.stdout
            proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            proc.stdin.flush()
            line = proc.stdout.readline()
        if not line:
            self._discard_worker("Pocket worker 没有返回结果。")
            raise RuntimeError("Pocket worker 没有返回结果。")
        payload = json.loads(line.decode("utf-8"))
        if not payload.get("ok"):
            from piper_zh.catalog import RequestError

            code = payload.get("code") or "worker_failed"
            message = payload.get("error") or "Pocket worker 失败。"
            if code not in _KEEP_WORKER_CODES:
                self._discard_worker(message)
            status = 503 if code in _KEEP_WORKER_CODES else 500
            raise RequestError(message, status, code)
        return payload

    def _discard_worker(self, error: str) -> None:
        self._inference_ready = False
        self._last_error = error[:300]
        self.close()

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
            env=worker_env(self._ready_path),
        )
        return self._proc
