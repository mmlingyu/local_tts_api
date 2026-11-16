"""Real chaowen + g2pW synthesis. Skipped when the weights are not on disk.

Passing assertions use the standard Mandarin reading. A mismatch is an engine
error and fails the test. Observed wrong output is not rewritten into the
expected value, and a correct reading is not marked xfail.
"""

from __future__ import annotations

import wave
from io import BytesIO

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


def _count_syllable(tokens: list[str], initial: str, final: str, tone: str) -> int:
    needle = [initial, final, tone]
    return sum(1 for index in range(len(tokens) - 2) if tokens[index : index + 3] == needle)


def _require(tokens: list[str], text: str, syllable: tuple[str, str, str], count: int = 1) -> None:
    found = _count_syllable(tokens, *syllable)
    if found != count:
        syllable_text = "".join(syllable)
        pytest.fail(f"{text} 应含 {count} 次 {syllable_text}，实际 {found} 次。音素：{tokens}")


def test_bank_and_chongqing_readings(engine: PiperEngine):
    bank = _tokens(engine, "一家银行。")
    _require(bank, "一家银行。", ("y", "in", "2"))
    _require(bank, "一家银行。", ("h", "ang", "2"))
    assert _count_syllable(bank, "x", "ing", "2") == 0

    sentence = _tokens(engine, "银行行长到了重庆。")
    # 银行 and 行长 are both háng; 长 is zhǎng; 重庆 is chóng qìng.
    _require(sentence, "银行行长到了重庆。", ("h", "ang", "2"), 2)
    _require(sentence, "银行行长到了重庆。", ("zh", "ang", "3"))
    _require(sentence, "银行行长到了重庆。", ("ch", "ong", "2"))
    _require(sentence, "银行行长到了重庆。", ("q", "ing", "4"))
    assert _count_syllable(sentence, "x", "ing", "2") == 0
    assert _count_syllable(sentence, "ch", "ang", "2") == 0

    compound = _tokens(engine, "银行的行长。")
    _require(compound, "银行的行长。", ("h", "ang", "2"), 2)
    _require(compound, "银行的行长。", ("zh", "ang", "3"))
    assert _count_syllable(compound, "x", "ing", "2") == 0


def test_zhewei_hangzhang_engine_reading(engine: PiperEngine):
    """行长 is háng zhǎng. xíng here is an engine error, not the expected reading."""
    text = "这位行长。"
    tokens = _tokens(engine, text)
    if _count_syllable(tokens, "x", "ing", "2") or _count_syllable(tokens, "h", "ang", "2") != 1:
        pytest.fail(
            "引擎读音错误：这位行长的「行」应读 háng（hang2），与「银行行长」相同，"
            f"不是 xíng。实际音素：{tokens}"
        )
    _require(tokens, text, ("zh", "ang", "3"))
    assert _count_syllable(tokens, "ch", "ang", "2") == 0


def test_other_polyphones(engine: PiperEngine):
    grown = _tokens(engine, "他长大后想长成大人。")
    _require(grown, "他长大后想长成大人。", ("zh", "ang", "3"), 2)
    assert _count_syllable(grown, "ch", "ang", "2") == 0

    music = _tokens(engine, "这首音乐很好听。")
    _require(music, "这首音乐很好听。", ("y", "ue", "4"))
    assert _count_syllable(music, "l", "e", "4") == 0

    repay = _tokens(engine, "钱还没还。")
    _require(repay, "钱还没还。", ("h", "ai", "2"))
    _require(repay, "钱还没还。", ("h", "uan", "2"))

    place = _tokens(engine, "重庆人很重要。")
    _require(place, "重庆人很重要。", ("ch", "ong", "2"))
    _require(place, "重庆人很重要。", ("zh", "ong", "4"))


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
