"""HTTP tests around the Piper service. The voice here is fake.

Real g2pW synthesis lives in test_real_synthesis.py and is skipped when the
weights are absent. These tests must not be described as end-to-end audio.
"""

from __future__ import annotations

import json
import math
import struct
import threading
import urllib.error
import urllib.request
import wave
from io import BytesIO

import pytest

from piper_zh.download import run as download_run
from piper_zh.engine import MAX_TEXT_CHARS
from piper_zh.server import create_server


def tone_wav(seconds: float = 0.4, rate: int = 22050) -> bytes:
    count = int(seconds * rate)
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        frames = bytearray()
        for index in range(count):
            sample = int(0.2 * 32767 * math.sin(2 * math.pi * 440 * index / rate))
            frames += struct.pack("<h", sample)
        wav_file.writeframes(frames)
    return buffer.getvalue()


class FakeEngine:
    """Stand-in used only by unit tests. It does not load Piper or a model."""

    def __init__(self) -> None:
        self.ready = True
        self.error = None
        self.calls: list[str] = []
        self.requests: list[tuple] = []
        self.entered = threading.Event()
        self.release = threading.Event()

    def synthesize(self, text: str, language: str | None = None, voice: str | None = None, speaker: int | None = None):
        from piper_zh.engine import Synthesis

        self.calls.append(text)
        self.requests.append((language, voice, speaker))
        if text == "HOLD":
            self.entered.set()
            assert self.release.wait(5)
        wav = tone_wav()
        return Synthesis(
            wav=wav,
            sample_rate=22050,
            duration_seconds=0.4,
            synth_seconds=0.05,
            phoneme_type="pinyin",
            model_id=voice or "zh_CN-chaowen-medium",
            language=language or "zh",
            speaker_id=speaker,
        )

    def status(self) -> dict:
        return {
            "ok": self.ready,
            "modelReady": self.ready,
            "error": self.error,
            "modelId": "zh_CN-chaowen-medium",
            "configuredDevice": "cpu",
            "hardwareProbe": False,
            "supportsStreaming": False,
            "firstAudioMeasured": False,
            "responseMode": "full-wav",
            "license": {"attribution": "测试替身，不是模型卡。"},
        }


@pytest.fixture
def server():
    engine = FakeEngine()
    httpd = create_server(engine, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.service_state.port
    base = f"http://127.0.0.1:{port}"
    yield httpd, engine, base
    httpd.shutdown()


def request(base: str, path: str, payload: dict | None = None, method: str | None = None, host: str | None = None, origin: str | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method=method or ("POST" if data else "GET"))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if host:
        req.add_header("Host", host)
    if origin:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def test_cors_keeps_8787_when_piper_uses_another_port():
    from piper_zh.server import ServiceState

    state = ServiceState(FakeEngine(), 8800)
    assert "http://127.0.0.1:8787" in state.origins()
    assert "http://127.0.0.1:8800" in state.origins()
    assert "http://example.com:8800" not in state.origins()


def test_health_and_page(server):
    _httpd, _engine, base = server
    status, _headers, body = request(base, "/api/health")
    assert status == 200
    payload = json.loads(body)
    assert payload["modelReady"] is True
    assert payload["hardwareProbe"] is False
    assert payload["supportsStreaming"] is False
    assert payload["firstAudioMeasured"] is False
    status, _headers, page = request(base, "/piper-compare.html")
    assert status == 200
    text = page.decode("utf-8")
    assert "多音字" in text
    assert "人工音质" in text
    assert "RTF" in text


def test_rejects_remote_host_and_origin(server):
    _httpd, _engine, base = server
    port = base.rsplit(":", 1)[1]
    status, _headers, body = request(base, "/api/health", host=f"example.com:{port}")
    assert status == 403
    assert "回环" in json.loads(body)["error"]
    status, _headers, body = request(base, "/api/health", origin="http://evil.example")
    assert status == 403


def test_rejects_path_and_command_fields(server):
    _httpd, engine, base = server
    status, _headers, body = request(base, "/api/tts", {"text": "你好。", "model": "/etc/passwd"})
    assert status == 400
    assert engine.calls == []
    status, _headers, body = request(base, "/api/tts", {"text": "你好。", "command": "rm -rf /"})
    assert status == 400
    status, _headers, _body = request(base, "/api/tts", {"text": ""})
    assert status == 400
    status, _headers, _body = request(base, "/api/tts", {"text": "啊" * (MAX_TEXT_CHARS + 1)})
    assert status == 400
    assert engine.calls == []


def test_wav_headers_define_full_utterance_rtf(server):
    _httpd, engine, base = server
    status, headers, body = request(base, "/api/tts", {"text": "你好。"})
    assert status == 200
    assert engine.calls == ["你好。"]
    assert headers["Content-Type"].startswith("audio/wav")
    assert headers["X-Streaming"] == "full-wav"
    assert "X-First-Audio" not in headers
    assert "X-Time-To-First-Audio" not in "".join(headers)
    synth = float(headers["X-Synth-Seconds"])
    duration = float(headers["X-Audio-Duration"])
    assert synth == pytest.approx(0.05)
    assert duration == pytest.approx(0.4)
    assert float(headers["X-RTF"]) == pytest.approx(synth / duration)
    assert body[:4] == b"RIFF"
    with wave.open(BytesIO(body), "rb") as wav_file:
        assert wav_file.getframerate() == 22050
        assert wav_file.getnframes() / wav_file.getframerate() == pytest.approx(0.4)


def test_busy_returns_429_without_second_synthesis(server):
    _httpd, engine, base = server
    box: dict = {}

    def first() -> None:
        box["result"] = request(base, "/api/tts", {"text": "HOLD"})

    thread = threading.Thread(target=first)
    thread.start()
    assert engine.entered.wait(3)
    status, _headers, body = request(base, "/api/tts", {"text": "第二条"})
    assert status == 429
    assert "正在合成" in json.loads(body)["error"]
    engine.release.set()
    thread.join(5)
    assert box["result"][0] == 200
    assert engine.calls == ["HOLD"]


def test_not_ready_is_a_readable_503(server):
    httpd, engine, base = server
    engine.ready = False
    engine.error = "请先运行 python -m piper_zh.download --confirm"
    status, _headers, body = request(base, "/api/tts", {"text": "你好。"})
    assert status == 503
    assert "download --confirm" in json.loads(body)["error"]
    assert engine.calls == []
    httpd.service_state.finish()


def test_download_command_does_not_fetch_without_confirm():
    assert download_run([]) == 2
    assert download_run(["--language", "en"]) == 2
    assert download_run(["--voice", "en_US-lessac-medium"]) == 2
    assert download_run(["--list"]) == 0


def test_old_text_body_stays_chinese(server):
    _httpd, engine, base = server
    status, headers, _body = request(base, "/api/tts", {"text": "你好。"})
    assert status == 200
    assert engine.requests == [("zh", "zh_CN-chaowen-medium", None)]
    assert headers["X-Language"] == "zh"
    assert headers["X-Voice"] == "zh_CN-chaowen-medium"


def test_whitelist_rejects_unknown_voice_mismatch_and_paths(server):
    _httpd, engine, base = server
    status, _headers, body = request(base, "/api/tts", {"text": "Hello.", "voice": "en_US-lessac-medium"})
    assert status == 400
    assert json.loads(body)["code"] == "unknown_voice"
    status, _headers, body = request(base, "/api/tts", {"text": "Hello.", "language": "de"})
    assert status == 400
    assert json.loads(body)["code"] == "unsupported_language"
    status, _headers, body = request(
        base, "/api/tts", {"text": "Hello.", "language": "zh", "voice": "en_US-joe-medium"}
    )
    assert status == 400
    assert json.loads(body)["code"] == "language_voice_mismatch"
    status, _headers, body = request(base, "/api/tts", {"text": "Hello.", "voice": "en_US-joe-medium", "url": "http://example.com/a.onnx"})
    assert status == 400
    status, _headers, body = request(base, "/api/tts", {"text": "你好。", "voice": "en_US-joe-medium"})
    assert status == 400
    assert json.loads(body)["code"] == "mixed_script"
    status, _headers, body = request(base, "/api/tts", {"text": "Hello.", "voice": "en_US-joe-medium", "speaker": 0})
    assert status == 400
    assert json.loads(body)["code"] == "speaker_not_allowed"
    status, _headers, body = request(
        base, "/api/tts", {"text": "こんにちは。", "language": "ja", "speaker": "female"}
    )
    assert status == 200
    assert engine.requests[-1] == ("ja", "ja_JP-hi_fi_captain-medium", 0)
    assert engine.calls[0] != "Hello."
    status, _headers, body = request(base, "/api/voices")
    payload = json.loads(body)
    ids = {item["voice"] for item in payload["voices"]}
    assert "en_US-lessac-medium" not in ids
    assert {"zh_CN-chaowen-medium", "en_US-joe-medium", "fr_FR-siwis-medium", "ja_JP-hi_fi_captain-medium", "ko_KR-kss-medium"} <= ids
    assert all("url" not in item for item in payload["voices"])
    assert engine.calls.count("こんにちは。") == 1


def test_gender_is_metadata_not_a_request_field(server):
    from piper_zh.catalog import BY_ID, language_rows

    rows = {item["language"]: item for item in language_rows()}
    assert rows["zh"]["verifiedGenders"] == ["female"]
    assert rows["zh"]["missingGenders"] == ["male"]
    assert rows["zh"]["defaultVoice"] == "zh_CN-chaowen-medium"
    assert BY_ID["zh_CN-chaowen-medium"].gender == "unknown"
    assert BY_ID["zh_CN-xiao_ya-medium"].gender == "female"
    assert BY_ID["zh_CN-xiao_ya-medium"].phoneme_type == "pinyin"
    assert BY_ID["zh_CN-xiao_ya-medium"].license_class == "noncommercial"
    assert rows["en"]["verifiedGenders"] == ["female", "male"]
    assert rows["en"]["missingGenders"] == []
    assert rows["en"]["defaultVoice"] == "en_US-joe-medium"
    assert BY_ID["en_US-joe-medium"].gender == "unknown"
    assert BY_ID["en_US-ljspeech-medium"].gender == "female"
    assert BY_ID["en_US-norman-medium"].gender == "male"
    assert rows["ja"]["verifiedGenders"] == ["female", "male"]
    assert BY_ID["ja_JP-hi_fi_captain-medium"].speakers == {"female": 0, "male": 1}
    assert rows["ko"]["verifiedGenders"] == ["female"]
    assert rows["ko"]["missingGenders"] == ["male"]
    assert "不能用变调" in rows["ko"]["gap"]
    _httpd, engine, base = server
    status, _headers, body = request(base, "/api/tts", {"text": "Hello.", "language": "en", "gender": "female"})
    assert status == 400
    assert json.loads(body)["code"] == "bad_request"
    assert engine.calls == []
    status, _headers, body = request(base, "/api/voices")
    payload = json.loads(body)
    ko = next(item for item in payload["languages"] if item["language"] == "ko")
    assert ko["missingGenders"] == ["male"]
    zh = next(item for item in payload["voices"] if item["voice"] == "zh_CN-xiao_ya-medium")
    assert zh["gender"] == "female"
    assert zh["licenseClass"] == "noncommercial"
    assert "url" not in zh


def test_pocket_engine_is_opt_in_and_rejects_unsupported_languages(server):
    from piper_zh.engine import Synthesis

    class FakePocket:
        def __init__(self) -> None:
            self.calls = []

        def status(self) -> dict:
            return {"installed": True, "prepared": False, "modelReady": False, "languages": ["english"]}

        def voices(self) -> dict:
            return {"engine": "pocket", "voices": [{"voice": "alba", "language": "english", "gender": "unknown"}]}

        def synthesize(self, text: str, language: str, voice: str) -> Synthesis:
            self.calls.append((text, language, voice))
            return Synthesis(
                wav=tone_wav(rate=24000),
                sample_rate=24000,
                duration_seconds=0.4,
                synth_seconds=0.05,
                phoneme_type="pocket",
                model_id=voice,
                language=language,
                engine_header="Pocket-TTS",
            )

    httpd, engine, base = server
    httpd.service_state.pocket = FakePocket()
    status, headers, body = request(base, "/api/tts", {"engine": "pocket", "text": "Hello.", "voice": "alba"})
    assert status == 200
    assert headers["X-Engine"] == "Pocket-TTS"
    assert headers["X-Sample-Rate"] == "24000"
    assert httpd.service_state.pocket.calls == [("Hello.", "english", "alba")]
    assert engine.calls == []
    status, _headers, body = request(base, "/api/tts", {"text": "你好。"})
    assert status == 200
    assert engine.calls == ["你好。"]
    status, _headers, body = request(base, "/api/tts", {"engine": "pocket", "text": "你好。", "language": "zh"})
    assert status == 400
    assert json.loads(body)["code"] == "unsupported_language"
    status, _headers, body = request(base, "/api/tts", {"engine": "pocket", "text": "Hello.", "voice": "hf://kyutai/tts-voices/x.wav"})
    assert status == 400
    assert json.loads(body)["code"] == "unknown_voice"
    status, _headers, body = request(base, "/api/tts", {"engine": "other", "text": "Hello."})
    assert status == 400
    assert json.loads(body)["code"] == "bad_engine"
    status, _headers, body = request(base, "/api/voices?engine=pocket")
    assert status == 200
    assert json.loads(body)["voices"][0]["voice"] == "alba"


def test_voice_cache_drops_the_oldest_and_stays_serial():
    from piper_zh.catalog import BY_ID
    from piper_zh.engine import Synthesis, VoicePool

    created: list[str] = []

    class Stub:
        def __init__(self, voice_id: str) -> None:
            self.ready = True
            self.voice_id = voice_id

        def synthesize(self, text: str, speaker_id: int | None = None) -> Synthesis:
            return Synthesis(
                wav=tone_wav(),
                sample_rate=22050,
                duration_seconds=0.4,
                synth_seconds=0.01,
                phoneme_type="espeak",
                model_id=self.voice_id,
                language=BY_ID[self.voice_id].language,
                speaker_id=speaker_id,
            )

    def loader(spec):
        created.append(spec.voice_id)
        return Stub(spec.voice_id)

    pool = VoicePool(cache_limit=2, loader=loader)
    pool.synthesize("Hello.", voice="en_US-joe-medium")
    pool.synthesize("Bonjour.", voice="fr_FR-siwis-medium")
    pool.synthesize("안녕하세요.", voice="ko_KR-kss-medium")
    assert created == ["en_US-joe-medium", "fr_FR-siwis-medium", "ko_KR-kss-medium"]
    assert list(pool._engines) == ["fr_FR-siwis-medium", "ko_KR-kss-medium"]
    pool.synthesize("Hello again.", voice="en_US-joe-medium")
    assert created[-1] == "en_US-joe-medium"
    assert "fr_FR-siwis-medium" not in pool._engines
