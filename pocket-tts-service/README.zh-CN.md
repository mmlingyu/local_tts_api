# 可选的 Pocket TTS

Pocket TTS 接在现有 Piper HTTP 进程里面。对外仍然只有 `POST /api/tts`。省略 `engine` 时还是 Piper。`engine` 为 `pocket` 时走内置 worker，不另开端口。

官方包是 `pocket-tts==4.0.1`，Python 3.10–3.14，依赖 PyTorch 2.5 或更高。代码许可是 MIT。模型 `kyutai/pocket-tts` 在 Hugging Face 上标为 CC BY 4.0，并且 `gated: auto`。缓存里还没有文件时，未登录下载会返回 401 `GatedRepo`，需要打开 <https://huggingface.co/kyutai/pocket-tts> 接受许可，再 `huggingface-cli login`。不能绕过。已经在 `models/hf-home` 里的权重不用再登录，也不用重下。

本次启用的模型 ID 是 `english_18m_2026-10`。官方配置写明这是 18.2M 参数、含 decoder 的英语模型。`load_model(language="english")` 会加载约 100M 的默认模型，本服务不调用它。`language` 字段只表示自然语言，用 `en` 或 `english`。模型 ID 放在 `variant`。省略 `variant` 也是 `english_18m_2026-10`。

`english_7m_2026-10`（6.9M）和 `english_2m_2026-10`（1.9M，实验档）写在上游 README 和 2026-10-20 的博客里，但这里没有启用，也没有测过，不能当成已支持。法语等上游语言同样没有接到这个 18.2M 变体上。中文、日语、韩语会返回 400，不会改用 Piper。

音色是 pocket-tts 4.0.1 `_ORIGINS_OF_PREDEFINED_VOICES` 的全部 27 个名字。`get_predefined_voice` 把每个名字解析到 `kyutai/pocket-tts-without-voice-cloning` 的 `languages/english_18m_2026-10/embeddings/{name}.safetensors`，revision `a7056f505a4a8ca72d8b5fb1440071d6f1a35739`。这个目录里的文件就是这 27 个，没有缺失，也没有额外文件。名字是：alba、anna、azelma、bill_boerst、caro_davy、charles、cosette、daan、eponine、estelle、eve、fantine、george、giovanni、jane、javert、jean、juergen、lola、marius、mary、michael、paul、peter_yearsley、rafael、stuart_bell、vera。请求不能带文件路径、URL 或 `hf://`。这个表没有性别字段，接口标为未知。`language=fr` 不会因为 estelle 而放行。

`english_18m_2026-10.yaml` 的 `mimi.sample_rate` 是 24000。响应头用模型实际值。`markerVersion` 2 且 voice 为 alba 表示权重标记已在、只准备了 alba。`markerVersion` 3 的 `voices` 列出已准备的内置名。只写 `languages: ["english"]` 的旧标记仍然无效。`prepared` 不是 `inferenceReady`。worker 第一次 torch 初始化失败会退出，父进程丢掉这个子进程，下一次请求重新启动。

本机如果 `.venv`、18.2M 权重和 alba 缓存已经在 `models/hf-home`，不要重装 torch，也不要重新登录。在 `pocket-tts-service` 里执行：

```powershell
.\.venv\Scripts\python.exe -m pocket_local.prepare --confirm --variant english_18m_2026-10
```

然后重启原来的 8800 进程，让它加载新的 worker 代码。页面点击不会下载。

Linux 上直接 `pip install pocket-tts` 会拉 CUDA 版 torch，体积大约数 GB。准备脚本使用 CPU 索引。Windows 的官方 torch 轮子本身是 CPU 版，虚拟环境仍要单独占用大约 2 GB 或更多磁盘，内存会在第一次加载模型时上升。不要把这些包装进 `piper-zh-service/.venv`。

```powershell
cd D:\aispace\local_tts_api\pocket-tts-service
powershell -ExecutionPolicy Bypass -File .\prepare-pocket.ps1 -Confirm
```

然后仍用原来的 Piper 启动命令。本机若 8791 被占用，继续用 `--port 8800`。Pocket worker 由这个进程在第一次 `engine=pocket` 时拉起。

```json
{"engine":"pocket","text":"Hello.","language":"en","voice":"alba","variant":"english_18m_2026-10"}
```
