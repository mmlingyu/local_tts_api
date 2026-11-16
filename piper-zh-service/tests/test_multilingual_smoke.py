"""One real WAV per whitelisted language. Structure only, not a listening review.

Skipped when that voice's files are absent. No timing assertion is recorded.
"""

from __future__ import annotations

import wave
from io import BytesIO

import pytest

from piper_zh.catalog import BY_ID
from piper_zh.engine import VoicePool

CASES = (
    ("zh", "zh_CN-chaowen-medium", "你好。", None),
    ("en", "en_US-joe-medium", "Hello.", None),
    ("fr", "fr_FR-siwis-medium", "Bonjour.", None),
    ("ja", "ja_JP-hi_fi_captain-medium", "こんにちは。", 0),
    ("ko", "ko_KR-kss-medium", "안녕하세요.", None),
)


@pytest.fixture(scope="module")
def pool():
    missing = [voice for _language, voice, _text, _speaker in CASES if not BY_ID[voice].downloaded()]
    if missing:
        pytest.skip("missing voices: " + ", ".join(missing))
    import piper.phonemize_chinese as chinese

    original = chinese.ChinesePhonemizer

    class Guard:
        def __init__(self, *args, **kwargs):
            raise AssertionError("非中文路径调用了 g2pW")

    # The Chinese case runs first, before the guard is installed.
    loaded = VoicePool(device="cpu", cache_limit=2)
    try:
        yield loaded, chinese, original, Guard
    finally:
        chinese.ChinesePhonemizer = original


def test_each_language_returns_a_pcm_wav(pool):
    loaded, chinese, original, guard = pool
    chinese.ChinesePhonemizer = original
    for language, voice, text, speaker in CASES:
        if language != "zh":
            chinese.ChinesePhonemizer = guard
        result = loaded.synthesize(text, language=language, voice=voice, speaker=speaker)
        assert result.language == language
        assert result.model_id == voice
        assert result.phoneme_type == BY_ID[voice].phoneme_type
        assert result.sample_rate == BY_ID[voice].sample_rate
        with wave.open(BytesIO(result.wav), "rb") as wav_file:
            assert wav_file.getnchannels() == 1
            assert wav_file.getsampwidth() == 2
            assert wav_file.getframerate() == BY_ID[voice].sample_rate
            assert wav_file.getnframes() > 0
        # A non-silent WAV is not a pronunciation or listening acceptance.
        assert result.duration_seconds > 0
