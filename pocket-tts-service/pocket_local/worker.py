"""Pocket TTS worker. The parent process starts it; it does not listen on a port."""

from __future__ import annotations

import json
import sys
import wave
from io import BytesIO

from pocket_local.catalog import parse_pocket


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


def main() -> int:
    from pocket_tts import TTSModel

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
            text, language, voice = parse_pocket(
                {
                    "text": message.get("text", ""),
                    "language": message.get("language", "english"),
                    "voice": message.get("voice", ""),
                    "engine": "pocket",
                }
            )
            if model is None or loaded != language:
                model = TTSModel.load_model(language=language)
                loaded = language
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
            body = {
                "ok": True,
                "wav_hex": _wav(pcm, rate).hex(),
                "sample_rate": rate,
                "frames": frames,
                "voice": voice,
                "language": language,
            }
        except Exception as exc:  # noqa: BLE001
            body = {"ok": False, "error": str(exc)[:500]}
        sys.stdout.write(json.dumps(body) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
