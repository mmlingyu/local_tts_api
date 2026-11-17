"""Builtin Pocket TTS languages and voices.

pocket-tts 4.0.1 `get_predefined_voice` maps a builtin name to
`hf://kyutai/pocket-tts-without-voice-cloning/languages/{variant}/embeddings/{name}.safetensors`
at revision a7056f505a4a8ca72d8b5fb1440071d6f1a35739. For
`english_18m_2026-10` that directory contains 27 safetensors, the same 27 keys
as `_ORIGINS_OF_PREDEFINED_VOICES`. Clients cannot pass a path, URL, or `hf://`.
Those origin strings do not state gender. Chinese, Japanese, and Korean are
not Pocket languages, and the 18.2M model is not given a French or other
natural language just because a voice name also appears in another catalog.
"""

from __future__ import annotations

MAX_TEXT_CHARS = 500

# Published in pocket_tts/config/english_18m_2026-10.yaml as mimi.sample_rate.
PUBLISHED_SAMPLE_RATE = 24000

# Official small-model id. `language="english"` in pocket-tts is the ~100M model.
DEFAULT_VARIANT = "english_18m_2026-10"
DEFAULT_PARAMETERS = "18.2M"
MARKER_VERSION = 3
VOICE_EMBEDDING_REVISION = "a7056f505a4a8ca72d8b5fb1440071d6f1a35739"
PREPARE_COMMAND = "python -m pocket_local.prepare --confirm --variant english_18m_2026-10"

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

# Alphabetical stems of languages/english_18m_2026-10/embeddings/*.safetensors
# at VOICE_EMBEDDING_REVISION. Gender is unknown; nothing in that listing states it.
BUILTIN_VOICES = (
    "alba",
    "anna",
    "azelma",
    "bill_boerst",
    "caro_davy",
    "charles",
    "cosette",
    "daan",
    "eponine",
    "estelle",
    "eve",
    "fantine",
    "george",
    "giovanni",
    "jane",
    "javert",
    "jean",
    "juergen",
    "lola",
    "marius",
    "mary",
    "michael",
    "paul",
    "peter_yearsley",
    "rafael",
    "stuart_bell",
    "vera",
)

VOICES_BY_LANGUAGE = {
    "english": BUILTIN_VOICES,
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
                    "genderSource": "pocket-tts 4.0.1 _ORIGINS_OF_PREDEFINED_VOICES has no gender field",
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


def ready_record(sample_rate: int, voices: list[str] | None = None) -> dict:
    allowed = set(BUILTIN_VOICES)
    names: list[str] = []
    for name in voices or []:
        if name in allowed and name not in names:
            names.append(name)
    return {
        "markerVersion": MARKER_VERSION,
        "variant": DEFAULT_VARIANT,
        "parameters": DEFAULT_PARAMETERS,
        "modelPrepared": True,
        "voices": names,
        "sampleRate": sample_rate,
    }


def ready_is_current(data: dict | None) -> bool:
    """True when the 18.2M weight marker is current. Voice completeness is separate."""
    if not isinstance(data, dict) or data.get("variant") != DEFAULT_VARIANT:
        return False
    version = data.get("markerVersion")
    if version == MARKER_VERSION:
        return data.get("modelPrepared") is True
    # markerVersion 2 only recorded alba, after the 18.2M weights were cached.
    return version == 2 and data.get("voice") == "alba"


def prepared_voice_names(data: dict | None) -> list[str]:
    if not ready_is_current(data):
        return []
    assert data is not None
    if data.get("markerVersion") == 2:
        return ["alba"]
    raw = data.get("voices")
    if not isinstance(raw, list):
        return []
    allowed = set(BUILTIN_VOICES)
    names: list[str] = []
    for name in raw:
        if isinstance(name, str) and name in allowed and name not in names:
            names.append(name)
    return names


def voices_complete(data: dict | None) -> bool:
    return set(prepared_voice_names(data)) == set(BUILTIN_VOICES)


def missing_voice_names(data: dict | None) -> list[str]:
    prepared = set(prepared_voice_names(data))
    return [name for name in BUILTIN_VOICES if name not in prepared]


def not_ready_reason(installed: bool, data: dict | None) -> str | None:
    """None means the 18.2M weight marker is current. Otherwise do not download or switch engines."""
    if not installed:
        return "Pocket 虚拟环境还没装。请在 pocket-tts-service 里准备，不要装进 Piper 的虚拟环境。"
    if data is None:
        return "没有 models/ready.json。不会下载权重，也不会改用 Piper。"
    if not ready_is_current(data):
        found = data.get("variant")
        return (
            f"ready.json 的 variant 是 {found!r}，不是 {DEFAULT_VARIANT}。"
            "旧标记或不匹配的标记不能沿用，也不会下载。"
        )
    return None


def incomplete_reason(data: dict | None) -> str:
    prepared = prepared_voice_names(data)
    missing = missing_voice_names(data)
    prepared_text = ", ".join(prepared) if prepared else "无"
    missing_text = ", ".join(missing) if missing else "无"
    return (
        f"18.2M 权重标记已在，这不等于 worker 已加载，也不等于推理成功。"
        f"已准备音色 {len(prepared)}/{len(BUILTIN_VOICES)}：{prepared_text}。"
        f"未准备：{missing_text}。"
        f"已有 models/hf-home 会复用，不用重新登录或重下整模。执行 {PREPARE_COMMAND}。"
        "页面点击不会下载。"
    )


def voice_gap(data: dict | None, voice: str) -> tuple[str, str] | None:
    if not ready_is_current(data) or voice in prepared_voice_names(data):
        return None
    return (
        "voices_incomplete",
        f"{voice} 还没写入 english_18m_2026-10 的准备标记。{incomplete_reason(data)}",
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
