"""Reject a CUDA or ROCm PyTorch wheel in the Pocket virtualenv.

pocket-tts 4.0.1 depends on torch>=2.5.0. The wheel on PyPI is the CUDA build.
prepare-pocket.sh installs from the CPU index first. A version such as
``2.5.1+cpu`` with ``torch.version.cuda is None`` is the accepted shape.
"""

from __future__ import annotations


def cpu_build_ok(version: str, cuda_version: str | None) -> tuple[bool, str]:
    if not isinstance(version, str) or not version:
        return False, "没有 torch 版本字符串。"
    lowered = version.lower()
    if "+cu" in lowered or "+rocm" in lowered or "+xpu" in lowered:
        return False, f"{version} 不是 CPU 轮。"
    if cuda_version:
        return False, f"torch.version.cuda={cuda_version}，这不是 CPU 构建。"
    if "+cpu" not in lowered:
        return False, f"{version} 没有 +cpu 后缀。PyPI 上不带后缀的 torch 是 CUDA 轮。"
    return True, "CPU 轮。"


def main() -> int:
    try:
        import torch
    except ImportError:
        print("当前解释器没有 torch。请先按 prepare-pocket.sh 从 CPU 索引安装。")
        return 2
    cuda = getattr(getattr(torch, "version", None), "cuda", None)
    ok, reason = cpu_build_ok(str(torch.__version__), None if cuda in (None, "") else str(cuda))
    print(torch.__version__, reason)
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
