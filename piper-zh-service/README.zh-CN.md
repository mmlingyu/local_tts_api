# 可选的本机 Piper 普通话服务

这是独立进程，不替换 8787 的 Kokoro，也不替换 8790 的英文 Phonon。默认打开 `http://127.0.0.1:8787/` 时，中文仍然走 Kokoro。

对照页：

- 只有 Piper 时：`http://127.0.0.1:8791/piper-compare.html`
- Piper 和 Kokoro 放在同一页时：`http://127.0.0.1:8787/piper-compare.html`

页面点击不会下载模型。权重必须先用下面的下载命令准备好。服务启动后强制 `HF_HUB_OFFLINE=1`，缺文件时健康检查会写明原因，合成接口返回 503。

## 支持的版本

- Python 3.9 及以上。本仓库在 Python 3.12 上跑过测试。
- `piper-tts[zh]==1.8.0`。chaowen 的模型卡要求 Piper 1.5 或更高，因为音素是 `pinyin`。
- 直接依赖和锁定版本在 `requirements.txt`。测试再加 `requirements-dev.txt` 里的 `pytest==8.3.4`。
- 推理设备默认 CPU。`--device cuda` 只是启动参数；服务不会探测电脑有没有 GPU。
- 不要把 `zh_CN-huayan-*` 配到这里。它的 `phoneme_type` 是 espeak，和 g2pW 拼音不是同一套 id。

## 许可和署名

Piper 引擎是 GPL-3.0-or-later。引擎许可证不覆盖音色。

建议音色是 `zh_CN-chaowen-medium`：

- 录音数据 CC0，来源见模型卡里的 `https://github.com/OHF-Voice/voice-datasets`。
- 从 `en_US-hifi_tts_92-medium` 微调。该底模是 Hi-Fi TTS reader 92（Cori Samuel），CC BY 4.0：`https://www.openslr.org/109/`。
- 分发这个音色或基于它再训练时，需要署名 Hi-Fi TTS。
- `zh_CN-xiao_ya-medium` 虽然也是 pinyin，但是标贝数据、非商用，本服务不默认下载它。

这不是法律意见。模型卡原文会在下载后放在 `models/MODEL_CARD`，健康检查也会带上这段说明。

## Linux

```bash
cd piper-zh-service
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m piper_zh.download --confirm
./start-piper-zh.sh
```

没有 `--confirm` 时，下载命令只打印许可并退出，不会取文件。

停止：`./stop-piper-zh.sh`

## Windows

旧环境的中文页在 `D:\aispace\zh-web-service`，英文 Phonon 在 `D:\aispace\phonon`。下面的命令使用仓库根 `D:\src\local_tts_api`。克隆到其他位置时，只替换这一段路径。不要把 Piper 写进那两个旧目录。

```powershell
cd D:\src\local_tts_api\piper-zh-service
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m piper_zh.download --confirm
$env:HF_HOME = "D:\src\local_tts_api\piper-zh-service\models\hf-home"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_HUB_DISABLE_TELEMETRY = "1"
.\.venv\Scripts\python.exe -m piper_zh --host 127.0.0.1 --port 8791 --device cpu
```

另开一个窗口启动原来的中文页：

```powershell
cd D:\src\local_tts_api\zh-web-service
npm install
node build.cjs
node download-voices.cjs
$env:PORT = "8787"
node server.cjs
```

浏览器打开 `http://127.0.0.1:8791/piper-compare.html`，或 `http://127.0.0.1:8787/piper-compare.html`。8787 读的是 `zh-web-service\public\piper-compare.html`。若 8787 上仍是旧的 node 进程，它没有这条路由，会返回 `Not found`。先停掉占用 8787 的旧进程，再运行 `start-zh-web.ps1`；脚本会先执行 `node sync-compare.cjs`，并且在 8787 仍被占用时直接退出，不再改到别的端口。

停止 Piper 时，在运行它的窗口按 Ctrl+C。也可以：

```powershell
powershell -ExecutionPolicy Bypass -File D:\src\local_tts_api\piper-zh-service\stop-piper-zh.ps1
```

模型可以不放在默认的 `models\`。用启动参数指定文件，例如：

```powershell
.\.venv\Scripts\python -m piper_zh --model D:\aispace\piper\zh_CN-chaowen-medium.onnx --g2p-dir D:\aispace\piper\g2pW
```

请求体不能改模型路径。

## 资源

`python -m piper_zh.download --confirm` 会写入，并且不提交到 Git：

| 文件 | 作用 |
| --- | --- |
| `models/zh_CN-chaowen-medium.onnx` | 声学模型，约 60 MB |
| `models/zh_CN-chaowen-medium.onnx.json` | 必须是 `phoneme_type: pinyin` |
| `models/MODEL_CARD` | 许可和训练链 |
| `models/g2pW/g2pw.onnx` | 多音字模型，压缩包约 108 MB |
| `models/hf-home/` | `bert-base-chinese` 分词器缓存。g2pW 只用分词器，不下载整份 BERT 权重 |

下载命令会核对官方 LFS 的大小和 SHA-256。服务进程本身不再访问 Hugging Face。

## 接口

只绑定 `127.0.0.1`。CORS 只允许本服务自己的页面，以及 `http://127.0.0.1:8787` 和 `http://localhost:8787`。

- `GET /api/health`：模型是否已加载、包版本、配置的 device、许可。`modelReady: false` 仍然返回说明，不是硬件探测。
- `POST /api/tts`，JSON 只能是 `{"text":"..."}`。最多 2000 个字符。同时只合成一段，另一段收到 429。
- 成功时返回整段 WAV。`X-Synth-Seconds` 是服务端整段合成耗时，`X-Audio-Duration` 是音频时长，`X-RTF` 是二者相除，`X-Streaming` 固定为 `full-wav`。没有首音时间头。

## 测试

```bash
cd piper-zh-service
.venv/bin/python -m pytest tests/test_server.py -q
node --test tests/compare-logic.test.mjs
```

上面两组不加载声学模型。`tests/test_server.py` 使用假的合成器，只检查健康检查、拒绝越权字段、WAV 头、RTF 定义、忙时 429 和缺模型 503。

权重下载完成后：

```bash
.venv/bin/python -m pytest tests/test_real_synthesis.py -q
```

这一组会真正调用 chaowen 和 g2pW。没有权重时会跳过，跳过不等于合成成功。多音字按普通话标准读音断言，不把引擎的错误输出改成期望值。

「银行」「行长」的「行」都读 háng（hang2），「长」读 zhǎng。「银行的行长」里两个「行」都应是 hang2。若「这位行长」被读成 xíng，测试失败，并在失败信息里留下实际音素；那是引擎错误，不是预期结果。

中文静态服务另有不依赖浏览器模型的检查：

```bash
cd zh-web-service
npm install
npm run build
npm run test:static
```

`npm test` 仍是原来的 `verify.cjs`。它依赖原机器上的 Edge 和 `D:\aispace\chickadee\extension` 里的 Playwright profile，不是这次 Piper 的测试。
