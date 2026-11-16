"""Official Piper voices this service is willing to load.

The ids, sizes, and MD5 values come from the Hugging Face `voices.json` index
fetched on 2026-11-16. URLs are fixed here. A request cannot supply a path or
a download address.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = SERVICE_DIR / "models"

MAX_TEXT_CHARS = 2000

# voices.json has these five language families for the requested set.
# VOICES.md's bullet list names zh, en, and fr. It does not name ja or ko.
# The download index still publishes one voice for each of those two.


class RequestError(Exception):
    def __init__(self, message: str, status: int, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


@dataclass(frozen=True)
class VoiceFile:
    name: str
    size: int
    md5: str

    @property
    def url(self) -> str:
        raise RuntimeError("VoiceFile.url is set on the voice, not the part")


@dataclass(frozen=True)
class VoiceSpec:
    voice_id: str
    language: str
    locale: str
    name: str
    quality: str
    phoneme_type: str
    espeak_voice: str | None
    sample_rate: int
    num_speakers: int
    speakers: dict[str, int]
    default_speaker_id: int
    onnx_size: int
    onnx_md5: str
    config_size: int
    config_md5: str
    card_size: int
    card_md5: str
    dataset_license: str
    dataset_url: str
    training: str
    commercial_note: str
    documented_in_voices_md: bool
    is_default: bool
    legacy_flat: bool = False
    gender: str = "unknown"
    gender_source: str = ""
    speaker_genders: dict[str, str] = field(default_factory=dict)
    license_class: str = "unknown"

    @property
    def directory(self) -> Path:
        if self.legacy_flat:
            return MODELS_DIR
        return MODELS_DIR / "voices" / self.voice_id

    @property
    def model_path(self) -> Path:
        return self.directory / f"{self.voice_id}.onnx"

    @property
    def config_path(self) -> Path:
        return self.directory / f"{self.voice_id}.onnx.json"

    @property
    def card_path(self) -> Path:
        return self.directory / "MODEL_CARD"

    def files(self) -> tuple[tuple[Path, VoiceFile], ...]:
        return (
            (self.model_path, VoiceFile(f"{self.voice_id}.onnx", self.onnx_size, self.onnx_md5)),
            (self.config_path, VoiceFile(f"{self.voice_id}.onnx.json", self.config_size, self.config_md5)),
            (self.card_path, VoiceFile("MODEL_CARD", self.card_size, self.card_md5)),
        )

    def huggingface_url(self, filename: str) -> str:
        family, region_name = self.locale.split("_", 1)
        return (
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            f"{family}/{self.locale}/{self.name}/{self.quality}/{filename}"
        )

    def downloaded(self) -> bool:
        for path, spec in self.files():
            if not path.is_file() or path.stat().st_size != spec.size:
                return False
        return True

    def verified_files(self) -> bool:
        for path, spec in self.files():
            if not path.is_file() or path.stat().st_size != spec.size:
                return False
            if _md5(path) != spec.md5:
                return False
        return True


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


VOICES: tuple[VoiceSpec, ...] = (
    VoiceSpec(
        voice_id="zh_CN-chaowen-medium",
        language="zh",
        locale="zh_CN",
        name="chaowen",
        quality="medium",
        phoneme_type="pinyin",
        espeak_voice=None,
        sample_rate=22050,
        num_speakers=1,
        speakers={},
        default_speaker_id=0,
        onnx_size=63_221_984,
        onnx_md5="6a5fa2ac1cdacad3deb10eb60844a35d",
        config_size=3157,
        config_md5="bc31773752c7811b2b4e2e33e83e86a9",
        card_size=472,
        card_md5="d681d121e12f168a1c5d080143b7d02d",
        dataset_license="CC0",
        dataset_url="https://github.com/OHF-Voice/voice-datasets",
        training="Finetuned from en_US-hifi_tts_92-medium (Hi-Fi TTS reader 92, Cori Samuel, CC BY 4.0).",
        commercial_note="录音本身是 CC0。底模 Hi-Fi TTS 是 CC BY 4.0，分发时要署名。这不是法律意见。",
        documented_in_voices_md=True,
        is_default=True,
        legacy_flat=True,
        gender="unknown",
        gender_source="https://huggingface.co/rhasspy/piper-voices/blob/main/zh/zh_CN/chaowen/medium/MODEL_CARD",
        license_class="attribution",
    ),
    VoiceSpec(
        voice_id="zh_CN-xiao_ya-medium",
        language="zh",
        locale="zh_CN",
        name="xiao_ya",
        quality="medium",
        phoneme_type="pinyin",
        espeak_voice=None,
        sample_rate=22050,
        num_speakers=1,
        speakers={},
        default_speaker_id=0,
        onnx_size=63_221_984,
        onnx_md5="b1cece47c5d601a8f6b63b8da82b484a",
        config_size=2927,
        config_md5="6018be9c632a62548fea129a42a4610a",
        card_size=434,
        card_md5="d5fc6eab8567db163e9cff56ed53f387",
        dataset_license="Non-commercial",
        dataset_url="https://www.data-baker.com/data/index/TNtts/",
        training="Trained from scratch. phoneme_type is pinyin, so synthesis uses g2pW and not espeak.",
        commercial_note="标贝中文标准女声音库只允许非商用。不是默认音色，也不能当成可商用女声。这不是法律意见。",
        documented_in_voices_md=True,
        is_default=False,
        gender="female",
        gender_source="https://www.data-baker.com/data/index/TNtts/",
        license_class="noncommercial",
    ),
    VoiceSpec(
        voice_id="en_US-joe-medium",
        language="en",
        locale="en_US",
        name="joe",
        quality="medium",
        phoneme_type="espeak",
        espeak_voice="en-us",
        sample_rate=22050,
        num_speakers=1,
        speakers={},
        default_speaker_id=0,
        onnx_size=63_221_984,
        onnx_md5="8dd388e2a102cbde27ca3fba4e78f488",
        config_size=5465,
        config_md5="1f50b93e502afa734bb3f50fcce34c52",
        card_size=423,
        card_md5="6b74715035811ff52524e22559e68f55",
        dataset_license="CC0",
        dataset_url="https://github.com/OHF-Voice/voice-datasets",
        training="Finetuned from nl_BE-rdh-medium (CC0). Not fine-tuned from lessac.",
        commercial_note="官方商用清单把整条训练链记为 CC0。这不是法律意见，也不覆盖 Piper 引擎的 GPL。",
        documented_in_voices_md=True,
        is_default=True,
        gender="unknown",
        gender_source="https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/joe/medium/MODEL_CARD",
        license_class="permissive",
    ),
    VoiceSpec(
        voice_id="en_US-ljspeech-medium",
        language="en",
        locale="en_US",
        name="ljspeech",
        quality="medium",
        phoneme_type="espeak",
        espeak_voice="en",
        sample_rate=22050,
        num_speakers=1,
        speakers={},
        default_speaker_id=0,
        onnx_size=63_531_379,
        onnx_md5="109d552e9dd78d92d1169a7edd6de38d",
        config_size=4972,
        config_md5="0668112b8b3ac5bb4b12c2b1a366776a",
        card_size=517,
        card_md5="5ad31d314786587d4f97effb0b716d61",
        dataset_license="public domain",
        dataset_url="https://keithito.com/LJ-Speech-Dataset/",
        training="Trained from scratch. The model card says: US English female voice.",
        commercial_note="公有领域，从零训练。模型卡写明是美国英语女声。这不是法律意见。",
        documented_in_voices_md=True,
        is_default=False,
        gender="female",
        gender_source="https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/ljspeech/medium/MODEL_CARD",
        license_class="permissive",
    ),
    VoiceSpec(
        voice_id="en_US-norman-medium",
        language="en",
        locale="en_US",
        name="norman",
        quality="medium",
        phoneme_type="espeak",
        espeak_voice="en",
        sample_rate=22050,
        num_speakers=1,
        speakers={},
        default_speaker_id=0,
        onnx_size=63_531_379,
        onnx_md5="829cea515dc724d694b83b71e8083f9f",
        config_size=4968,
        config_md5="975830d6f230f6eccf657d265de99eba",
        card_size=528,
        card_md5="c34f20bbc4918681ad7a070a8321f2fa",
        dataset_license="public domain",
        dataset_url="https://librivox.org",
        training="Trained from scratch. The model card says: US English male voice.",
        commercial_note="公有领域，从零训练。模型卡写明是美国英语男声。这不是法律意见。",
        documented_in_voices_md=True,
        is_default=False,
        gender="male",
        gender_source="https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/norman/medium/MODEL_CARD",
        license_class="permissive",
    ),
    VoiceSpec(
        voice_id="fr_FR-siwis-medium",
        language="fr",
        locale="fr_FR",
        name="siwis",
        quality="medium",
        phoneme_type="espeak",
        espeak_voice="fr",
        sample_rate=22050,
        num_speakers=1,
        speakers={},
        default_speaker_id=0,
        onnx_size=63_221_984,
        onnx_md5="bb8456dcd54ce8143ee62c19bf2d4b41",
        config_size=5458,
        config_md5="1ab0f73eb813ff70b6228d03ff9aed94",
        card_size=502,
        card_md5="e91cf50daa58d5ef95d1c8fe3caf2099",
        dataset_license="CC BY 4.0",
        dataset_url="https://datashare.is.ed.ac.uk/handle/10283/2353",
        training="Finetuned from en_US-hifi_tts_92-medium (CC BY 4.0). Not a CC0 voice.",
        commercial_note="数据集和底模都是 CC BY 4.0，需要署名，不是完全无义务的许可。这不是法律意见。",
        documented_in_voices_md=True,
        is_default=True,
    ),
    VoiceSpec(
        voice_id="ja_JP-hi_fi_captain-medium",
        language="ja",
        locale="ja_JP",
        name="hi_fi_captain",
        quality="medium",
        phoneme_type="japanese",
        espeak_voice=None,
        sample_rate=22050,
        num_speakers=2,
        speakers={"female": 0, "male": 1},
        default_speaker_id=0,
        onnx_size=76_753_841,
        onnx_md5="f9daab8970d06d7e9fc895a879854542",
        config_size=5301,
        config_md5="828a68fa5fc7677f98ea336fa1d66512",
        card_size=361,
        card_md5="f4c4d57dd187c3836381134026d84c45",
        dataset_license="CC BY-NC-SA 4.0",
        dataset_url="https://ast-astrec.nict.go.jp/en/release/hi-fi-captain/",
        training="Finetuned from a LibriTTS-R base. Requires the Japanese OpenJTalk frontend, not g2pW and not espeak.",
        commercial_note="数据集是非商用的 CC BY-NC-SA 4.0。VOICES.md 的语言列表没有写日语，但 voices.json 有这一条。这不是法律意见。",
        documented_in_voices_md=False,
        is_default=True,
        gender="multiple",
        gender_source="https://huggingface.co/rhasspy/piper-voices/resolve/main/ja/ja_JP/hi_fi_captain/medium/ja_JP-hi_fi_captain-medium.onnx.json",
        speaker_genders={"female": "female", "male": "male"},
        license_class="noncommercial",
    ),
    VoiceSpec(
        voice_id="ko_KR-kss-medium",
        language="ko",
        locale="ko_KR",
        name="kss",
        quality="medium",
        phoneme_type="espeak",
        espeak_voice="ko",
        sample_rate=22050,
        num_speakers=1,
        speakers={},
        default_speaker_id=0,
        onnx_size=63_221_984,
        onnx_md5="bebbd298dffe5ee7b88f2ce41bb4e3a9",
        config_size=5232,
        config_md5="427c0b8d93211ba2ffea1f565819058a",
        card_size=333,
        card_md5="90186834a09a6110dff277d342446845",
        dataset_license="CC BY-NC-SA 4.0",
        dataset_url="https://www.kaggle.com/datasets/bryanpark/korean-single-speaker-speech-dataset",
        training="Finetuned from a LibriTTS-R base. phoneme_type is espeak with voice ko. There is no separate Korean g2p in this service.",
        commercial_note="数据集是非商用的 CC BY-NC-SA 4.0。VOICES.md 的语言列表没有写韩语，但 voices.json 有这一条。这不是法律意见。",
        documented_in_voices_md=False,
        is_default=True,
        gender="female",
        gender_source="https://www.kaggle.com/datasets/bryanpark/korean-single-speaker-speech-dataset",
        license_class="noncommercial",
    ),
)

# Official index has no verified voice for these cells. Do not invent one.
GENDER_GAPS = {
    "zh": "没有官方中文模型写明男声。超文的模型卡和 voice-datasets 都没写性别。华严许可证未知，而且音素是 espeak，没有把它当成已核实男声。",
    "en": "",
    "ja": "",
    "ko": "voices.json 只有 ko_KR-kss-medium。没有官方韩语男声或多说话人模型。不能用变调、别的语言或新训练来冒充。",
    "fr": "这轮不补法语性别。siwis 的模型卡没有写性别。",
}

BY_ID = {item.voice_id: item for item in VOICES}
DEFAULT_BY_LANGUAGE = {item.language: item for item in VOICES if item.is_default}

LANGUAGE_ALIASES = {
    "zh": "zh",
    "zh_cn": "zh",
    "zh-cn": "zh",
    "en": "en",
    "en_us": "en",
    "en-us": "en",
    "fr": "fr",
    "fr_fr": "fr",
    "fr-fr": "fr",
    "ja": "ja",
    "ja_jp": "ja",
    "ja-jp": "ja",
    "ko": "ko",
    "ko_kr": "ko",
    "ko-kr": "ko",
}

_HAN = re.compile(r"[\u3400-\u9fff]")
_KANA = re.compile(r"[\u3040-\u30ff]")
_HANGUL = re.compile(r"[\uac00-\ud7af]")


def frontend_ready(spec: VoiceSpec) -> tuple[bool, str | None]:
    if spec.phoneme_type == "pinyin":
        onnx = MODELS_DIR / "g2pW" / "g2pw.onnx"
        if not onnx.is_file():
            return False, "缺少 g2pW。中文音色不会改用 espeak。"
        return True, None
    if spec.phoneme_type == "espeak":
        try:
            from piper.phonemize_espeak import ESPEAK_DATA_DIR
        except ImportError:
            return False, "没有安装带 espeak-ng 数据的 piper-tts。"
        voice = spec.espeak_voice or ""
        folder = voice.split("-", 1)[0]
        # Piper ships espeak-ng language data as <code>_dict, not voices/<code>.
        if not (Path(ESPEAK_DATA_DIR) / f"{folder}_dict").is_file():
            return False, f"内置 espeak 数据里没有 {spec.espeak_voice}。"
        return True, None
    if spec.phoneme_type == "japanese":
        try:
            import importlib.util

            if importlib.util.find_spec("pyopenjtalk") is None:
                raise ImportError
        except ImportError:
            return False, "日语前端未安装。需要 pyopenjtalk-plus，不能改用 g2pW 或 espeak。"
        return True, None
    return False, f"没有为 phoneme_type={spec.phoneme_type} 实现前端。"


def inventory(loaded_ids: set[str] | None = None, verified_ids: set[str] | None = None) -> list[dict]:
    loaded_ids = loaded_ids or set()
    verified_ids = verified_ids or set()
    rows = []
    for spec in VOICES:
        ready, reason = frontend_ready(spec)
        rows.append(
            {
                "voice": spec.voice_id,
                "language": spec.language,
                "locale": spec.locale,
                "phonemeType": spec.phoneme_type,
                "espeakVoice": spec.espeak_voice,
                "sampleRate": spec.sample_rate,
                "numSpeakers": spec.num_speakers,
                "speakers": spec.speakers,
                "defaultSpeakerId": spec.default_speaker_id,
                "defaultForLanguage": spec.is_default,
                "datasetLicense": spec.dataset_license,
                "datasetUrl": spec.dataset_url,
                "training": spec.training,
                "commercialNote": spec.commercial_note,
                "documentedInVoicesMd": spec.documented_in_voices_md,
                "official": True,
                "supported": True,
                "downloaded": spec.downloaded(),
                "filesMatchIndex": spec.verified_files() if spec.downloaded() else False,
                "loaded": spec.voice_id in loaded_ids,
                "frontendReady": ready,
                "frontendError": reason,
                "synthesisVerifiedThisProcess": spec.voice_id in verified_ids,
                "pronunciationReviewed": False,
                "onnxBytes": spec.onnx_size,
                "gender": spec.gender,
                "genderSource": spec.gender_source,
                "speakerGenders": spec.speaker_genders,
                "licenseClass": spec.license_class,
            }
        )
    return rows


def language_rows(loaded_ids: set[str] | None = None, verified_ids: set[str] | None = None) -> list[dict]:
    voices = inventory(loaded_ids, verified_ids)
    rows = []
    for language in ("zh", "en", "ja", "ko", "fr"):
        owned = [item for item in voices if item["language"] == language]
        present = set()
        for item in owned:
            if item["speakerGenders"]:
                present.update(item["speakerGenders"].values())
            elif item["gender"] in {"female", "male"}:
                present.add(item["gender"])
        missing = [name for name in ("female", "male") if name not in present]
        rows.append(
            {
                "language": language,
                "locale": owned[0]["locale"],
                "officialVoiceCount": len(owned),
                "supported": bool(owned),
                "gap": GENDER_GAPS.get(language) or None,
                "verifiedGenders": sorted(present),
                "missingGenders": missing,
                "voices": [item["voice"] for item in owned],
                "defaultVoice": next(item["voice"] for item in owned if item["defaultForLanguage"]),
                "anyDownloaded": any(item["downloaded"] for item in owned),
                "anyLoaded": any(item["loaded"] for item in owned),
                "pronunciationReviewed": False,
            }
        )
    return rows


@dataclass(frozen=True)
class TtsRequest:
    engine: str
    text: str
    language: str
    voice: str
    speaker: int | None
    variant: str | None = None


def parse_tts_fields(payload: dict) -> TtsRequest:
    if not isinstance(payload, dict) or "text" not in payload or not set(payload) <= {"text", "language", "voice", "speaker", "engine", "variant"}:
        raise RequestError(
            '只接受 {"text": "..."}，可选 engine、language、voice、speaker。不能传 gender，也不能指定模型、路径、地址或命令。',
            400,
            "bad_request",
        )
    engine = payload.get("engine", "piper")
    if engine is None:
        engine = "piper"
    if not isinstance(engine, str) or engine not in {"piper", "pocket"}:
        raise RequestError("engine 只能是 piper 或 pocket。省略时仍是 piper。", 400, "bad_engine")
    if engine == "pocket":
        import sys

        root = Path(__file__).resolve().parents[2] / "pocket-tts-service"
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from pocket_local.catalog import PocketRequestError, parse_pocket

        try:
            text, language, voice, variant = parse_pocket(payload)
        except PocketRequestError as exc:
            raise RequestError(exc.message, exc.status, exc.code) from exc
        return TtsRequest("pocket", text, language, voice, None, variant)
    if "variant" in payload:
        raise RequestError("variant 只用于 Pocket。Piper 请求不要带这个字段。", 400, "bad_request")
    text = payload["text"]
    if not isinstance(text, str) or "\x00" in text:
        raise RequestError("text 必须是不含空字符的字符串。", 400, "bad_request")
    text = text.strip()
    if not text:
        raise RequestError("请输入要朗读的文本。", 400, "bad_request")
    if len(text) > MAX_TEXT_CHARS:
        raise RequestError(f"文本不能超过 {MAX_TEXT_CHARS} 个字符。", 400, "text_too_long")

    language = payload.get("language", None)
    voice = payload.get("voice", None)
    if language is not None and not isinstance(language, str):
        raise RequestError("language 必须是语言代码。", 400, "bad_request")
    if voice is not None and not isinstance(voice, str):
        raise RequestError("voice 必须是白名单里的音色 id。", 400, "bad_request")

    if voice is None and language is None:
        spec = DEFAULT_BY_LANGUAGE["zh"]
    elif voice is None:
        key = LANGUAGE_ALIASES.get(language.strip().lower())
        if key is None:
            raise RequestError(
                "不支持这个 language。白名单只有 zh、en、ja、ko、fr，或对应的 zh_CN、en_US、ja_JP、ko_KR、fr_FR。",
                400,
                "unsupported_language",
            )
        spec = DEFAULT_BY_LANGUAGE[key]
    else:
        spec = BY_ID.get(voice.strip())
        if spec is None:
            raise RequestError(
                "voice 不在白名单。没有 lessac，也不会接受任意文件名。请改用 /api/voices 里的 id。",
                400,
                "unknown_voice",
            )
        if language is not None:
            key = LANGUAGE_ALIASES.get(language.strip().lower())
            if key is None:
                raise RequestError(
                    "不支持这个 language。白名单只有 zh、en、ja、ko、fr，或对应的 zh_CN、en_US、ja_JP、ko_KR、fr_FR。",
                    400,
                    "unsupported_language",
                )
            if key != spec.language:
                raise RequestError(
                    f"{spec.voice_id} 属于 {spec.language}，不能同时声明 language={language.strip()}。",
                    400,
                    "language_voice_mismatch",
                )
    _reject_wrong_script(spec.language, text)
    speaker_id = _speaker_id(spec, payload)
    return TtsRequest("piper", text, spec.language, spec.voice_id, speaker_id)


def _speaker_id(spec: VoiceSpec, payload: dict) -> int | None:
    if "speaker" not in payload:
        if spec.num_speakers > 1:
            return spec.default_speaker_id
        return None
    if spec.num_speakers <= 1:
        raise RequestError(f"{spec.voice_id} 只有一个说话人，不能传 speaker。", 400, "speaker_not_allowed")
    raw = payload["speaker"]
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise RequestError("speaker 必须是白名单里的名字或编号。", 400, "speaker_out_of_range")
    if isinstance(raw, int):
        if raw < 0 or raw >= spec.num_speakers:
            raise RequestError(
                f"speaker 编号必须在 0 到 {spec.num_speakers - 1}。",
                400,
                "speaker_out_of_range",
            )
        return raw
    key = raw.strip().lower()
    if key not in spec.speakers:
        names = "、".join(spec.speakers)
        raise RequestError(f"未知 speaker。可选：{names}。", 400, "speaker_out_of_range")
    return spec.speakers[key]


def _reject_wrong_script(language: str, text: str) -> None:
    if language == "zh":
        return
    if language in {"en", "fr"} and (_HAN.search(text) or _KANA.search(text) or _HANGUL.search(text)):
        raise RequestError(
            "这段文本含有汉字、假名或韩文。英语和法语音色不会拆句，也不会改用中文、日语或韩语音色。",
            400,
            "mixed_script",
        )
    if language == "ja" and _HANGUL.search(text):
        raise RequestError("日语音色不会朗读韩文，也不会自动改用韩语音色。", 400, "mixed_script")
    if language == "ko" and _KANA.search(text):
        raise RequestError("韩语音色不会朗读假名，也不会自动改用日语音色。", 400, "mixed_script")
