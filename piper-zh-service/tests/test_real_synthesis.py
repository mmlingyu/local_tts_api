"""Real chaowen + g2pW synthesis. Skipped when the weights are not on disk.

This file is not a mock. A passing run means Piper produced a WAV from Chinese text.
"""

from __future__ import annotations

import wave
from io import BytesIO
from pathlib import Path

import pytest

from piper_zh.engine import DEFAULT_G2P_DIR, DEFAULT_MODEL, PiperEngine

pytestmark = pytest.mark.skipif(
    not (DEFAULT_MODEL.is_file() and (DEFAULT_G2P_DIR / "g2pw.onnx").is_file()),
    reason="chaowen onnx or g2pW weights are not downloaded",
)


@pytest.fixture(scope="module")
def engine():
    loaded = PiperEngine(device="cpu")
    loaded.load()
    yield loaded


def _tokens(engine: PiperEngine, text: str) -> list[str]:
    return [token for sentence in engine._voice.phonemize(text) for token in sentence]


def _has_syllable(tokens: list[str], initial: str, final: str, tone: str) -> bool:
    needle = [initial, final, tone]
    return any(tokens[index : index + 3] == needle for index in range(len(tokens) - 2))


def test_g2pw_separates_bank_and_president(engine: PiperEngine):
    bank = _tokens(engine, "一家银行。")
    president = _tokens(engine, "这位行长。")
    assert _has_syllable(bank, "h", "ang", "2")
    assert not _has_syllable(bank, "x", "ing", "2")
    assert _has_syllable(president, "x", "ing", "2")
    assert _has_syllable(president, "zh", "ang", "3")


@pytest.mark.xfail(
    reason="2026-11-16 实测：银行的行长 里第二个行仍被读成 hang2，不是 xing2。这是当前 g2pW 输出，不是听感通过。",
    strict=True,
)
def test_bank_president_compound_is_not_yet_correct(engine: PiperEngine):
    flat = _tokens(engine, "银行的行长。")
    after_particle = flat[flat.index("e") + 2 :]
    assert after_particle[:3] == ["x", "ing", "2"]


def test_http_free_synthesis_writes_audible_wav(engine: PiperEngine):
    result = engine.synthesize("银行行长到了重庆。")
    assert result.sample_rate == 22050
    assert result.duration_seconds > 0.4
    assert result.synth_seconds > 0
    assert result.phoneme_type == "pinyin"
    assert result.model_id == "zh_CN-chaowen-medium"
    with wave.open(BytesIO(result.wav), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 22050
        frames = wav_file.readframes(wav_file.getnframes())
    peak = max(abs(int.from_bytes(frames[index : index + 2], "little", signed=True)) for index in range(0, len(frames), 2))
    assert peak > 100
