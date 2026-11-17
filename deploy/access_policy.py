"""Loopback access rules for a later unified process.

server.py does not import this module yet. The uncommitted local server.py
has not been attached, so these rules are not wired into the running handler.
They exist so a public hostname cannot be enabled by turning Host, CORS, or
auth off.
"""

from __future__ import annotations


class AccessConfigError(ValueError):
    pass


def compile_access(
    *,
    bind_host: str,
    port: int,
    extra_origins: str = "",
    api_token: str = "",
    public_base: str = "",
) -> dict:
    if bind_host not in {"127.0.0.1", "localhost"}:
        raise AccessConfigError(
            "进程只能绑定 127.0.0.1 或 localhost。对外访问由本机反向代理完成，不能改成监听公网地址，也不能关掉 Host 检查。"
        )
    if port in {3080, 8080, 80, 443}:
        raise AccessConfigError(f"端口 {port} 留给已有服务，TTS 不能占用。")
    if not isinstance(port, int) or isinstance(port, bool) or port < 1 or port > 65535:
        raise AccessConfigError("端口不合法。")
    token = api_token.strip()
    base = public_base.strip()
    if base:
        if "*" in base or base in {"*", "null"}:
            raise AccessConfigError("对外地址不能是通配。")
        if not base.startswith(("http://", "https://")):
            raise AccessConfigError("对外地址必须以 http:// 或 https:// 开头。")
        if len(token) < 16:
            raise AccessConfigError("配置了对外地址时必须设置至少 16 个字符的 API token。空 token 不会被当成关闭鉴权。")
    elif token and len(token) < 16:
        raise AccessConfigError("API token 至少 16 个字符。")
    origins = {
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
        "http://127.0.0.1:8787",
        "http://localhost:8787",
    }
    for item in [part.strip() for part in extra_origins.split(",") if part.strip()]:
        if item in {"*", "null"} or "*" in item:
            raise AccessConfigError("不允许通配来源。")
        if not item.startswith(("http://", "https://")) or "\n" in item:
            raise AccessConfigError("额外来源必须是 http 或 https 地址。")
        origins.add(item)
    return {
        "bindHost": bind_host,
        "port": port,
        "allowedHosts": [f"127.0.0.1:{port}", f"localhost:{port}"],
        "origins": sorted(origins),
        "authorization": "bearer" if token else "loopback-only",
        "tokenConfigured": bool(token),
        "publicBase": base or None,
        "wiredIntoServer": False,
    }
