"""WAV structure for the newly selected gendered voices. Not a listening test."""

from __future__ import annotations

import wave
from io import BytesIO

import pytest

from piper_zh.catalog import BY_ID
from piper_zh.engine import VoicePool

CASES = (
    ("zh_CN-xiao_ya-medium", "你好。", None, "pinyin"),
    ("en_US-ljspeech-medium", "Hello.", None, "espeak"),
    ("en_US-norman-medium", "Hello.", None, "espeak"),
    ("ja_JP-hi_fi_captain-medium", "こんにちは。", 0, "japanese"),
    ("ja_JP-hi_fi_captain-medium", "こんにちは。", 1, "japanese"),
)


@pytest.fixture(scope="module")
def pool():
    missing = sorted({voice for voice, _text, _speaker, _phoneme in CASES if not BY_ID[voice].downloaded()})
    if missing:
        pytest.skip("missing voices: " + ", ".join(missing))
    return VoicePool(device="cpu", cache_limit=2)


def test_gendered_voices_match_their_frontend(pool):
    import piper.phonemize_chinese as chinese

    original = chinese.ChinesePhonemizer
    try:
        for voice, text, speaker, phoneme in CASES:
            if phoneme == "pinyin":
                chinese.ChinesePhonemizer = original
            else:
                class Guard:
                    def __init__(self, *args, **kwargs):
                        raise AssertionError("这个音色不应该调用 g2pW")

                chinese.ChinesePhonemizer = Guard
            result = pool.synthesize(text, voice=voice, speaker=speaker)
            assert result.model_id == voice
            assert result.phoneme_type == phoneme
            assert result.sample_rate == 22050
            if phoneme == "pinyin":
                engine = pool._engines[voice]
                assert getattr(engine._voice, "_chinese_phonemizer", None) is not None
            with wave.open(BytesIO(result.wav), "rb") as wav_file:
                assert wav_file.getnchannels() == 1
                assert wav_file.getsampwidth() == 2
                assert wav_file.getframerate() == 22050
                assert wav_file.getnframes() > 0
            assert result.duration_seconds > 0
    finally:
        chinese.ChinesePhonemizer = original
