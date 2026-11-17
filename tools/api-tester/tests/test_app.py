"""Proxy, page, and redaction tests. They do not call the production API."""

from __future__ import annotations

import json
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as tester

ROOT = Path(__file__).resolve().parents[1]


def test_base_url_rules():
    assert tester.validate_base("https://124.222.128.61").scheme == "https"
    assert tester.validate_base("http://127.0.0.1:8791").hostname == "127.0.0.1"
    with pytest.raises(tester.TargetError):
        tester.validate_base("https://user:secret@124.222.128.61")
    with pytest.raises(tester.TargetError):
        tester.validate_base("https://124.222.128.61/api/tts#x")
    with pytest.raises(tester.TargetError):
        tester.validate_base("http://124.222.128.61")
    with pytest.raises(tester.TargetError):
        tester.validate_base("https://124.222.128.61/extra")


def test_paths_and_pocket_query_are_limited():
    assert tester.validate_call("GET", "/api/health", None)[1] == "/api/health"
    assert tester.validate_call("GET", "/api/voices", {"engine": "phonon"})[2] == {"engine": "phonon"}
    with pytest.raises(tester.TargetError):
        tester.validate_call("GET", "/api/voices", {"engine": "pocket"})
    with pytest.raises(tester.TargetError):
        tester.validate_call("POST", "/api/health", None)
    with pytest.raises(tester.TargetError):
        tester.validate_call("GET", "/piper-compare.html", None)


def test_redact_removes_bearer_and_token_text():
    hidden = tester.redact("Authorization: Bearer super-secret-value failed", "super-secret-value")
    assert "super-secret-value" not in hidden
    assert "Bearer [redacted]" in hidden


def test_ssl_context_verifies_certificates():
    context = tester.ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "CERT_NONE" not in source
    assert "check_hostname = False" not in source


def test_page_has_empty_token_and_no_storage():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app.js").read_text(encoding="utf-8")
    assert 'value="https://124.222.128.61"' in html
    assert 'id="token"' in html and 'type="password"' in html
    assert 'id="clear-token"' in html
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "尚未连接" in html
    assert "不能把它停掉" in html
    node = subprocess.run(["node", "--check", str(ROOT / "app.js")], capture_output=True, text=True)
    assert node.returncode == 0, node.stderr


class Upstream(BaseHTTPRequestHandler):
    hits = 0
    redirect = False

    def log_message(self, fmt: str, *args) -> None:
        return None

    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        Upstream.hits += 1
        auth = self.headers.get("Authorization", "")
        if self.path.startswith("/api/health"):
            if Upstream.redirect:
                self.send_response(302)
                self.send_header("Location", "https://example.invalid/api/health")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if auth != "Bearer good-token":
                self._send(401, b'{"error":"unauthorized","code":"unauthorized"}', "application/json")
                return
            self._send(200, b'{"ok":true,"apiVersion":"1.2.0"}', "application/json")
            return
        if "redirect" in self.path:
            self.send_response(302)
            self.send_header("Location", "https://example.invalid/api/health")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._send(404, b'{"error":"no"}', "application/json")

    def do_POST(self) -> None:  # noqa: N802
        Upstream.hits += 1
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        wav = b"RIFF" + b"\x00" * 32
        self._send(200, wav, "audio/wav", {"X-Engine": "Piper-zh", "X-Sample-Rate": "22050"})


@pytest.fixture
def servers():
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    proxy = tester.create_server("127.0.0.1", 0)
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    yield upstream, proxy
    proxy.shutdown()
    upstream.shutdown()


def _post(proxy, payload: dict, origin: str | None = None, host: str | None = None):
    port = proxy.tester_port
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"http://127.0.0.1:{port}/proxy", data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Host", host or f"127.0.0.1:{port}")
    if origin is not None:
        request.add_header("Origin", origin)
    else:
        request.add_header("Origin", f"http://127.0.0.1:{port}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_proxy_forwards_health_and_error_without_echoing_token(servers):
    upstream, proxy = servers
    base = f"http://127.0.0.1:{upstream.server_address[1]}"
    status, body = _post(proxy, {"base": base, "token": "good-token", "method": "GET", "path": "/api/health"})
    assert status == 200
    assert body["status"] == 200
    assert body["json"]["ok"] is True
    assert "good-token" not in json.dumps(body)
    status, body = _post(proxy, {"base": base, "token": "bad-token", "method": "GET", "path": "/api/health"})
    assert body["status"] == 401
    assert body["json"]["code"] == "unauthorized"


def test_redirect_is_not_followed(servers):
    upstream, proxy = servers
    Upstream.redirect = True
    before = Upstream.hits
    base = f"http://127.0.0.1:{upstream.server_address[1]}"
    try:
        status, body = _post(proxy, {"base": base, "token": "good-token", "method": "GET", "path": "/api/health"})
    finally:
        Upstream.redirect = False
    assert status == 502
    assert "不跟随重定向" in body["error"]
    assert "good-token" not in body["error"]
    assert Upstream.hits == before + 1


def test_cross_site_origin_and_bad_host_are_rejected(servers):
    _upstream, proxy = servers
    port = proxy.tester_port
    status, body = _post(
        proxy,
        {"base": "https://124.222.128.61", "token": "x", "method": "GET", "path": "/api/health"},
        origin="https://evil.example",
    )
    assert status == 403
    status, body = _post(
        proxy,
        {"base": "https://124.222.128.61", "token": "x", "method": "GET", "path": "/api/health"},
        host=f"evil.example:{port}",
    )
    assert status == 403
    assert "x" not in body["error"]


def test_tts_returns_wav_metadata(servers):
    upstream, proxy = servers
    base = f"http://127.0.0.1:{upstream.server_address[1]}"
    status, body = _post(
        proxy,
        {
            "base": base,
            "token": "good-token",
            "method": "POST",
            "path": "/api/tts",
            "body": {"text": "Hello."},
        },
    )
    assert status == 200
    assert body["headers"]["X-Engine"] == "Piper-zh"
    assert body["headers"]["X-Sample-Rate"] == "22050"
    assert body["bodyBase64"]
    assert "good-token" not in json.dumps(body)


def test_occupied_port_message(capsys):
    holder = tester.create_server("127.0.0.1", 0)
    busy = holder.tester_port
    code = tester.main(["--host", "127.0.0.1", "--port", str(busy)])
    assert code == 1
    captured = capsys.readouterr()
    assert "无法监听" in captured.out
    assert "8134" in captured.out
    holder.server_close()
