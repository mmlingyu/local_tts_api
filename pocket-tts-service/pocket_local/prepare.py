"""Download the official Pocket TTS weights. A page click cannot run this."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pocket_local.catalog import BUILTIN_VOICES, DEFAULT_VARIANT, PREPARE_COMMAND, prepared_voice_names, ready_record

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
    print("Pocket TTS 代码许可：MIT。")
    print("模型 kyutai/pocket-tts：CC BY 4.0，并且是 Hugging Face gated 仓库。")
    print("若 hf-home 里还没有这个模型，才需要打开 https://huggingface.co/kyutai/pocket-tts 接受许可并 huggingface-cli login。")
    print("已有 18.2M 权重和音色缓存会复用，不会重下整模，也不会重装 torch。")
    print("这次准备", variant, "（18.2M，含 decoder）和", len(BUILTIN_VOICES), "个内置音色：")
    print(", ".join(BUILTIN_VOICES))
    print("load_model 的 language 参数使用这个官方 ID，不是 english。")
    print("不会把 torch 装进 Piper 的虚拟环境。")
    if not args.confirm:
        print("未下载。确认后执行", PREPARE_COMMAND)
        return 2
    os.environ["HF_HOME"] = str(ROOT / "models" / "hf-home")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ.pop("HF_HUB_OFFLINE", None)
    for key in ("HUGGINGFACE_HUB_CACHE", "HF_HUB_CACHE", "TRANSFORMERS_CACHE"):
        os.environ.pop(key, None)
    try:
        from pocket_tts import TTSModel
    except ImportError as exc:
        print("当前解释器没有 pocket-tts。请使用 pocket-tts-service/.venv。", exc)
        return 2
    try:
        model = TTSModel.load_model(language=variant)
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        print(text)
        if "gated" in text.lower() or "401" in text or "restricted" in text.lower():
            print("下载被 Hugging Face 门控拦住。已有缓存不会被这次失败删掉。")
        return 3
    done = _existing_voices()
    failed: list[str] = []
    for name in BUILTIN_VOICES:
        try:
            model.get_state_for_audio_prompt(name)
        except Exception as exc:  # noqa: BLE001
            print(name, str(exc)[:300])
            if name in done:
                done.remove(name)
            failed.append(name)
            continue
        if name not in done:
            done.append(name)
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        json.dumps(ready_record(int(model.sample_rate), done), ensure_ascii=False),
        encoding="utf-8",
    )
    print("已写入标记。采样率", int(model.sample_rate), "音色", len(done), "/", len(BUILTIN_VOICES))
    if failed:
        print("这些音色没有准备成功：", ", ".join(failed))
        print("标记已区分模型在、音色未齐。补齐仍执行", PREPARE_COMMAND)
        return 3
    return 0


def _existing_voices() -> list[str]:
    if not MARKER.is_file():
        return []
    try:
        data = json.loads(MARKER.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return prepared_voice_names(data if isinstance(data, dict) else None)


if __name__ == "__main__":
    raise SystemExit(run())
