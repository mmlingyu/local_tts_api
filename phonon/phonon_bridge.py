"""One Phonon request, one ptts process, then the process is gone.

The bridge never fabricates WAV bytes. A missing runtime or checkpoint
becomes an error. Weights are not kept in this Python process.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from pathlib import Path

from linux_runtime import (
    Layout,
    RuntimeError_,
    layout_from_env,
    public_voices,
    readiness,
    resolve_voice,
    synthesis_argv,
    worker_env,
)


class PhononBridge:
    def __init__(self, layout: Layout | None = None) -> None:
        self.layout = layout or layout_from_env()
        self._last_ok = False
        self._last_error: str | None = None

    def close(self) -> None:
        """Phonon is not kept resident. close() exists so the server can switch engines."""
        return None

    def status(self) -> dict:
        report = readiness(self.layout)
        report["lastSynthesisOk"] = self._last_ok
        report["resident"] = False
        report["inferenceReady"] = False
        report["lifecycle"] = "per-request-process"
        report["lastError"] = self._last_error
        report["readinessNote"] = (
            "modelReady 只表示四个模型文件都在。"
            "runtimeAuthentic 只表示 ptts 的 SHA256 与官方 0.7.0 Linux 可执行文件一致。"
            "inferenceReady 保持 false：进程不常驻，不能把文件在磁盘上说成正在推理。"
        )
        return report

    def voices(self) -> dict:
        payload = public_voices(self.layout)
        info = self.status()
        payload["modelReady"] = info["modelReady"]
        payload["runtimeAuthentic"] = info["runtimeAuthentic"]
        payload["runtimeError"] = info["runtimeError"]
        payload["inferenceReady"] = False
        return payload

    def synthesize(self, text: str, voice: str):
        from piper_zh.catalog import RequestError
        from piper_zh.engine import Synthesis, wav_duration

        report = self.status()
        if not report["runtimeAuthentic"]:
            self._last_ok = False
            self._last_error = report["runtimeError"]
            raise RequestError(report["runtimeError"] or "Phonon 运行时未就绪。", 503, "runtime_not_ready")
        if not report["modelReady"]:
            missing = [name for name, ok in report["modelFiles"].items() if not ok]
            self._last_ok = False
            message = "Phonon 模型文件不齐：" + ", ".join(missing) + "。不会下载，也不会运行 ptts.exe。"
            self._last_error = message
            raise RequestError(message, 503, "model_missing")
        cache = self.layout.cache_dir
        cache.mkdir(parents=True, exist_ok=True)
        output = cache / f"phonon-{uuid.uuid4().hex}.wav"
        try:
            argv = synthesis_argv(self.layout, text, voice, output)
        except RuntimeError_ as exc:
            self._last_ok = False
            self._last_error = exc.message
            status = 503 if exc.code == "voice_file_missing" else 400
            raise RequestError(exc.message, status, exc.code) from exc
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                argv,
                cwd=cache,
                env=worker_env(self.layout),
                capture_output=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self._last_ok = False
            self._last_error = "timeout"
            output.unlink(missing_ok=True)
            raise RequestError("Phonon 超过 120 秒，已结束进程。", 504, "timeout") from exc
        elapsed = time.perf_counter() - started
        try:
            if completed.returncode != 0 or not output.is_file():
                err = (completed.stderr or b"").decode("utf-8", errors="replace").strip()[-500:]
                self._last_ok = False
                self._last_error = err or "no wav"
                raise RequestError(err or "Phonon 没有写出 WAV。", 500, "synth_failed")
            blob = output.read_bytes()
            try:
                rate, duration, peak = wav_duration(blob)
            except (OSError, ValueError) as exc:
                self._last_ok = False
                self._last_error = str(exc)
                raise RequestError(f"Phonon WAV 不合格：{exc}", 500, "bad_wav") from exc
        finally:
            output.unlink(missing_ok=True)
        voice_id, voice_name, _path = resolve_voice(self.layout, voice)
        self._last_ok = True
        self._last_error = None
        return Synthesis(
            wav=blob,
            sample_rate=rate,
            duration_seconds=duration,
            synth_seconds=elapsed,
            phoneme_type="phonon",
            model_id="phonon-31m-en",
            language="en",
            speaker_id=None,
            engine_header="Phonon-English",
            voice_name=voice_name,
            voice_id=voice_id,
            peak=peak,
        )
