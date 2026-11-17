"""Loopback page for trying the Piper and Phonon HTTPS API.

The process listens only on 127.0.0.1 or localhost. It forwards the token the
page just typed to the base URL the user typed, then drops it. TLS verification
stays on. This file does not read a saved token and does not log Authorization.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import socket
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
}
ALLOWED = {
    ("GET", "/api/health"),
    ("GET", "/api/voices"),
    ("POST", "/api/tts"),
}
VOICE_ENGINES = {"piper", "phonon", "all"}
MAX_REQUEST = 65_536
MAX_UPSTREAM = 8 * 1024 * 1024
TIMEOUT_SECONDS = 200
_BEARER = re.compile(r"(?i)bearer\s+\S+")
_SYNTH = threading.Lock()
SAFE_HEADERS = {
    "content-type",
    "retry-after",
    "x-audio-duration",
    "x-synth-seconds",
    "x-rtf",
    "x-sample-rate",
    "x-engine",
    "x-model",
    "x-phoneme-type",
    "x-streaming",
    "x-language",
    "x-voice",
    "x-voice-id",
    "x-speaker-id",
    "x-audio-peak",
}


class TargetError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def redact(text: str, token: str = "") -> str:
    cleaned = _BEARER.sub("Bearer [redacted]", text)
    if token:
        cleaned = cleaned.replace(token, "[redacted]")
    return cleaned


def ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise RuntimeError("TLS 校验必须保持开启。")
    return context


def validate_base(raw: object) -> urllib.parse.SplitResult:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 300:
        raise TargetError("请填写目标服务地址。")
    if any(char in raw for char in "\r\n\x00"):
        raise TargetError("地址含有非法字符。")
    parts = urllib.parse.urlsplit(raw.strip())
    if parts.username or parts.password or "@" in parts.netloc:
        raise TargetError("地址不能包含用户名或密码。")
    if parts.fragment:
        raise TargetError("地址不能带 # 片段。")
    if parts.query:
        raise TargetError("基址不要带查询字符串。")
    if parts.path not in {"", "/"}:
        raise TargetError("基址不要带路径，只填到主机为止。")
    host = (parts.hostname or "").lower()
    if not host:
        raise TargetError("地址缺少主机名。")
    local = host in {"localhost", "127.0.0.1", "::1"}
    if parts.scheme == "http" and local:
        return parts
    if parts.scheme == "https":
        return parts
    raise TargetError("公网地址必须使用 https。只有本机 localhost 或 127.0.0.1 可以用 http。")


def validate_call(method: object, path: object, query: object) -> tuple[str, str, dict[str, str]]:
    if not isinstance(method, str) or method not in {"GET", "POST"}:
        raise TargetError("方法只能是 GET 或 POST。")
    if not isinstance(path, str) or path not in {"/api/health", "/api/voices", "/api/tts"}:
        raise TargetError("只能请求 /api/health、/api/voices 或 /api/tts。")
    if (method, path) not in ALLOWED:
        raise TargetError("这个方法和路径的组合不允许。")
    params: dict[str, str] = {}
    if query not in (None, {}):
        if path != "/api/voices" or not isinstance(query, dict):
            raise TargetError("只有音色接口可以带 engine 查询。")
        engine = query.get("engine")
        if engine not in VOICE_ENGINES or set(query) != {"engine"}:
            raise TargetError("engine 只能是 piper、phonon 或 all。")
        params["engine"] = engine
    return method, path, params


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        raise TargetError("上游要求跳转。本工具不跟随重定向，因此不会把令牌带到另一个地址。", 502)


def _read_limited(source, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        block = source.read(64 * 1024)
        if not block:
            break
        total += len(block)
        if total > limit:
            raise TargetError("上游响应超过 8 MiB，已停止读取。", 502)
        chunks.append(block)
    return b"".join(chunks)


def _pick_headers(headers) -> dict[str, str]:
    picked = {}
    for key, value in headers.items():
        if key.lower() in SAFE_HEADERS:
            picked[key] = value
    return picked


def _package(status: int, headers, raw: bytes, token: str) -> dict:
    content_type = headers.get("Content-Type", "") if headers is not None else ""
    picked = _pick_headers(headers or {})
    if raw.startswith(b"RIFF") or content_type.lower().startswith("audio/wav"):
        return {
            "ok": 200 <= status < 300,
            "status": status,
            "contentType": content_type,
            "headers": picked,
            "bodyBase64": base64.b64encode(raw).decode("ascii"),
            "json": None,
            "errorText": None,
        }
    text = redact(raw.decode("utf-8", errors="replace"), token)
    parsed = None
    parse_error = False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
        parse_error = True
    return {
        "ok": 200 <= status < 300 and not parse_error,
        "status": status,
        "contentType": content_type,
        "headers": picked,
        "bodyBase64": None,
        "json": parsed,
        "parseError": parse_error,
        "errorText": None if parsed is not None else text[:8000],
    }


def forward(base: str, token: str, method: str, path: str, query: dict[str, str], body: object) -> dict:
    parts = validate_base(base)
    method, path, query = validate_call(method, path, query)
    if token:
        if not isinstance(token, str) or len(token) > 4096 or any(char in token for char in "\r\n\x00"):
            raise TargetError("令牌格式不正确。")
        token = token.strip()
    else:
        token = ""
    data = None
    headers = {"Accept": "application/json, audio/wav", "User-Agent": "local-tts-api-tester"}
    if body is not None:
        if not isinstance(body, dict):
            raise TargetError("合成正文必须是 JSON 对象。")
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if len(data) > MAX_REQUEST:
            raise TargetError("请求体超过 65536 字节。", 413)
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = "Bearer " + token
    url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, urllib.parse.urlencode(query), ""))
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=ssl_context()))
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = _read_limited(response, MAX_UPSTREAM)
            return _package(getattr(response, "status", 200), response.headers, raw, token)
    except TargetError:
        raise
    except urllib.error.HTTPError as exc:
        raw = _read_limited(exc, 256 * 1024)
        return _package(exc.code, exc.headers, raw, token)
    except ssl.SSLError as exc:
        raise TargetError("证书校验失败。本工具不会改为不校验证书。" + redact(str(exc), token), 502) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise TargetError("等待超过 200 秒，已停止等待。这不能取消服务端可能仍在进行的合成。", 504) from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ssl.SSLError):
            raise TargetError("证书校验失败。本工具不会改为不校验证书。", 502) from exc
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise TargetError("等待超过 200 秒，已停止等待。这不能取消服务端可能仍在进行的合成。", 504) from exc
        raise TargetError("无法连接目标服务。" + redact(str(reason), token), 502) from exc


def create_server(host: str = "127.0.0.1", port: int = 8133) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("只能绑定 127.0.0.1 或 localhost。")

    class _Server(ThreadingHTTPServer):
        allow_reuse_address = False

    provisional = _Server((host, port), make_handler(0))
    actual = int(provisional.server_address[1])
    provisional.RequestHandlerClass = make_handler(actual)
    provisional.tester_port = actual  # type: ignore[attr-defined]
    return provisional


def make_handler(port: int) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:
            print("[api-tester]", redact(fmt % args))

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: dict) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _guard(self, require_origin: bool) -> bool:
            host = self.headers.get("Host", "")
            if host not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                self._json(403, {"error": "只接受本机地址。"})
                return False
            origin = self.headers.get("Origin")
            allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
            if origin is None:
                if require_origin:
                    self._json(403, {"error": "缺少本机来源。"})
                    return False
                return True
            if origin not in allowed:
                self._json(403, {"error": "这个来源不能使用本地自测页。"})
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802
            if not self._guard(False):
                return
            path = urllib.parse.urlsplit(self.path).path
            item = STATIC.get(path)
            if item is None:
                self._json(404, {"error": "没有这个页面。"})
                return
            name, content_type = item
            file_path = (ROOT / name).resolve()
            if file_path.parent != ROOT or not file_path.is_file():
                self._json(404, {"error": "没有这个页面。"})
                return
            self._send(200, file_path.read_bytes(), content_type)

        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_OPTIONS(self) -> None:  # noqa: N802
            if not self._guard(True):
                return
            self.send_response(204)
            origin = self.headers.get("Origin", "")
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if not self._guard(True):
                return
            if urllib.parse.urlsplit(self.path).path != "/proxy":
                self._json(404, {"error": "没有这个接口。"})
                return
            if not (self.headers.get("Content-Type", "").startswith("application/json")):
                self._json(415, {"error": "请发送 application/json。"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json(400, {"error": "Content-Length 不合法。"})
                return
            if length <= 0 or length > MAX_REQUEST:
                self._json(413, {"error": "请求体过大或为空。"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"error": "JSON 无法解析。"})
                return
            if not isinstance(payload, dict):
                self._json(400, {"error": "请求必须是 JSON 对象。"})
                return
            allowed_keys = {"base", "token", "method", "path", "query", "body"}
            if not set(payload) <= allowed_keys or "base" not in payload or "method" not in payload or "path" not in payload:
                self._json(400, {"error": "代理字段不合法。"})
                return
            token = payload.get("token") or ""
            method = payload.get("method")
            path = payload.get("path")
            held = False
            try:
                if method == "POST" and path == "/api/tts":
                    held = _SYNTH.acquire(blocking=False)
                    if not held:
                        self._json(429, {"error": "本地已有一段合成在等待上游。请等这一段结束后再试。这不是上游的 Retry-After。"})
                        return
                result = forward(
                    payload.get("base"),
                    token if isinstance(token, str) else "",
                    method,
                    path,
                    payload.get("query"),
                    payload.get("body"),
                )
            except TargetError as exc:
                self._json(exc.status, {"error": redact(exc.message, token if isinstance(token, str) else "")})
                return
            finally:
                if held:
                    _SYNTH.release()
            self._json(200, result)

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local loopback tester for the TTS HTTPS API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8133)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        print("只能绑定 127.0.0.1 或 localhost。")
        return 2
    try:
        httpd = create_server(args.host, args.port)
    except OSError as exc:
        print(f"端口 {args.port} 无法监听：{exc.strerror or exc}。请换一个端口，例如 python app.py --host 127.0.0.1 --port 8134。不会改动已有的语音服务。")
        return 1
    port = httpd.tester_port  # type: ignore[attr-defined]
    print(f"本地自测页 http://127.0.0.1:{port}/")
    print("令牌只存在于浏览器这次打开的页面内存里。本进程不保存、不写入日志。")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
