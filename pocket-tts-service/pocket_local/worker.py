"""Pocket TTS worker. The parent process starts it; it does not listen on a port."""

from __future__ import annotations

import json
import os
import sys
import wave
from io import BytesIO
from pathlib import Path

from pocket_local.catalog import (
    DEFAULT_VARIANT,
    PocketRequestError,
    not_ready_reason,
    parse_pocket,
    prepared_voice_names,
    voice_gap,
)


def _pcm16(audio) -> tuple[bytes, int]:
    import numpy as np

    array = audio.detach().cpu().numpy().reshape(-1)
    if array.dtype != np.int16:
        array = np.clip(array, -1.0, 1.0)
        array = (array * 32767.0).astype(np.int16)
    return array.tobytes(), int(array.shape[0])


def _wav(pcm: bytes, rate: int) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


def _ready_data() -> dict | None:
    path = Path(os.environ.get("POCKET_READY", ""))
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"variant": None}
    return data if isinstance(data, dict) else {"variant": None}


def _emit(body: dict) -> None:
    sys.stdout.write(json.dumps(body) + "\n")
    sys.stdout.flush()


def main() -> int:
    model = None
    loaded = None
    cached_voice = None
    cached_state = None
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            _emit({"ok": False, "code": "bad_request", "error": "worker 收到的不是 JSON。"})
            continue
        try:
            text, language, voice, variant = parse_pocket(
                {
                    "text": message.get("text", ""),
                    "language": message.get("language", "english"),
                    "voice": message.get("voice", "alba"),
                    "variant": message.get("variant", DEFAULT_VARIANT),
                    "engine": "pocket",
                }
            )
        except PocketRequestError as exc:
            _emit({"ok": False, "code": exc.code, "error": exc.message})
            continue
        if variant != DEFAULT_VARIANT:
            _emit({"ok": False, "code": "worker_failed", "error": "只加载 english_18m_2026-10。"})
            return 3
        data = _ready_data()
        reason = not_ready_reason(True, data)
        if reason:
            _emit({"ok": False, "code": "model_not_ready", "error": reason})
            continue
        if voice not in prepared_voice_names(data):
            code, message = voice_gap(data, voice) or ("voices_incomplete", "音色未准备。")
            _emit({"ok": False, "code": code, "error": message})
            continue
        try:
            from pocket_tts import TTSModel

            if model is None or loaded != variant:
                model = TTSModel.load_model(language=variant)
                loaded = variant
                cached_voice = None
                cached_state = None
            if cached_voice != voice:
                cached_state = model.get_state_for_audio_prompt(voice)
                cached_voice = voice
            audio = model.generate_audio(cached_state, text)
            pcm, frames = _pcm16(audio)
            rate = int(model.sample_rate)
            if frames <= 0 or rate <= 0:
                raise RuntimeError("Pocket 没有返回音频。")
            _emit(
                {
                    "ok": True,
                    "wav_hex": _wav(pcm, rate).hex(),
                    "sample_rate": rate,
                    "frames": frames,
                    "voice": voice,
                    "language": language,
                    "variant": variant,
                }
            )
        except Exception as exc:  # noqa: BLE001
            _emit({"ok": False, "code": "worker_failed", "error": str(exc)[:500]})
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
