"""Builtin Pocket TTS languages and voices.

Names come from pocket-tts 4.0.1 `default_parameters.py` and
`_ORIGINS_OF_PREDEFINED_VOICES`. A request cannot pass a file path, URL, or
`hf://` reference. Chinese, Japanese, and Korean are not in the upstream list.
"""

from __future__ import annotations

MAX_TEXT_CHARS = 500

# Published in pocket_tts/config/english.yaml as mimi.sample_rate.
# A live model may report the same value; this constant is the config fact.
PUBLISHED_SAMPLE_RATE = 24000

LANGUAGES = {
    "english": {"voice": "alba", "aliases": ("en", "en_us", "en-us")},
    "french": {"voice": "estelle", "aliases": ("fr", "fr_fr", "fr-fr")},
    "german": {"voice": "juergen", "aliases": ("de", "de_de", "de-de")},
    "portuguese": {"voice": "rafael", "aliases": ("pt", "pt_pt", "pt-pt")},
    "italian": {"voice": "giovanni", "aliases": ("it", "it_it", "it-it")},
    "spanish": {"voice": "lola", "aliases": ("es", "es_es", "es-es")},
    "dutch": {"voice": "daan", "aliases": ("nl", "nl_nl", "nl-nl")},
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
    "english": ENGLISH_VOICES,
    "french": ("estelle",),
    "german": ("juergen",),
    "portuguese": ("rafael",),
    "italian": ("giovanni",),
    "spanish": ("lola",),
    "dutch": ("daan",),
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
            "supported": True,
        }
        for name, spec in LANGUAGES.items()
    ]


def parse_pocket(payload: dict) -> tuple[str, str, str]:
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
        raise PocketRequestError("language 必须是 Pocket 官方语言名。", 400, "unsupported_language")
    key = raw_language.strip().lower().replace("-", "_")
    if key in UNSUPPORTED:
        raise PocketRequestError(UNSUPPORTED[key], 400, "unsupported_language")
    language = _ALIAS.get(key)
    if language is None:
        raise PocketRequestError(
            "Pocket 官方语言只有 english、french、german、portuguese、italian、spanish、dutch。没有中文、日语、韩语。",
            400,
            "unsupported_language",
        )
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
    return text, language, voice
