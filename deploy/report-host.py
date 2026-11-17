"""Print CPU, memory, disk, and whether 3080/8080 are listening. Read-only."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def _meminfo() -> dict[str, int]:
    found: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", 1)
        found[key] = int(raw.strip().split()[0])
    return found


def _listening_ports() -> set[int]:
    ports: set[int] = set()
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        path = Path(name)
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()[1:]
        for line in lines:
            local, state = line.split()[1:3]
            if state != "0A":
                continue
            ports.add(int(local.split(":")[1], 16))
    return ports


def main() -> int:
    memory = _meminfo()
    flags: set[str] = set()
    for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("flags"):
            flags.update(line.split(":", 1)[1].split())
            break
    usage = shutil.disk_usage("/")
    listening = _listening_ports()
    glibc = os.confstr("CS_GNU_LIBC_VERSION") if hasattr(os, "confstr") else None
    print(
        json.dumps(
            {
                "logicalCpus": os.cpu_count(),
                "glibc": glibc,
                "avx2": "avx2" in flags,
                "fma": "fma" in flags,
                "f16c": "f16c" in flags,
                "memTotalKiB": memory.get("MemTotal"),
                "memAvailableKiB": memory.get("MemAvailable"),
                "swapTotalKiB": memory.get("SwapTotal"),
                "diskFreeBytes": usage.free,
                "listening3080": 3080 in listening,
                "listening8080": 8080 in listening,
                "note": "只读。没有连接这两个端口，也没有改任何服务。",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
