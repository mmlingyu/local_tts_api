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
        self.entered = threading.Event()
        self.release = threading.Event()

    def synthesize(self, text: str):
        from piper_zh.engine import Synthesis

        self.calls.append(text)
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
            model_id="zh_CN-chaowen-medium",
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
