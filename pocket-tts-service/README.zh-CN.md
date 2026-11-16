# 可选的 Pocket TTS

Pocket TTS 接在现有 Piper HTTP 进程里面。对外仍然只有 `POST /api/tts`。省略 `engine` 时还是 Piper。`engine` 为 `pocket` 时走内置 worker，不另开端口。

官方包是 `pocket-tts==4.0.1`，Python 3.10–3.14，依赖 PyTorch 2.5 或更高。代码许可是 MIT。模型 `kyutai/pocket-tts` 在 Hugging Face 上标为 CC BY 4.0，并且 `gated: auto`。未登录下载权重会返回 401 `GatedRepo`。需要打开 <https://huggingface.co/kyutai/pocket-tts> 接受许可，再 `huggingface-cli login`。不能绕过。

官方 README 和 `default_parameters.py` 列出的语言是 english、french、german、portuguese、italian、spanish、dutch。没有中文、日语、韩语。请求这些语言会返回 400，不会改用 Piper。

内置音色按语言分开，例如英语默认 `alba`，法语默认 `estelle`。请求不能带文件路径、URL 或 `hf://`。音色页没有逐个写明性别，这里标为未知。各条音色的许可见 <https://huggingface.co/kyutai/tts-voices>。

英语配置 `pocket_tts/config/english.yaml` 的 `mimi.sample_rate` 是 24000。响应头 `X-Sample-Rate` 用模型实际值，不改成 Piper 的 22050。

Linux 上直接 `pip install pocket-tts` 会拉 CUDA 版 torch，体积大约数 GB。准备脚本使用 CPU 索引。Windows 的官方 torch 轮子本身是 CPU 版，虚拟环境仍要单独占用大约 2 GB 或更多磁盘，内存会在第一次加载模型时上升。不要把这些包装进 `piper-zh-service/.venv`。

```powershell
cd D:\aispace\local_tts_api\pocket-tts-service
powershell -ExecutionPolicy Bypass -File .\prepare-pocket.ps1 -Confirm
```

然后仍用原来的 Piper 启动命令。本机若 8791 被占用，继续用 `--port 8800`。Pocket worker 由这个进程在第一次 `engine=pocket` 时拉起。

```json
{"engine":"pocket","text":"Hello.","language":"english","voice":"alba"}
```
