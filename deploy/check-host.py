"""Read-only host check used before installation.

Exits 2 when this CPU lacks AVX2, FMA, or F16C, or when the chosen TTS port
is one of the ports already used by other local services. It does not connect
to those services and does not change them.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FORBIDDEN_PORTS = {80, 443, 3080, 8080}
REQUIRED_FLAGS = ("avx2", "fma", "f16c")


def cpu_flags() -> set[str]:
    flags: set[str] = set()
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.is_file():
        return flags
    for line in cpuinfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("flags") or line.startswith("Features"):
            flags.update(line.split(":", 1)[1].lower().split())
    return flags


def listening_ports() -> set[int]:
    ports: set[int] = set()
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        path = Path(name)
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines()[1:]:
            local, state = line.split()[1:3]
            if state != "0A":
                continue
            ports.add(int(local.rsplit(":", 1)[1], 16))
    return ports


def meminfo() -> dict[str, int]:
    found: dict[str, int] = {}
    path = Path("/proc/meminfo")
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", 1)
        found[key] = int(raw.strip().split()[0])
    return found


def report(port: int) -> dict:
    flags = cpu_flags()
    memory = meminfo()
    listening = listening_ports()
    missing = [name for name in REQUIRED_FLAGS if name not in flags]
    glibc = os.confstr("CS_GNU_LIBC_VERSION") if hasattr(os, "confstr") else None
    return {
        "logicalCpus": os.cpu_count(),
        "glibc": glibc,
        "flagsPresent": {name: name in flags for name in REQUIRED_FLAGS},
        "missingFlags": missing,
        "memTotalKiB": memory.get("MemTotal"),
        "memAvailableKiB": memory.get("MemAvailable"),
        "swapTotalKiB": memory.get("SwapTotal"),
        "ttsPort": port,
        "portForbidden": port in FORBIDDEN_PORTS,
        "listening3080": 3080 in listening,
        "listening8080": 8080 in listening,
        "note": "只读。没有连接 3080 或 8080，也没有修改这两个端口上的服务。",
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    port = int(os.environ.get("TTS_PORT", "8800"))
    payload = report(port)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["missingFlags"] or payload["portForbidden"]:
        return 2
    if "--require-flags" in args and payload["missingFlags"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
