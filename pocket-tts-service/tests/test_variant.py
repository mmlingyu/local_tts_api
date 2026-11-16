from pocket_local.catalog import DEFAULT_VARIANT, parse_pocket, parse_variant, ready_is_current
from pocket_local.catalog import PocketRequestError
import pytest


def test_omitted_variant_is_the_small_model():
    text, language, voice, variant = parse_pocket({"text": "Hello.", "language": "en", "voice": "alba"})
    assert (text, language, voice, variant) == ("Hello.", "english", "alba", DEFAULT_VARIANT)
    assert DEFAULT_VARIANT == "english_18m_2026-10"
    assert parse_variant(None) == DEFAULT_VARIANT


def test_hundred_million_and_smaller_ids_are_not_loaded():
    for variant in ("english", "english_7m_2026-10", "english_2m_2026-10"):
        with pytest.raises(PocketRequestError) as caught:
            parse_pocket({"text": "Hello.", "variant": variant})
        assert caught.value.code == "variant_not_enabled"


def test_old_ready_marker_is_not_current():
    assert ready_is_current({"languages": ["english"], "sampleRate": 24000}) is False
    assert ready_is_current({"markerVersion": 2, "variant": "english", "voice": "alba"}) is False
    assert ready_is_current({"markerVersion": 2, "variant": DEFAULT_VARIANT, "voice": "alba"}) is True
