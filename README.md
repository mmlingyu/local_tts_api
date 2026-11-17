# local_tts_api

本地 TTS 服务的代码、启动脚本和构建/下载脚本。

本仓库整理自一台**已经放好模型、音色和运行时**的 Windows 机器。仓库里只有服务代码和脚本，**不包含模型、音色权重、ONNX Runtime、Phonon 运行时或 `node_modules`**。因此：

- 在原环境（依赖文件已经就位）上，可以用这里的脚本启动服务。
- **把仓库克隆到一台全新电脑后，不能直接启动。** 必须先自行准备下文列出的本机依赖，并放到脚本所期望的目录结构中。

更细的本地说明见：

- [`zh-web-service/README.zh-CN.md`](zh-web-service/README.zh-CN.md)
- [`phonon/README.zh-CN.md`](phonon/README.zh-CN.md)
- [`piper-zh-service/README.zh-CN.md`](piper-zh-service/README.zh-CN.md)
- [`docs/API.zh-CN.md`](docs/API.zh-CN.md)
- [`docs/API-INTEGRATION.zh-CN.md`](docs/API-INTEGRATION.zh-CN.md)（第三方应用接入。接口行为以 `dfb62eb` 为准）
- [`pocket-tts-service/README.zh-CN.md`](pocket-tts-service/README.zh-CN.md)

如果这两份说明与本文件冲突，以「模型未入库、新机器不能直接运行」这条边界为准。

## 目录结构

```text
.
├── README.md
├── .gitignore
├── zh-web-service/          # 中文 Web TTS，原环境监听 8787
│   ├── app.js               # 前端源码（不是构建产物）
│   ├── build.cjs            # 构建脚本，生成本机 public/app.js
│   ├── server.cjs
│   ├── package.json
│   ├── download-voices.cjs
│   ├── verify.cjs
│   ├── voice-manifest.json
│   ├── start-zh-web.ps1
│   ├── stop-zh-web.ps1
│   ├── README.zh-CN.md
│   └── public/
│       ├── index.html
│       └── phonon-bridge.js
├── piper-zh-service/        # 可选的本机 Piper 普通话，默认监听 8791
│   ├── piper_zh/            # Python 服务、显式下载、引擎
│   ├── static/              # 对照测试页
│   ├── tests/
│   ├── requirements.txt
│   └── README.zh-CN.md
└── phonon/                  # Phonon 英文 TTS 配套，原环境监听 8790
    ├── start-phonon-web.ps1
    ├── stop-phonon-web.ps1
    ├── synthesize-en.ps1
    ├── README.zh-CN.md
    ├── web/                 # 测试页与本地服务
    │   ├── server.cjs
    │   ├── index.html
    │   ├── app.js
    │   ├── compare.html
    │   ├── compare.js
    │   ├── voices-manifest.cjs
    │   └── 若干 compare 辅助脚本（.py）
    └── voices/
        ├── manifest.json    # 音色目录元数据
        └── voices.jsonl
```

未纳入仓库的本机目录（模型、运行时、缓存、测试产物等）不要从本仓库期望得到。

## 本机依赖（必须已经存在，本仓库不提供）

下面是原机器上的路径和关键文件，供对照。换机器或换盘符时，需要自己准备同样这批依赖，并让启动脚本仍能找到它们。没有这些文件时不要假设服务能跑起来。

### zh-web-service

原路径：`D:\aispace\zh-web-service`

| 依赖 | 原环境位置 | 说明 |
| --- | --- | --- |
| npm 依赖 | `node_modules/` | 未上传，需在本机按 `package.json` 安装 |
| 前端构建产物 | `public/app.js` | 由 `build.cjs` 生成的大 bundle，未上传 |
| ONNX Runtime Web | `public/ort/` | 多个 `.mjs` / `.wasm` 文件，原环境约 86 MB，未上传 |
| Kokoro 音色 | `public/kokoro/voices/*.bin` | 原环境有 `af_maple.bin`、`zf_001.bin`、`zf_002.bin`、`zm_009.bin`、`zm_010.bin`，未上传 |

`download-voices.cjs` 和 `voice-manifest.json` 在仓库中，可用于对照或在本机下载音色，但下载来源、校验和结果文件都不在本仓库里，需要你在本机自行完成。

### phonon

原路径：`D:\aispace\phonon`

| 依赖 | 原环境位置 | 说明 |
| --- | --- | --- |
| 英文模型 | `models/phonon-31m-en/` | 未上传。原环境含 `config.json`、`default-voice.safetensors`、`model.q8.gguf`（约 64.5 MB）、`tokenizer.json` 及该目录自带说明 |
| Phonon 运行时 | `runtime/ptts-0.7.0-x86_64-pc-windows-msvc/` | 未上传。原环境含 `ptts.exe`（约 21.5 MB）及许可证/说明；另有 `runtime/ptts-0.7.0-windows.zip` |
| 音色权重 | `voices/*.safetensors` | 未上传。仓库只保留 `voices/manifest.json` 与 `voices/voices.jsonl` 作为目录元数据 |
| 缓存 / 测试输出 | `cache/`、`test-output/`、日志、试听音频 | 未上传 |

## 在依赖已经就位的 Windows 本机上启动

以下步骤只适用于模型、音色、运行时和（如需要的）`node_modules` / `public/app.js` 已经准备好的机器。全新克隆后不要直接执行这些脚本并期望它能工作。

### 中文 Web 服务（8787）

1. 进入 `zh-web-service`。
2. 若还没有 `node_modules`，按该目录 `package.json` 在本机安装依赖。
3. 若还没有 `public/app.js`，使用仓库中的 `build.cjs` 在本机构建；这个生成文件故意没有入库。
4. 确认 `public/ort/`（由 `build.cjs` 从本目录依赖复制）与 `public/kokoro/voices/` 中的音色已存在。音色仍用 `download-voices.cjs` 单独下载，构建不会顺手下载。
5. 运行 `start-zh-web.ps1` 启动，需要停止时运行 `stop-zh-web.ps1`。
6. 浏览器访问 `http://127.0.0.1:8787/`。

### Phonon 配套服务（8790）

1. 进入 `phonon`。
2. 确认 `models/phonon-31m-en/`、`runtime/ptts-0.7.0-x86_64-pc-windows-msvc/ptts.exe`、以及 `voices/*.safetensors` 已存在。
3. 运行 `start-phonon-web.ps1` 启动，需要停止时运行 `stop-phonon-web.ps1`。
4. 浏览器访问 `http://127.0.0.1:8790/`。
5. 命令行英文合成可参考 `synthesize-en.ps1`，它同样依赖上述本机 runtime、模型和音色。

### 可选 Piper 普通话（8791）

中文默认仍然是上面的 Kokoro。Piper 要单独安装、单独下载 `zh_CN-chaowen-medium` 和 g2pW，再启动。Linux 与 Windows 步骤、许可和测试命令见 [`piper-zh-service/README.zh-CN.md`](piper-zh-service/README.zh-CN.md)。

- Piper 测试页：`http://127.0.0.1:8791/piper-compare.html`
- 与 Kokoro 同一页对照：`http://127.0.0.1:8787/piper-compare.html`（需要先按 `zh-web-service` 的步骤构建）
- Linux 也可以在 `zh-web-service` 里执行 `./start-zh-web.sh`。它只在缺少构建产物时调用 `build.cjs`，不会下载 Piper 模型。

脚本内部的具体参数以脚本和子目录 `README.zh-CN.md` 为准。

## 明确没有上传的内容

- 模型、音色权重（`.bin` / `.safetensors` / `.gguf`）、ORT wasm、Phonon `runtime` / `ptts.exe`
- `node_modules`、虚拟环境、缓存、日志、`test-output`、试听或对比音频
- `.env` 及密钥
- 生成的 `zh-web-service/public/app.js` 和 `public/kokoro-client.js`
- Piper 的 onnx、g2pW 和 Hugging Face 分词器缓存（`piper-zh-service/models/`）
- Kokoro-FastAPI、chickadee 或其他未列入上面结构的项目
