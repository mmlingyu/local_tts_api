"""Builtin Pocket TTS languages and voices.

Names come from pocket-tts 4.0.1 `default_parameters.py` and
`_ORIGINS_OF_PREDEFINED_VOICES`. A request cannot pass a file path, URL, or
`hf://` reference. Chinese, Japanese, and Korean are not in the upstream list.
"""

from __future__ import annotations

MAX_TEXT_CHARS = 500

# Published in pocket_tts/config/english_18m_2026-10.yaml as mimi.sample_rate.
PUBLISHED_SAMPLE_RATE = 24000

# Official small-model id. `language="english"` in pocket-tts is the ~100M model.
DEFAULT_VARIANT = "english_18m_2026-10"
DEFAULT_PARAMETERS = "18.2M"
MARKER_VERSION = 2

# Known upstream ids that this service does not load.
REJECTED_VARIANTS = {
    "english": "这是上游默认的约 100M 模型，不是本次选择的 18.2M。",
    "english_7m_2026-10": "6.9M 官方 ID 存在，但本服务没有启用，也没有测过。",
    "english_2m_2026-10": "1.9M 是实验档，本服务没有启用，也没有测过。",
    "english_18m_refl_2026-10": "带 reward fine-tuning 的 18.2M 变体没有启用。",
}

LANGUAGES = {
    "english": {"voice": "alba", "aliases": ("en", "en_us", "en-us")},
}

# English names are the README entries marked (en). Other languages only have
# the one default voice named by upstream. Gender is not stated in those files.
ENGLISH_VOICES = (
    "alba",
    "anna",
    "azelma",
    "bill_boerst",
    "caro_davy",
    "charles",
    "cosette",
    "eponine",
    "eve",
    "fantine",
    "george",
    "jane",
    "jean",
    "javert",
    "marius",
    "mary",
    "michael",
    "paul",
    "peter_yearsley",
    "stuart_bell",
    "vera",
)

VOICES_BY_LANGUAGE = {
    "english": ("alba",),
}

_ALIAS = {}
for _name, _spec in LANGUAGES.items():
    _ALIAS[_name] = _name
    for _alias in _spec["aliases"]:
        _ALIAS[_alias] = _name

UNSUPPORTED = {
    "zh": "Pocket TTS 官方语言列表没有中文。这次请求不会改用 Piper。",
    "ja": "Pocket TTS 官方语言列表没有日语。这次请求不会改用 Piper。",
    "ko": "Pocket TTS 官方语言列表没有韩语。这次请求不会改用 Piper。",
    "zh_cn": "Pocket TTS 官方语言列表没有中文。这次请求不会改用 Piper。",
    "ja_jp": "Pocket TTS 官方语言列表没有日语。这次请求不会改用 Piper。",
    "ko_kr": "Pocket TTS 官方语言列表没有韩语。这次请求不会改用 Piper。",
}


class PocketRequestError(Exception):
    def __init__(self, message: str, status: int, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def voices() -> list[dict]:
    rows = []
    for language, names in VOICES_BY_LANGUAGE.items():
        for name in names:
            rows.append(
                {
                    "voice": name,
                    "language": language,
                    "variant": DEFAULT_VARIANT,
                    "parameters": DEFAULT_PARAMETERS,
                    "defaultForLanguage": name == LANGUAGES[language]["voice"],
                    "gender": "unknown",
                    "genderSource": "https://github.com/kyutai-labs/pocket-tts/blob/main/README.md",
                    "sampleRate": PUBLISHED_SAMPLE_RATE,
                    "builtin": True,
                }
            )
    return rows


def languages() -> list[dict]:
    return [
        {
            "language": name,
            "defaultVoice": spec["voice"],
            "voices": list(VOICES_BY_LANGUAGE[name]),
            "variant": DEFAULT_VARIANT,
            "parameters": DEFAULT_PARAMETERS,
            "supported": True,
        }
        for name, spec in LANGUAGES.items()
    ]


def ready_record(sample_rate: int) -> dict:
    return {
        "markerVersion": MARKER_VERSION,
        "variant": DEFAULT_VARIANT,
        "parameters": DEFAULT_PARAMETERS,
        "voice": "alba",
        "sampleRate": sample_rate,
    }


def ready_is_current(data: dict | None) -> bool:
    if not isinstance(data, dict):
        return False
    return (
        data.get("markerVersion") == MARKER_VERSION
        and data.get("variant") == DEFAULT_VARIANT
        and data.get("voice") == "alba"
    )


def parse_variant(raw: object) -> str:
    if raw is None:
        return DEFAULT_VARIANT
    if not isinstance(raw, str):
        raise PocketRequestError("variant 必须是官方模型 ID。", 400, "bad_variant")
    variant = raw.strip()
    if any(mark in variant for mark in ("/", "\\", ":", "?", "#")) or variant.startswith("hf"):
        raise PocketRequestError("variant 不接受路径、URL 或 hf://。", 400, "bad_variant")
    if variant == DEFAULT_VARIANT:
        return variant
    if variant in REJECTED_VARIANTS:
        raise PocketRequestError(REJECTED_VARIANTS[variant], 400, "variant_not_enabled")
    raise PocketRequestError(
        "variant 只能是 english_18m_2026-10。省略时也是这个 18.2M 模型，不会改用约 100M 的 english。",
        400,
        "bad_variant",
    )


def parse_pocket(payload: dict) -> tuple[str, str, str, str]:
    if "speaker" in payload:
        raise PocketRequestError("Pocket 音色没有 Piper 的 speaker 编号。", 400, "speaker_not_allowed")
    text = payload.get("text")
    if not isinstance(text, str) or "\x00" in text:
        raise PocketRequestError("text 必须是不含空字符的字符串。", 400, "bad_request")
    text = text.strip()
    if not text:
        raise PocketRequestError("请输入要朗读的文本。", 400, "bad_request")
    if len(text) > MAX_TEXT_CHARS:
        raise PocketRequestError(f"Pocket 文本不能超过 {MAX_TEXT_CHARS} 个字符。", 400, "text_too_long")
    raw_language = payload.get("language", "english")
    if not isinstance(raw_language, str):
        raise PocketRequestError("language 必须是自然语言代码。模型 ID 请放在 variant。", 400, "unsupported_language")
    key = raw_language.strip().lower().replace("-", "_")
    variant_keys = {item.replace("-", "_") for item in REJECTED_VARIANTS}
    variant_keys.add(DEFAULT_VARIANT.replace("-", "_"))
    if key not in _ALIAS and key in variant_keys:
        raise PocketRequestError("language 是自然语言。english_18m_2026-10 要放在 variant，不能放在 language。", 400, "unsupported_language")
    if key in UNSUPPORTED:
        raise PocketRequestError(UNSUPPORTED[key], 400, "unsupported_language")
    language = _ALIAS.get(key)
    if language is None:
        raise PocketRequestError(
            "当前只启用英语小模型。language 用 en 或 english。法语等上游语言没有接到 18.2M 变体上，也不会改用约 100M 模型。",
            400,
            "unsupported_language",
        )
    variant = parse_variant(payload.get("variant"))
    raw_voice = payload.get("voice", LANGUAGES[language]["voice"])
    if not isinstance(raw_voice, str):
        raise PocketRequestError("voice 必须是内置音色名。", 400, "unknown_voice")
    voice = raw_voice.strip()
    if any(mark in voice for mark in ("/", "\\", ":", "?", "#")) or voice.startswith("hf"):
        raise PocketRequestError("Pocket 不接受路径、URL 或 hf://。只能选内置音色名。", 400, "unknown_voice")
    allowed = VOICES_BY_LANGUAGE[language]
    if voice not in allowed:
        raise PocketRequestError(
            f"{voice} 不是 {language} 的内置音色。不会改用 Piper，也不会按文件克隆。",
            400,
            "unknown_voice",
        )
    return text, language, voice, variant
