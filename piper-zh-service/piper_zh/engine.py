"""Load one Piper Mandarin voice and reuse it for every request."""

from __future__ import annotations

import os
import threading
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = SERVICE_DIR / "models" / "zh_CN-chaowen-medium.onnx"
DEFAULT_G2P_DIR = SERVICE_DIR / "models" / "g2pW"
DEFAULT_HF_HOME = SERVICE_DIR / "models" / "hf-home"

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

MAX_TEXT_CHARS = 2000


@dataclass
class Synthesis:
    wav: bytes
    sample_rate: int
    duration_seconds: float
    synth_seconds: float
    phoneme_type: str
    model_id: str


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
        missing = []
        if not model.is_file():
            missing.append(str(model))
        if not config.is_file():
            missing.append(str(config))
        if not g2p_onnx.is_file():
            missing.append(str(g2p_onnx))
        if missing:
            raise EngineError(
                "普通话模型或 g2pW 权重还没准备好，服务不会在请求时下载。"
                "请先运行 python -m piper_zh.download --confirm。缺少："
                + "；".join(missing)
            )
        import json

        try:
            config_data = json.loads(config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise EngineError(f"模型配置不是合法 JSON：{config}") from exc
        phoneme_type = config_data.get("phoneme_type")
        if phoneme_type != "pinyin":
            raise EngineError(
                f"{model.name} 的 phoneme_type 是 {phoneme_type!r}，不是 pinyin。"
                "huayan 使用 espeak 音素，不能接到这条 g2pW 路径上。"
                "请改用 zh_CN-chaowen-medium，或另一个模型卡写明 phoneme_type 为 pinyin 的音色。"
            )
        self.phoneme_type = phoneme_type
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
        # Build the g2pW session now. voice.phonemize caches it on the voice object.
        phonemes = voice.phonemize("测试。")
        if not phonemes or not phonemes[0]:
            raise EngineError("g2pW 预热没有返回音素。请确认 models/g2pW 与 bert-base-chinese 缓存完整。")
        self._voice = voice
        self.ready = True
        self.error = None

    def synthesize(self, text: str) -> Synthesis:
        if not self.ready or self._voice is None:
            raise EngineError(self.error or "模型尚未加载")
        import time

        started = time.perf_counter()
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)
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
            "g2p": "python-g2pW",
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
