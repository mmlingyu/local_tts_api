"""Loopback HTTP server for one already-loaded Piper voice."""

from __future__ import annotations

import argparse
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from .catalog import RequestError, inventory, language_rows, parse_tts_fields
from .engine import DEFAULT_G2P_DIR, DEFAULT_HF_HOME, DEFAULT_MODEL, VoicePool

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
    def __init__(self, engine, port: int, pocket=None, phonon=None, api_token: str = "", extra_origins: str = "") -> None:
        self.engine = engine
        self.port = port
        self.pocket = pocket
        self.phonon = phonon
        self.api_token = api_token.strip()
        self.extra_origins = extra_origins
        self._lock = threading.Lock()
        self.busy = False

    def origins(self) -> set[str]:
        found = {
            f"http://127.0.0.1:{self.port}",
            f"http://localhost:{self.port}",
            "http://127.0.0.1:8787",
            "http://localhost:8787",
            "http://127.0.0.1:8133",
            "http://localhost:8133",
        }
        for item in self.extra_origins.split(","):
            origin = item.strip()
            if not origin or origin in {"*", "null"} or "*" in origin:
                continue
            if origin.startswith(("http://", "https://")) and "\n" not in origin:
                found.add(origin)
        return found

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
                    "X-Audio-Duration, X-Synth-Seconds, X-RTF, X-Audio-Peak, X-Sample-Rate, X-Engine, X-Model, X-Phoneme-Type, X-Streaming, X-Language, X-Voice, X-Voice-ID, X-Speaker-Id",
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

        def _guard(self, require_token: bool = True) -> bool:
            host = self.headers.get("Host", "")
            allowed = {f"127.0.0.1:{state.port}", f"localhost:{state.port}"}
            if host not in allowed:
                self._json(403, {"error": "只接受本机回环地址。"})
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin not in state.origins():
                self._json(403, {"error": "这个来源不能调用 Piper 服务。"})
                return False
            if require_token and state.api_token and not self._bearer_ok():
                self._json(401, {"error": "需要 Bearer token。Host 和来源检查仍然有效。", "code": "unauthorized"})
                return False
            return True

        def _bearer_ok(self) -> bool:
            try:
                presented = self.headers.get("Authorization", "").encode("utf-8")
                expected = f"Bearer {state.api_token}".encode("utf-8")
            except UnicodeError:
                return False
            return hmac.compare_digest(presented, expected)

        def do_OPTIONS(self) -> None:  # noqa: N802
            if not self._guard(require_token=False):
                return
            path = urlparse(self.path).path
            if path not in {"/api/tts", "/api/health", "/api/voices"}:
                self._json(404, {"error": "没有这个接口。"})
                return
            self.send_response(204)
            origin = self.headers.get("Origin")
            if origin in state.origins():
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
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
                pocket_status = state.pocket.status() if state.pocket is not None else {"installed": False}
                phonon_status = state.phonon.status() if state.phonon is not None else {"runtimePresent": False, "inferenceReady": False}
                payload["apiVersion"] = "1.2.0"
                payload["engines"] = {
                    "piper": {
                        "serviceVersion": payload.get("serviceVersion"),
                        "modelReady": payload.get("modelReady"),
                        "loadedVoiceIds": payload.get("loadedVoiceIds", []),
                    },
                    "pocket": pocket_status,
                    "phonon": phonon_status,
                }
                payload["access"] = {
                    "bind": "loopback",
                    "authorization": "bearer" if state.api_token else "loopback-only",
                    "tokenConfigured": bool(state.api_token),
                    "origins": sorted(state.origins()),
                }
                self._json(200, payload)
                return
            if path == "/api/voices":
                asked = (parse_qs(urlparse(self.path).query).get("engine") or ["piper"])[0]
                if asked == "pocket":
                    if state.pocket is None:
                        self._json(200, {"engine": "pocket", "voices": [], "languages": []})
                        return
                    self._json(200, state.pocket.voices())
                    return
                if asked == "phonon":
                    if state.phonon is None:
                        self._json(200, {"engine": "phonon", "voices": [], "count": 0, "runtimePresent": False})
                        return
                    self._json(200, state.phonon.voices())
                    return
                if asked == "all":
                    piper_status = state.engine.status()
                    self._json(
                        200,
                        {
                            "piper": {
                                "voices": piper_status.get("voices") or inventory(),
                                "languages": piper_status.get("languages") or language_rows(),
                            },
                            "pocket": state.pocket.voices() if state.pocket is not None else {"engine": "pocket", "voices": []},
                            "phonon": state.phonon.voices() if state.phonon is not None else {"engine": "phonon", "voices": []},
                        },
                    )
                    return
                if asked != "piper":
                    self._json(400, {"error": "engine 只能是 piper、phonon、pocket 或 all。", "code": "bad_engine"})
                    return
                status_payload = state.engine.status()
                voices = status_payload.get("voices")
                languages = status_payload.get("languages")
                if voices is None:
                    voices = inventory()
                    languages = language_rows()
                self._json(
                    200,
                    {
                        "voices": voices,
                        "languages": languages,
                        "cacheLimit": status_payload.get("cacheLimit", 2),
                        "loadedVoiceIds": status_payload.get("loadedVoiceIds", []),
                        "note": "列表来自白名单。没有下载地址字段，页面不能提交远程模型。",
                    },
                )
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
            try:
                request = parse_tts_fields(payload)
            except RequestError as exc:
                self._json(exc.status, {"error": exc.message, "code": exc.code})
                return
            text, language, voice, speaker = request.text, request.language, request.voice, request.speaker
            if request.engine == "piper" and not state.engine.ready:
                self._json(503, {"error": state.engine.error or "模型还没准备好。", "modelReady": False})
                return
            if not state.try_begin():
                self._json(429, {"error": "正在合成另一段，请等这一段结束后再试。"}, {"Retry-After": "2"})
                return

            holder: dict = {}
            finished = threading.Event()

            def work() -> None:
                try:
                    _release_other_engines(state, request.engine)
                    if request.engine == "pocket":
                        if state.pocket is None:
                            raise RequestError("Pocket 没有接入这个进程。", 503, "pocket_not_ready")
                        holder["result"] = state.pocket.synthesize(text, language, voice, request.variant)
                    elif request.engine == "phonon":
                        if state.phonon is None:
                            raise RequestError("Phonon 没有接入这个进程。", 503, "runtime_not_ready")
                        holder["result"] = state.phonon.synthesize(text, voice)
                    else:
                        holder["result"] = state.engine.synthesize(
                            text, language=language, voice=voice, speaker=speaker
                        )
                except RequestError as exc:
                    holder["request_error"] = exc
                except Exception as exc:  # noqa: BLE001
                    holder["error"] = exc
                finally:
                    finished.set()
                    state.finish()

            threading.Thread(target=work, daemon=True).start()
            if not finished.wait(SYNTH_TIMEOUT_SECONDS):
                self._json(504, {"error": "整段合成超过 180 秒，已停止等待。模型仍可能在后台收尾，请稍后再试。"})
                return
            if "request_error" in holder:
                exc = holder["request_error"]
                self._json(exc.status, {"error": exc.message, "code": exc.code})
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
            extra = {
                "X-Audio-Duration": f"{result.duration_seconds:.6f}",
                "X-Synth-Seconds": f"{result.synth_seconds:.6f}",
                "X-RTF": f"{rtf:.6f}",
                "X-Sample-Rate": str(result.sample_rate),
                "X-Engine": getattr(result, "engine_header", "Piper-zh"),
                "X-Model": result.model_id,
                "X-Phoneme-Type": result.phoneme_type,
                "X-Streaming": "full-wav",
                "X-Language": getattr(result, "language", language),
                "X-Voice": getattr(result, "voice_name", None) or result.model_id,
            }
            speaker_header = getattr(result, "speaker_id", speaker)
            if speaker_header is not None:
                extra["X-Speaker-Id"] = str(speaker_header)
            peak = getattr(result, "peak", None)
            if peak is not None:
                extra["X-Audio-Peak"] = f"{peak:.9f}"
            voice_id = getattr(result, "voice_id", None)
            if voice_id:
                extra["X-Voice-ID"] = voice_id
            self._send(200, result.wav, "audio/wav", extra)

    return Handler


def _release_other_engines(state: ServiceState, active: str) -> None:
    """Keep only the engine that is about to run. The 3.6GiB host cannot hold all three."""
    if active != "piper":
        release = getattr(state.engine, "release_all", None)
        if release is not None:
            release()
    if active != "pocket" and state.pocket is not None:
        close = getattr(state.pocket, "close", None)
        if close is not None:
            close()
    if active != "phonon" and state.phonon is not None:
        close = getattr(state.phonon, "close", None)
        if close is not None:
            close()


def create_server(
    engine,
    host: str = "127.0.0.1",
    port: int = 8791,
    pocket=None,
    phonon=None,
    api_token: str = "",
    extra_origins: str = "",
) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Piper 服务只能绑定回环地址。")
    if port in {80, 443, 3080, 8080}:
        raise ValueError(f"端口 {port} 留给已有服务。")
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
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    pocket_root = repo_root / "pocket-tts-service"
    phonon_root = repo_root / "phonon"
    if str(pocket_root) not in sys.path:
        sys.path.insert(0, str(pocket_root))
    if str(phonon_root) not in sys.path:
        sys.path.insert(0, str(phonon_root))
    if pocket is None:
        from pocket_local.bridge import PocketBridge

        pocket = PocketBridge()
    if phonon is None:
        from phonon_bridge import PhononBridge

        phonon = PhononBridge()
    bound = ServiceState(
        engine,
        actual_port,
        pocket=pocket,
        phonon=phonon,
        api_token=api_token,
        extra_origins=extra_origins,
    )
    httpd.RequestHandlerClass = make_handler(bound)
    httpd.service_state = bound  # type: ignore[attr-defined]
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local Piper HTTP service for the zh/en/ja/ko/fr whitelist")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--g2p-dir", type=Path, default=DEFAULT_G2P_DIR)
    parser.add_argument("--hf-home", type=Path, default=None)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--cache-limit", type=int, default=2)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        print("拒绝绑定非回环地址。")
        return 2
    if args.port in {80, 443, 3080, 8080}:
        print("拒绝占用 80、443、3080 或 8080。这些端口留给已有服务。")
        return 2
    if args.model.name != DEFAULT_MODEL.name:
        print("拒绝加载白名单以外的模型文件名。")
        return 2
    import os
    import sys

    token = os.environ.get("TTS_API_TOKEN", "")
    extra_origins = os.environ.get("TTS_EXTRA_ORIGINS", "")
    public_base = os.environ.get("TTS_PUBLIC_BASE", "")
    deploy_root = Path(__file__).resolve().parents[2] / "deploy"
    if str(deploy_root) not in sys.path:
        sys.path.insert(0, str(deploy_root))
    from access_policy import AccessConfigError, compile_access

    try:
        compile_access(
            bind_host=args.host,
            port=args.port,
            extra_origins=extra_origins,
            api_token=token,
            public_base=public_base,
        )
    except AccessConfigError as exc:
        print(str(exc))
        return 2
    engine = VoicePool(
        device=args.device,
        cache_limit=args.cache_limit,
        g2p_dir=args.g2p_dir,
        hf_home=args.hf_home or DEFAULT_HF_HOME,
        chinese_model=args.model,
    )
    print(json.dumps({"modelReady": engine.status()["modelReady"], "loadedVoiceIds": [], "device": engine.device, "cacheLimit": engine.cache_limit}, ensure_ascii=False))
    httpd = create_server(
        engine,
        args.host,
        args.port,
        api_token=token,
        extra_origins=extra_origins,
    )
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
        pocket_worker = getattr(httpd, "service_state", None)
        if pocket_worker is not None and getattr(pocket_worker, "pocket", None) is not None:
            pocket_worker.pocket.close()
        if pocket_worker is not None and getattr(pocket_worker, "phonon", None) is not None:
            pocket_worker.phonon.close()
        httpd.server_close()
    return 0


def os_pid() -> int:
    import os

    return os.getpid()


# Imported by tests that want a custom engine.
ServerFactory = Callable[[object, str, int], ThreadingHTTPServer]
