"""Loopback HTTP server for one already-loaded Piper voice."""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .engine import MAX_TEXT_CHARS, DEFAULT_G2P_DIR, DEFAULT_HF_HOME, DEFAULT_MODEL, PiperEngine

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
STATIC_FILES = {
    "/": "compare.html",
    "/piper-compare.html": "compare.html",
    "/piper-compare.js": "compare.js",
    "/piper-compare.css": "compare.css",
    "/piper-compare-logic.mjs": "compare-logic.mjs",
}
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}
MAX_BODY = 65_536
SYNTH_TIMEOUT_SECONDS = 180


class ServiceState:
    def __init__(self, engine, port: int) -> None:
        self.engine = engine
        self.port = port
        self._lock = threading.Lock()
        self.busy = False

    def origins(self) -> set[str]:
        return {
            f"http://127.0.0.1:{self.port}",
            f"http://localhost:{self.port}",
            "http://127.0.0.1:8787",
            "http://localhost:8787",
        }

    def try_begin(self) -> bool:
        with self._lock:
            if self.busy:
                return False
            self.busy = True
            return True

    def finish(self) -> None:
        with self._lock:
            self.busy = False


def _static_path(url_path: str) -> Path | None:
    name = STATIC_FILES.get(url_path)
    if name is None or "/" in name or name.startswith("."):
        return None
    path = (STATIC_DIR / name).resolve()
    if STATIC_DIR.resolve() not in path.parents or not path.is_file():
        return None
    return path


def make_handler(state: ServiceState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args) -> None:
            print(f"[piper-zh] {self.address_string()} {fmt % args}")

        def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
            origin = self.headers.get("Origin")
            if origin in state.origins():
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header(
                    "Access-Control-Expose-Headers",
                    "X-Audio-Duration, X-Synth-Seconds, X-RTF, X-Sample-Rate, X-Engine, X-Model, X-Phoneme-Type, X-Streaming",
                )
            if extra:
                for key, value in extra.items():
                    self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: dict, extra: dict | None = None) -> None:
            self._send(
                status,
                json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
                extra,
            )

        def _guard(self) -> bool:
            host = self.headers.get("Host", "")
            allowed = {f"127.0.0.1:{state.port}", f"localhost:{state.port}"}
            if host not in allowed:
                self._json(403, {"error": "只接受本机回环地址。"})
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin not in state.origins():
                self._json(403, {"error": "这个来源不能调用 Piper 服务。"})
                return False
            return True

        def do_OPTIONS(self) -> None:  # noqa: N802
            if not self._guard():
                return
            path = urlparse(self.path).path
            if path not in {"/api/tts", "/api/health"}:
                self._json(404, {"error": "没有这个接口。"})
                return
            self.send_response(204)
            origin = self.headers.get("Origin")
            if origin in state.origins():
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Content-Length", "0")
            self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
            self.end_headers()

        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_GET(self) -> None:  # noqa: N802
            if not self._guard():
                return
            path = urlparse(self.path).path
            if path == "/api/health":
                payload = state.engine.status()
                payload["busy"] = state.busy
                payload["port"] = state.port
                self._json(200 if payload.get("modelReady") else 200, payload)
                return
            static = _static_path(path)
            if static is None:
                self._json(404, {"error": "没有这个页面。"})
                return
            body = static.read_bytes()
            self._send(200, body, MIME.get(static.suffix, "application/octet-stream"))

        def do_POST(self) -> None:  # noqa: N802
            if not self._guard():
                return
            if urlparse(self.path).path != "/api/tts":
                self._json(404, {"error": "合成接口是 POST /api/tts。"})
                return
            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("application/json"):
                self._json(415, {"error": "请发送 application/json。"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json(400, {"error": "Content-Length 不合法。"})
                return
            if length <= 0 or length > MAX_BODY:
                self._json(413, {"error": "请求体过大或为空。"})
                return
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"error": "JSON 无法解析。"})
                return
            if not isinstance(payload, dict) or set(payload) != {"text"}:
                self._json(400, {"error": "只接受 {\"text\": \"...\"}。不能通过请求指定模型、路径或命令。"})
                return
            text = payload["text"]
            if not isinstance(text, str) or "\x00" in text:
                self._json(400, {"error": "text 必须是不含空字符的字符串。"})
                return
            text = text.strip()
            if not text:
                self._json(400, {"error": "请输入要朗读的文本。"})
                return
            if len(text) > MAX_TEXT_CHARS:
                self._json(400, {"error": f"文本不能超过 {MAX_TEXT_CHARS} 个字符。"})
                return
            if not state.engine.ready:
                self._json(503, {"error": state.engine.error or "模型还没准备好。", "modelReady": False})
                return
            if not state.try_begin():
                self._json(429, {"error": "正在合成另一段，请等这一段结束后再试。"}, {"Retry-After": "2"})
                return

            holder: dict = {}
            finished = threading.Event()

            def work() -> None:
                try:
                    holder["result"] = state.engine.synthesize(text)
                except Exception as exc:  # noqa: BLE001
                    holder["error"] = exc
                finally:
                    finished.set()
                    state.finish()

            threading.Thread(target=work, daemon=True).start()
            if not finished.wait(SYNTH_TIMEOUT_SECONDS):
                self._json(504, {"error": "整段合成超过 180 秒，已停止等待。模型仍可能在后台收尾，请稍后再试。"})
                return
            if "error" in holder:
                message = str(holder["error"])[:500]
                self._json(500, {"error": message})
                return
            result = holder["result"]
            if result.duration_seconds <= 0:
                self._json(500, {"error": "音频时长无效。"})
                return
            rtf = result.synth_seconds / result.duration_seconds
            self._send(
                200,
                result.wav,
                "audio/wav",
                {
                    "X-Audio-Duration": f"{result.duration_seconds:.6f}",
                    "X-Synth-Seconds": f"{result.synth_seconds:.6f}",
                    "X-RTF": f"{rtf:.6f}",
                    "X-Sample-Rate": str(result.sample_rate),
                    "X-Engine": "Piper-zh",
                    "X-Model": result.model_id,
                    "X-Phoneme-Type": result.phoneme_type,
                    "X-Streaming": "full-wav",
                },
            )

    return Handler


def create_server(engine, host: str = "127.0.0.1", port: int = 8791) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Piper 服务只能绑定回环地址。")
    state_port = port
    handler = make_handler  # assigned after we know the real port when port is 0

    class _Server(ThreadingHTTPServer):
        allow_reuse_address = True

    # Bind first when port is 0 so the host check uses the real port.
    provisional = ServiceState(engine, port or 0)
    httpd = _Server((host, port), make_handler(provisional))
    actual_port = int(httpd.server_address[1])
    if actual_port != provisional.port:
        httpd.RequestHandlerClass = make_handler(ServiceState(engine, actual_port))
    httpd.state = httpd.RequestHandlerClass  # type: ignore[attr-defined]
    # The handler closes over the ServiceState instance created above. Rebuild
    # so Host checks and CORS use the port the OS actually assigned.
    bound = ServiceState(engine, actual_port)
    httpd.RequestHandlerClass = make_handler(bound)
    httpd.service_state = bound  # type: ignore[attr-defined]
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local Mandarin Piper HTTP service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--g2p-dir", type=Path, default=DEFAULT_G2P_DIR)
    parser.add_argument("--hf-home", type=Path, default=None)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        print("拒绝绑定非回环地址。")
        return 2
    engine = PiperEngine(
        model_path=args.model,
        g2p_dir=args.g2p_dir,
        hf_home=args.hf_home or DEFAULT_HF_HOME,
        device=args.device,
    )
    try:
        engine.load()
        print(json.dumps({"modelReady": True, "modelId": engine.model_id, "device": engine.device}, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"modelReady": False, "error": str(exc)}, ensure_ascii=False))
    httpd = create_server(engine, args.host, args.port)
    port = httpd.service_state.port  # type: ignore[attr-defined]
    state_path = Path(__file__).resolve().parents[1] / "service-state.json"
    state_path.write_text(
        json.dumps(
            {
                "pid": os_pid(),
                "port": port,
                "url": f"http://127.0.0.1:{port}/piper-compare.html",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Piper zh http://127.0.0.1:{port}/piper-compare.html")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        httpd.server_close()
    return 0


def os_pid() -> int:
    import os

    return os.getpid()


# Imported by tests that want a custom engine.
ServerFactory = Callable[[object, str, int], ThreadingHTTPServer]
