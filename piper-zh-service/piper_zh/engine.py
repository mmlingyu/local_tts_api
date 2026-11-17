"""Load one Piper Mandarin voice and reuse it for every request."""

from __future__ import annotations

import os
import threading
import wave
from dataclasses import dataclass
from io import BytesIO
from collections import OrderedDict
from pathlib import Path

from .catalog import BY_ID, DEFAULT_BY_LANGUAGE, RequestError, frontend_ready, inventory, language_rows

SERVICE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = SERVICE_DIR / "models" / "zh_CN-chaowen-medium.onnx"
DEFAULT_G2P_DIR = SERVICE_DIR / "models" / "g2pW"
DEFAULT_HF_HOME = SERVICE_DIR / "models" / "hf-home"
MAX_LOADED_VOICES = 2

# Facts taken from the published MODEL_CARD and Piper's licensing docs.
# The running service also returns the local MODEL_CARD text when that file exists.
LICENSE_INFO = {
    "engine": "GPL-3.0-or-later",
    "engineUrl": "https://github.com/OHF-Voice/piper1-gpl/blob/d76f335d9eb5dea5ef6d7d70b2d6114e6303fa08/docs/LICENSING.md",
    "recommendedModel": "zh_CN-chaowen-medium",
    "dataset": "CC0",
    "datasetUrl": "https://github.com/OHF-Voice/voice-datasets",
    "baseModel": "en_US-hifi_tts_92-medium",
    "baseLicense": "CC BY 4.0",
    "baseDatasetUrl": "https://www.openslr.org/109/",
    "attribution": (
        "超文（chaowen）录音为 CC0。"
        "该音色从 Hi-Fi TTS reader 92（Cori Samuel）的 en_US-hifi_tts_92-medium 微调而来，"
        "分发或再训练时需要按 CC BY 4.0 署名 Hi-Fi TTS。"
        "Piper 引擎本身是 GPL-3.0-or-later，引擎许可证不覆盖音色权重。"
    ),
    "phonemes": "pinyin，由 Python g2pW 生成。不要把 espeak 音素的 huayan 模型配到这条路径。",
    "notLegalAdvice": True,
}

MAX_TEXT_CHARS = 2000  # kept in sync with catalog.MAX_TEXT_CHARS


@dataclass
class Synthesis:
    wav: bytes
    sample_rate: int
    duration_seconds: float
    synth_seconds: float
    phoneme_type: str
    model_id: str
    language: str = "zh"
    speaker_id: int | None = None
    engine_header: str = "Piper-zh"
    voice_name: str | None = None
    voice_id: str | None = None
    peak: float | None = None


def wav_duration(blob: bytes) -> tuple[int, float, float]:
    """Return sample rate, duration seconds, and peak amplitude in 0..1."""
    with wave.open(BytesIO(blob), "rb") as wav_file:
        if wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
            raise ValueError("Piper 输出必须是 16-bit 单声道 WAV")
        rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())
    if rate <= 0 or len(frames) < 2:
        raise ValueError("WAV 没有音频样本")
    peak = 0
    for index in range(0, len(frames) - 1, 2):
        sample = int.from_bytes(frames[index : index + 2], "little", signed=True)
        peak = max(peak, abs(sample))
    duration = (len(frames) // 2) / rate
    return rate, duration, peak / 32768.0


class EngineError(RuntimeError):
    """The voice cannot be used. The HTTP service should stay up and report it."""


class PiperEngine:
    """One in-process voice. HTTP handlers must not construct another one per request."""

    def __init__(
        self,
        model_path: Path | None = None,
        g2p_dir: Path | None = None,
        hf_home: Path | None = None,
        device: str = "cpu",
    ) -> None:
        self.model_path = Path(model_path or DEFAULT_MODEL)
        self.g2p_dir = Path(g2p_dir or DEFAULT_G2P_DIR)
        self.hf_home = Path(hf_home or os.environ.get("HF_HOME") or DEFAULT_HF_HOME)
        if device not in {"cpu", "cuda"}:
            raise EngineError("device 只能是 cpu 或 cuda。这是启动参数，不是硬件探测结果。")
        self.device = device
        self.ready = False
        self.error: str | None = None
        self.phoneme_type = "pinyin"
        self.language = "zh"
        self.model_id = self.model_path.name.removesuffix(".onnx")
        self.sample_rate: int | None = None
        self._voice = None
        self._load_lock = threading.Lock()
        self._card_text = ""

    def load(self) -> None:
        """Load the ONNX voice and g2pW once. Never called from a request handler."""
        with self._load_lock:
            if self._voice is not None and self.ready:
                return
            try:
                self._load_locked()
            except Exception as exc:  # noqa: BLE001 - surface a local operator message
                self._voice = None
                self.ready = False
                self.error = str(exc)
                raise

    def _load_locked(self) -> None:
        model = self.model_path.expanduser().resolve()
        config = Path(str(model) + ".json")
        g2p_onnx = self.g2p_dir.expanduser().resolve() / "g2pw.onnx"
        card = model.parent / "MODEL_CARD"
        self.model_path = model
        self.model_id = model.name.removesuffix(".onnx")
        if card.is_file():
            self._card_text = card.read_text(encoding="utf-8")[:4000]
        expected = BY_ID.get(self.model_id)
        if expected is None:
            raise EngineError(f"{self.model_id} 不在音色白名单，拒绝加载。")
        missing = []
        if not model.is_file():
            missing.append(str(model))
        if not config.is_file():
            missing.append(str(config))
        if expected.phoneme_type == "pinyin" and not g2p_onnx.is_file():
            missing.append(str(g2p_onnx))
        if missing:
            raise EngineError(
                "所选音色的权重还没准备好，服务不会在请求时下载。"
                "请先运行 python -m piper_zh.download --confirm --voice "
                + expected.voice_id
                + "。缺少："
                + "；".join(missing)
            )
        import json

        try:
            config_data = json.loads(config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise EngineError(f"模型配置不是合法 JSON：{config}") from exc
        phoneme_type = config_data.get("phoneme_type")
        if phoneme_type != expected.phoneme_type:
            raise EngineError(
                f"{model.name} 的 phoneme_type 是 {phoneme_type!r}，白名单要求 {expected.phoneme_type}。"
                "不会把一种语言的前端接到另一种模型上。"
            )
        ready, reason = frontend_ready(expected)
        if not ready:
            raise EngineError(reason or "这个音色的前端还没准备好。")
        self.phoneme_type = phoneme_type
        self.language = expected.language
        audio = config_data.get("audio") or {}
        self.sample_rate = int(audio.get("sample_rate") or 0) or None

        # Requests must not reach Hugging Face. The download command fills this cache.
        os.environ["HF_HOME"] = str(self.hf_home)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise EngineError(
                "当前 Python 没有安装 piper-tts[zh]==1.8.0。"
                "请在 piper-zh-service 里创建虚拟环境并 pip install -r requirements.txt。"
            ) from exc

        voice = PiperVoice.load(
            model,
            config_path=config,
            use_cuda=self.device == "cuda",
            download_dir=self.g2p_dir.parent,
        )
        warmup = {"zh": "测试。", "en": "Hello.", "fr": "Bonjour.", "ja": "こんにちは。", "ko": "안녕하세요."}[
            expected.language
        ]
        phonemes = voice.phonemize(warmup)
        if not phonemes or not phonemes[0]:
            raise EngineError(f"{expected.voice_id} 的 {phoneme_type} 前端没有返回音素。")
        if phoneme_type != "pinyin" and getattr(voice, "_chinese_phonemizer", None) is not None:
            raise EngineError("非中文音色错误地调用了 g2pW。")
        self._voice = voice
        self.ready = True
        self.error = None

    def synthesize(self, text: str, speaker_id: int | None = None) -> Synthesis:
        if not self.ready or self._voice is None:
            raise EngineError(self.error or "模型尚未加载")
        import time

        from piper.config import SynthesisConfig

        started = time.perf_counter()
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            self._voice.synthesize_wav(
                text,
                wav_file,
                syn_config=SynthesisConfig(speaker_id=speaker_id),
            )
        elapsed = time.perf_counter() - started
        blob = buffer.getvalue()
        rate, duration, peak = wav_duration(blob)
        if peak <= 0 or duration <= 0:
            raise EngineError("合成结果是静音")
        return Synthesis(
            wav=blob,
            sample_rate=rate,
            duration_seconds=duration,
            synth_seconds=elapsed,
            phoneme_type=self.phoneme_type,
            model_id=self.model_id,
            language=getattr(self, "language", "zh"),
            speaker_id=speaker_id,
        )

    def status(self) -> dict:
        version = None
        try:
            from importlib.metadata import version as pkg_version

            version = pkg_version("piper-tts")
        except Exception:
            version = None
        return {
            "ok": self.ready,
            "engine": "piper-zh",
            "serviceVersion": "1.0.0",
            "piperPackage": "piper-tts[zh]==1.8.0",
            "piperVersion": version,
            "modelId": self.model_id,
            "modelPath": str(self.model_path),
            "modelReady": self.ready,
            "error": self.error,
            "phonemeType": self.phoneme_type,
            "g2p": "python-g2pW" if self.phoneme_type == "pinyin" else self.phoneme_type,
            "sampleRate": self.sample_rate,
            "configuredDevice": self.device,
            "hardwareProbe": False,
            "deviceNote": "configuredDevice 只表示本进程的启动参数，不代表检测过这台电脑的 GPU。",
            "supportsStreaming": False,
            "firstAudioMeasured": False,
            "responseMode": "full-wav",
            "maxTextChars": MAX_TEXT_CHARS,
            "license": LICENSE_INFO,
            "modelCard": self._card_text,
        }


class VoicePool:
    """Load whitelist voices on demand and keep at most a few of them resident."""

    def __init__(
        self,
        device: str = "cpu",
        cache_limit: int = MAX_LOADED_VOICES,
        g2p_dir: Path | None = None,
        hf_home: Path | None = None,
        chinese_model: Path | None = None,
        loader=None,
    ) -> None:
        if device not in {"cpu", "cuda"}:
            raise EngineError("device 只能是 cpu 或 cuda。这是启动参数，不是硬件探测结果。")
        if cache_limit < 1:
            raise EngineError("缓存至少要能留下 1 个音色。")
        self.device = device
        self.cache_limit = cache_limit
        self.g2p_dir = Path(g2p_dir or DEFAULT_G2P_DIR)
        self.hf_home = Path(hf_home or DEFAULT_HF_HOME)
        self.chinese_model = Path(chinese_model or DEFAULT_MODEL)
        if self.chinese_model.name != DEFAULT_MODEL.name:
            raise EngineError("启动参数里的中文模型只能是 zh_CN-chaowen-medium.onnx。")
        self.ready = True
        self.error = None
        self._engines: OrderedDict[str, PiperEngine] = OrderedDict()
        self._verified: set[str] = set()
        self._lock = threading.Lock()
        self._loader = loader

    def synthesize(self, text: str, language: str | None = None, voice: str | None = None, speaker: int | None = None) -> Synthesis:
        # language/voice/speaker are already normalized by the HTTP layer.
        # Direct callers may still pass the whitelist id.
        spec = BY_ID[voice or DEFAULT_BY_LANGUAGE["zh"].voice_id]
        if language is not None and language != spec.language:
            raise RequestError("language 与 voice 不一致。", 400, "language_voice_mismatch")
        with self._lock:
            engine = self._acquire(spec)
            result = engine.synthesize(text, speaker_id=speaker)
            self._verified.add(spec.voice_id)
            return result

    def _acquire(self, spec) -> PiperEngine:
        current = self._engines.get(spec.voice_id)
        if current is not None and current.ready:
            self._engines.move_to_end(spec.voice_id)
            return current
        while len(self._engines) >= self.cache_limit:
            self._engines.popitem(last=False)
        if self._loader is not None:
            engine = self._loader(spec)
            self._engines[spec.voice_id] = engine
            return engine
        model = self.chinese_model if spec.legacy_flat else spec.model_path
        engine = PiperEngine(
            model_path=model,
            g2p_dir=self.g2p_dir,
            hf_home=self.hf_home,
            device=self.device,
        )
        try:
            engine.load()
        except EngineError as exc:
            message = str(exc)
            code = "frontend_missing" if "前端" in message or "espeak" in message or "g2pW" in message else "model_missing"
            raise RequestError(message, 503, code) from exc
        self._engines[spec.voice_id] = engine
        return engine

    def release_all(self) -> int:
        """Drop resident Piper voices before another engine loads."""
        with self._lock:
            count = len(self._engines)
            self._engines.clear()
            return count

    def status(self) -> dict:
        loaded = set(self._engines)
        default = DEFAULT_BY_LANGUAGE["zh"]
        default_ready = default.downloaded() and frontend_ready(default)[0]
        version = None
        try:
            from importlib.metadata import version as pkg_version

            version = pkg_version("piper-tts")
        except Exception:
            version = None
        loaded_engine = self._engines.get(default.voice_id)
        return {
            "ok": default_ready,
            "engine": "piper-zh",
            "serviceVersion": "1.1.0",
            "piperPackage": "piper-tts[zh]==1.8.0",
            "piperVersion": version,
            "modelId": default.voice_id if default_ready else None,
            "modelPath": str(self.chinese_model if default.legacy_flat else default.model_path),
            "modelReady": default_ready,
            "loaded": default.voice_id in loaded,
            "loadedVoiceIds": list(self._engines),
            "cacheLimit": self.cache_limit,
            "error": None if default_ready else "默认中文音色还没准备好。其他已下载的白名单音色仍可单独调用。",
            "phonemeType": default.phoneme_type if default_ready else None,
            "g2p": "python-g2pW" if default_ready else None,
            "sampleRate": default.sample_rate,
            "configuredDevice": self.device,
            "hardwareProbe": False,
            "deviceNote": "configuredDevice 只表示本进程的启动参数，不代表检测过这台电脑的 GPU。",
            "supportsStreaming": False,
            "firstAudioMeasured": False,
            "responseMode": "full-wav",
            "maxTextChars": MAX_TEXT_CHARS,
            "license": LICENSE_INFO,
            "languages": language_rows(loaded, self._verified),
            "voices": inventory(loaded, self._verified),
            "residentModels": list(self._engines),
            "modelCard": loaded_engine._card_text if loaded_engine is not None else "",
        }
