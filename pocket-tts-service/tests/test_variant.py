from pathlib import Path

from pocket_local.catalog import (
    BUILTIN_VOICES,
    DEFAULT_VARIANT,
    parse_pocket,
    parse_variant,
    prepared_voice_names,
    ready_is_current,
    ready_record,
    voices_complete,
)
from pocket_local.catalog import PocketRequestError
import pytest


def test_omitted_variant_is_the_small_model():
    text, language, voice, variant = parse_pocket({"text": "Hello.", "language": "en", "voice": "alba"})
    assert (text, language, voice, variant) == ("Hello.", "english", "alba", DEFAULT_VARIANT)
    assert DEFAULT_VARIANT == "english_18m_2026-10"
    assert parse_variant(None) == DEFAULT_VARIANT
    assert len(BUILTIN_VOICES) == 27
    assert len(set(BUILTIN_VOICES)) == 27


def test_hundred_million_and_smaller_ids_are_not_loaded():
    for variant in ("english", "english_7m_2026-10", "english_2m_2026-10"):
        with pytest.raises(PocketRequestError) as caught:
            parse_pocket({"text": "Hello.", "variant": variant})
        assert caught.value.code == "variant_not_enabled"


def test_old_ready_marker_is_not_current():
    assert ready_is_current({"languages": ["english"], "sampleRate": 24000}) is False
    assert ready_is_current({"markerVersion": 2, "variant": "english", "voice": "alba"}) is False
    legacy = {"markerVersion": 2, "variant": DEFAULT_VARIANT, "voice": "alba"}
    assert ready_is_current(legacy) is True
    assert prepared_voice_names(legacy) == ["alba"]
    assert voices_complete(legacy) is False


def test_builtin_voices_are_accepted_and_paths_are_not():
    for name in ("alba", "marius", "daan", "estelle", "giovanni", "juergen", "lola", "rafael"):
        assert name in BUILTIN_VOICES
        parsed = parse_pocket({"text": "Hello.", "language": "en", "voice": name})
        assert parsed[2] == name
        assert parsed[1] == "english"
    with pytest.raises(PocketRequestError) as french:
        parse_pocket({"text": "Bonjour.", "language": "fr", "voice": "estelle"})
    assert french.value.code == "unsupported_language"
    with pytest.raises(PocketRequestError) as missing:
        parse_pocket({"text": "Hello.", "voice": "not_a_voice"})
    assert missing.value.code == "unknown_voice"


def test_compare_page_lists_the_same_builtin_voices():
    page = Path(__file__).resolve().parents[2] / "piper-zh-service" / "static" / "compare-logic.mjs"
    text = page.read_text(encoding="utf-8")
    for name in BUILTIN_VOICES:
        assert f'"{name}"' in text


def test_marker_separates_weights_from_voice_set():
    partial = ready_record(24000, ["alba"])
    assert partial["markerVersion"] == 3
    assert partial["modelPrepared"] is True
    assert voices_complete(partial) is False
    assert "marius" not in partial["voices"]
    full = ready_record(24000, list(BUILTIN_VOICES))
    assert voices_complete(full) is True
    assert ready_is_current({"markerVersion": 3, "variant": DEFAULT_VARIANT, "modelPrepared": False}) is False
