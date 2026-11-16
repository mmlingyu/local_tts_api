"""Download the official Pocket TTS weights. A page click cannot run this."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pocket_local.catalog import DEFAULT_VARIANT, ready_record

ROOT = Path(__file__).resolve().parents[1]
MARKER = ROOT / "models" / "ready.json"


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare the 18.2M Pocket TTS variant.")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    args = parser.parse_args(argv)
    variant = args.variant.strip()
    if variant != DEFAULT_VARIANT:
        print("只准备 english_18m_2026-10。不会下载约 100M 的 english，也不会下载 6.9M 或 1.9M。")
        return 2
    voice = "alba"
    print("Pocket TTS 代码许可：MIT。")
    print("模型 kyutai/pocket-tts：CC BY 4.0，并且是 Hugging Face gated 仓库。")
    print("请先打开 https://huggingface.co/kyutai/pocket-tts 接受许可，再用 huggingface-cli login。")
    print("不能绕过这个授权。这次只准备", variant, "（18.2M，含 decoder）和内置音色", voice)
    print("load_model 的 language 参数使用这个官方 ID，不是 english。")
    print("不会把 torch 装进 Piper 的虚拟环境。")
    if not args.confirm:
        print("未下载。确认后执行 python -m pocket_local.prepare --confirm --variant english_18m_2026-10")
        return 2
    os.environ["HF_HOME"] = str(ROOT / "models" / "hf-home")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ.pop("HF_HUB_OFFLINE", None)
    try:
        from pocket_tts import TTSModel
    except ImportError as exc:
        print("当前解释器没有 pocket-tts。请使用 pocket-tts-service/.venv。", exc)
        return 2
    try:
        model = TTSModel.load_model(language=variant)
        model.get_state_for_audio_prompt(voice)
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        print(text)
        if "gated" in text.lower() or "401" in text or "restricted" in text.lower():
            print("下载被 Hugging Face 门控拦住。请用已接受许可的账号登录后再执行。")
        return 3
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        json.dumps(ready_record(int(model.sample_rate)), ensure_ascii=False),
        encoding="utf-8",
    )
    print("已准备", variant, "采样率", int(model.sample_rate))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
