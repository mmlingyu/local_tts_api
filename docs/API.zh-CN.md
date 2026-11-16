# 中英文语音调用说明

本文只描述当前仓库里已经实现的调用方式。核对来源是：

- `piper-zh-service/piper_zh/server.py`、`piper_zh/engine.py`
- `phonon/web/server.cjs`
- `zh-web-service/server.cjs`、`zh-web-service/app.js`、`zh-web-service/kokoro-client.js`
- `piper-zh-service/static/compare.js`

没有一个接口会自动拆开中英混合文本。Piper 的一次请求只使用白名单里的一个音色。Phonon 仍是另一条英文 HTTP。Kokoro 仍在浏览器里。调用方如果要一句里换引擎，必须自己拆句。

## 端口：源码默认和本机现状分开

| 引擎 | 源码默认 | 绑定地址 | 本机现状 |
| --- | --- | --- | --- |
| 中文静态页，含对照页 | `8787` | `127.0.0.1` | 用户电脑上的测试页使用 `127.0.0.1:8787` |
| Piper 白名单（中、英、日、韩、法） | `--port` 默认 `8791` | `127.0.0.1` | 用户电脑上 `8791` 被 Cursor 占用，已有 Piper 进程在 `127.0.0.1:8800`。本文不改那个进程。新代码仍用 `--port`，默认 8791 |
| Phonon 英文 | `server.cjs` 里写死 `8790` | `127.0.0.1` | 本机是否正在监听没有在这次文档工作中确认 |

下文示例里的 `PIPER` 用 `http://127.0.0.1:8800` 表示用户电脑上的当前 Piper。源码默认仍是 `8791`。把示例换到默认端口时，只改这一个地址。Phonon 示例用源码默认 `8790`，不表示已经确认它正在运行。

## 服务矩阵

| 能力 | 入口 | 中文 | 英文 | 日语 / 韩语 / 法语 | 是否 HTTP 合成 |
| --- | --- | --- | --- | --- | --- |
| Piper | `POST /api/tts` | `zh_CN-chaowen-medium`，g2pW 拼音 | `en_US-joe-medium`，espeak `en-us`。不是 lessac，也不替换 Phonon | 各有一条官方白名单音色，见下表 | 是 |
| Phonon | `POST /api/tts` | 含汉字则整段拒绝 | 是。旧英文页默认仍是它 | 不支持 | 是 |
| Kokoro | `window.zhTts` 或 `kokoro-client.js` | 是 | 主页面另有 `af_maple`；对照页不拿中文音色去读其他语言 | 不支持 | 否 |
| 8787 静态服务 | `GET /`、`GET /piper-compare.html` | 页面 | 页面可选 Piper 或 Phonon | 对照页可选 Piper 白名单 | 本身不合成 |

推荐调用：

- 旧客户端只发 `{"text":"..."}`：仍是 Piper 中文 chaowen。
- 要指定语言：同一 Piper 地址，加上 `language` 或 `voice`。用户电脑上的地址是 `http://127.0.0.1:8800`，但那个进程要换成这份新代码后才会认识新字段。
- 继续用原来的 Phonon 英文页：`http://127.0.0.1:8790/api/tts`。它没有被改成 Piper。
- 浏览器中文或 `af_maple`：`http://127.0.0.1:8787/` 的 `window.zhTts`。这不是 HTTP。

对照页 `http://127.0.0.1:8787/piper-compare.html` 也不是统一 API。它在浏览器里分别请求 Piper 和 Kokoro。

## 健康检查

### Piper

`GET /api/health`

模型还没准备好时也是 HTTP 200。看 JSON 里的 `modelReady`，不要只看状态码。

本次在开发虚拟机上用空闲端口做了一次烟测（不是性能数据），返回字段包括：

- `ok`、`modelReady`：布尔值
- `engine`：`piper-zh`
- `piperPackage`：`piper-tts[zh]==1.8.0`
- `piperVersion`：已安装的包版本；没装到时为 `null`
- `modelId`：默认中文音色是否已在磁盘上。`modelReady: true` 只表示 chaowen 文件和 g2pW 都在，不表示五种语言都已加载进内存
- `loadedVoiceIds`、`cacheLimit`：内存里最多保留有限个音色，默认 2。不会把五种模型一直放着
- `languages`、`voices`：每种语言的官方条目、是否已下载、是否已加载、前端是否就绪、`pronunciationReviewed`。最后一项恒为 false，自动 WAV 不是人工听审
- `phonemeType`：默认中文就绪时为 `pinyin`
- `g2p`：默认中文就绪时为 `python-g2pW`。英语、法语、韩语走 espeak，日语走 OpenJTalk，不会调用 g2pW

`GET /api/voices` 返回同一份白名单。响应里没有可填写的模型 URL。页面不能提交远程下载地址。
- `sampleRate`：chaowen 为 `22050`，单位 Hz
- `configuredDevice`：启动参数 `cpu` 或 `cuda`
- `hardwareProbe`：`false`。这个接口不探测 GPU
- `supportsStreaming`：`false`
- `responseMode`：`full-wav`
- `firstAudioMeasured`：`false`
- `maxTextChars`：`2000`
- `busy`：是否正在合成
- `port`：本进程实际监听端口
- `error`：未就绪时的说明
- `license`、`modelCard`

### Phonon

`GET /api/health`

源码返回 HTTP 200 和 JSON：`engine` 为 `Phonon English`，`version` 为 `0.7.0`，`voice` 为 `default`，以及 `voiceCount`、`pid`、`port`、`busy`。

这次没有本机 Phonon 可执行文件，**该响应未做实机烟测**。

### Kokoro / 8787

没有 `/api/health`。8787 的 `GET /` 和 `GET /piper-compare.html` 只说明静态页是否在。页面加载完成后，`window.appReady === true` 只表示主页面脚本已执行，不表示 Kokoro 模型已下载。

## Piper 合成

`POST /api/tts`

- `Content-Type` 必须以 `application/json` 开头。
- 请求体只能包含 `text`，以及可选的 `language`、`voice`、`speaker`。`model`、`path`、`url`、`command`、`speed` 都会 400。
- 只有 `{"text":"..."}` 时，语言是 `zh`，音色是 `zh_CN-chaowen-medium`。
- `language` 接受 `zh`、`en`、`ja`、`ko`、`fr`，或 `zh_CN`、`en_US`、`ja_JP`、`ko_KR`、`fr_FR`。`en_GB` 不在白名单里。
- `voice` 必须是下表里的 id。`en_US-lessac-medium` 会被拒绝。
- `language` 和 `voice` 同时出现时必须属于同一种语言，否则 `language_voice_mismatch`。
- `text`：字符串，必填。去掉首尾空白后长度 1 到 2000。不能含有 U+0000。
- 整个请求体的 `Content-Length` 必须在 1 到 65536 字节之间。
- 没有语速参数。语速仍是模型配置里的 `length_scale`。
- 单说话人音色如果带了 `speaker`，返回 `speaker_not_allowed`。日语 `ja_JP-hi_fi_captain-medium` 有 `female`（0）和 `male`（1）。省略时用 0。
- 英语和法语文本里如果有汉字、假名或韩文，返回 `mixed_script`。日语文本里的韩文、韩语文本里的假名同样拒绝。服务不会把这些片段改派给另一个音色。中文请求仍接受夹杂的拉丁字母，但 g2pW 不会把英文分给 Joe。

成功时：

- HTTP 200
- `Content-Type: audio/wav`
- 正文是整段 WAV，16-bit 单声道 PCM。chaowen 的采样率是 22050 Hz。
- `X-Streaming: full-wav`。这不是流式响应，也没有首音时间。
- `X-Audio-Duration`：音频时长，单位秒，十进制字符串，固定 6 位小数。
- `X-Synth-Seconds`：服务端整段合成耗时，单位秒，6 位小数。不含调用方的网络时间。
- `X-RTF`：`X-Synth-Seconds / X-Audio-Duration`，无单位，6 位小数。小于 1 表示整段合成比这段音频的播放时长短。
- `X-Sample-Rate`：整数 Hz 的十进制字符串。
- `X-Engine: Piper-zh`
- `X-Model`：实际音色 id
- `X-Language`：`zh`、`en`、`ja`、`ko` 或 `fr`
- `X-Voice`：与 `X-Model` 相同的音色 id
- `X-Speaker-Id`：只有多说话人音色才有
- `X-Phoneme-Type`：`pinyin`、`espeak` 或 `japanese`

这些头在开发虚拟机的一次 `{"text":"你好。"}` 烟测里都出现了，WAV 头为单声道、16-bit、22050 Hz。那次的具体秒数不是性能报告，这里不记录。

错误正文是 JSON，`Content-Type: application/json; charset=utf-8`，形如 `{"error":"……"}`。模型未就绪时还有 `"modelReady": false`。

| HTTP | 何时 |
| --- | --- |
| 400 | JSON 无效、出现路径或命令字段、`text` 不合法、超过 2000 字、`unsupported_language`、`unknown_voice`、`language_voice_mismatch`、`speaker_not_allowed`、`speaker_out_of_range`、`mixed_script` |
| 403 | `Host` 不是 `127.0.0.1:实际端口` 或 `localhost:实际端口`；或者带了 `Origin` 且不在允许列表 |
| 404 | POST 路径不是 `/api/tts` |
| 413 | 请求体为空或大于 65536 字节 |
| 415 | `Content-Type` 不是 `application/json` 开头 |
| 429 | 已有一段正在合成。响应带 `Retry-After: 2`。等当前段结束后再发，不要并行打同一进程 |
| 500 | 合成失败或结果无声。`error` 最长 500 字符 |
| 503 | 该音色文件还没下载，或它的前端没装好。`code` 为 `model_missing` 或 `frontend_missing`。中文缺 g2pW、日语缺 pyopenjtalk-plus 都属于这一类 |
| 504 | 等待整段合成超过 180 秒。后台可能还在算，随后的请求会先看到 429 |

允许的浏览器来源只有：

- `http://127.0.0.1:8787`
- `http://localhost:8787`
- `http://127.0.0.1:<本进程端口>`
- `http://localhost:<本进程端口>`

没有 `Origin` 的本机程序（curl、Python）可以调用。服务只监听 `127.0.0.1`。

`OPTIONS /api/tts`、`OPTIONS /api/health` 和 `OPTIONS /api/voices` 在来源合法时返回 204。`Access-Control-Max-Age` 为 600 秒。

离线准备一次只下载一个音色。不带 `--voice` 或 `--language` 时仍只准备中文 chaowen 和 g2pW：

```bash
python -m piper_zh.download --confirm
python -m piper_zh.download --confirm --language en
python -m piper_zh.download --confirm --voice fr_FR-siwis-medium
python -m piper_zh.download --list
```

日语还要另装 `pyopenjtalk-plus`（`requirements-ja.txt`）。这条依赖不会在下载英语时安装。页面点击不会下载模型。

### 白名单

索引核对日期是 2026-11-16 的 `voices.json`。采样率都是 22050 Hz。ONNX 大小是索引里的字节数。许可描述来自模型卡和 Piper 的商用说明，不是法律意见。

| 语言 | 默认音色 | 前端 | ONNX 字节 | 许可与训练链 | VOICES.md 语言列表 |
| --- | --- | --- | --- | --- | --- |
| zh | `zh_CN-chaowen-medium` | pinyin，g2pW | 63221984 | 录音 CC0；底模 Hi-Fi TTS reader 92，CC BY 4.0，分发要署名 | 有 |
| en | `en_US-joe-medium` | espeak `en-us` | 63221984 | 录音 CC0；底模 `nl_BE-rdh-medium`，CC0。不是 lessac | 有 |
| fr | `fr_FR-siwis-medium` | espeak `fr` | 63221984 | SIWIS 为 CC BY 4.0；底模同样是 Hi-Fi TTS，CC BY 4.0。不是无义务许可 | 有 |
| ja | `ja_JP-hi_fi_captain-medium` | japanese，OpenJTalk。两个说话人 | 76753841 | 数据集 CC BY-NC-SA 4.0，非商用；模型卡写明从 LibriTTS-R 微调 | 列表里没有日语，索引里有这一条 |
| ko | `ko_KR-kss-medium` | espeak `ko` | 63221984 | 数据集 CC BY-NC-SA 4.0，非商用；模型卡写明从 LibriTTS-R 微调 | 列表里没有韩语，索引里有这一条 |

没有把 lessac 或 huayan 放进白名单。`gender` 不是请求字段。`GET /api/voices` 会给出每个音色的 `gender`、`genderSource`、`licenseClass` 和语言级的 `missingGenders`。

### 中英日韩男女声

性别只采用模型卡、模型配置或数据集作者的原文。名字本身不算证据。

| 语言 | 女 | 男 | 状态 |
| --- | --- | --- | --- |
| zh | `zh_CN-xiao_ya-medium`。标贝页面写明「中文标准女声音库」「发音人：女」。拼音，g2pW。非商用，不是默认 | 官方索引里没有写明男声的模型。`zh_CN-chaowen-medium` 仍是默认，模型卡没写性别，标为未知 | 女声已补上。男声仍缺 |
| en | `en_US-ljspeech-medium`。模型卡写 “US English female voice”，公有领域，从零训练 | `en_US-norman-medium`。模型卡写 “US English male voice”，公有领域，从零训练 | 两者都已加入。`en_US-joe-medium` 仍是不带 voice 时的默认，性别未知 |
| ja | 同一模型 `speaker` 为 `female` 或 `0` | 同一模型 `speaker` 为 `male` 或 `1`。来源是官方 `onnx.json` 的 `speaker_id_map` | 已具备，不用再下载第二个模型 |
| ko | `ko_KR-kss-medium`。数据集作者写 “professional female voice actoress” | `voices.json` 没有第二份韩语模型 | 女声已核实。男声仍缺，不能用变调或其他语言冒充 |

显式下载，一次一个：

```bash
python -m piper_zh.download --confirm --voice zh_CN-xiao_ya-medium
python -m piper_zh.download --confirm --voice en_US-ljspeech-medium
python -m piper_zh.download --confirm --voice en_US-norman-medium
```

英语女声示例仍用 UTF-8 文件：

```powershell
$json = '{"text":"Hello.","voice":"en_US-ljspeech-medium"}'
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$pwd\piper-female.json", $json, $utf8)
curl.exe -sS -o piper-female.wav -H "Content-Type: application/json" --data-binary "@piper-female.json" http://127.0.0.1:8800/api/tts
```

日语男声把 `speaker` 写成 `"male"`。韩语没有对应的男声请求。Kokoro 页面本身有中文女声 `zf_001`、`zf_002` 和男声 `zm_009`、`zm_010`，英文 `af_maple` 在库里标为 Female，没有随这页提供的英文男声。Phonon 清单里美式和英式都有标注过的男女声，`default` 的 gender 是空。这些不是 Piper 白名单。

## Phonon 合成

`POST /api/tts`

- `Content-Type` 必须以 `application/json` 开头。
- JSON 对象。源码只读取 `text` 和 `voice`，没有「多余字段即失败」的检查。
- `text`：字符串，必填。`trim` 后不能为空，原始长度不超过 1000，不能含 U+0000。只要含有汉字（Unicode Han），整段返回 400，不会只朗读其中的英文。
- `voice`：字符串，可选。省略时为 `default`。可以填音色名或音色 ID，比较时忽略大小写。未知音色为 400。
- 请求体累计超过 8192 字节为 413。
- 没有语速参数。进程参数在源码里固定为英文、q8、CPU、4 线程。
- 成功响应是整段 WAV，不是流式。源码没有 `X-Streaming` 头。

成功头：

- `Content-Type: audio/wav`
- `X-Audio-Duration`：秒，6 位小数
- `X-Synth-Seconds`：从启动进程到读完 WAV 的耗时，秒，6 位小数
- `X-RTF`：上面两者相除，6 位小数
- `X-Audio-Peak`：峰值绝对值，相对满幅，9 位小数
- `X-Sample-Rate`：Hz
- `X-Voice`：音色名
- `X-Voice-ID`：音色 ID
- `X-Engine: Phonon-English`

`GET /api/voices` 返回 `{repo, revision, count, voices}`。每个音色有 `id`、`name`、`label`、`locale`、`gender`、`language`。

错误多为 `{"error":"……"}`。

| HTTP | 何时 |
| --- | --- |
| 400 | 文本不合法、含汉字、`voice` 不是字符串、音色未知、JSON 无效 |
| 403 | `Host` 不是 `127.0.0.1:8790` 或 `localhost:8790`；POST 的 `Origin` 不在允许列表；`OPTIONS` 的来源不是 `http://127.0.0.1:8787` |
| 404 | 其他路径 |
| 413 | 请求体超过 8192 字节 |
| 415 | 不是 JSON |
| 429 | `busy === true`。没有 `Retry-After`。等这一段结束再发 |
| 500 | 进程启动失败、退出码非 0、WAV 不合格 |
| 503 | 本地音色文件不存在 |

CORS 只对 `Origin: http://127.0.0.1:8787` 返回允许头。`http://localhost:8787` **不在** Phonon 的允许来源里。POST 另外允许本服务自己的 `http://127.0.0.1:8790` 和 `http://localhost:8790`。

子进程超过 120 秒会被杀掉。`requestTimeout` 为 150 秒。

**Phonon 的实机 HTTP 烟测这次没有做**，因为当前环境没有 `ptts.exe`。上面全部来自 `phonon/web/server.cjs`。

## Kokoro 浏览器调用

8787 不提供 Kokoro 的 HTTP 合成。合成发生在打开页面的浏览器里。

主页面脚本 `zh-web-service/app.js` 在页面 DOM 齐全时执行，并设置：

- `window.appReady = true`
- `window.zhTts.synthesize(text, voice, speed)`
- `window.zhTts.loadModel()`
- `window.zhTts.examples`

`synthesize` 的限制：

- `text`：去掉空白后 1 到 1500 字。
- `voice`：只能是 `zf_001`、`zf_002`、`zm_009`、`zm_010`、`af_maple`。
- `speed`：传给 `generate` 的数字。页面上的控件只有 `0.85`、`1`、`1.15`。函数本身没有再限制别的正数，但是页面没提供其他档。
- 同一页面同时只跑一段。第二段抛出「正在处理，请稍候」，这不是 HTTP 429。
- 使用 `KokoroTTS.generate()`，返回整段浮点波形后再封装 WAV。本仓库这两个调用点都没有使用库里的 `stream()`。
- 采样率用结果里的 `sampling_rate`，没有则按 24000 Hz。
- 模型 `onnx-community/Kokoro-82M-v1.1-zh-ONNX`，`dtype` 为 `fp32`。有 WebGPU adapter 时用 `webgpu`，初始化失败再试 `wasm`。
- 音色文件从同站 `/kokoro/voices/<voice>.bin` 读取。首次加载模型会访问 Hugging Face，除非浏览器里已经有缓存。

`window.zhTts.synthesize` 依赖主页面上的 `#status`、`#generate`、`#player` 等元素。不要在没有这些元素的页面里调用它。

对照页使用的是 `zh-web-service/kokoro-client.js`，构建后为 `/kokoro-client.js`：

- `loadKokoroModel()`：返回 `{device}`，`device` 为 `webgpu` 或 `wasm`。
- `synthesizeKokoro(text, voice, speed = 1)`：返回 `{samples, sampleRate, synthMs, device}`。
- `voice` 只能是 `zf_001`、`zf_002`、`zm_009`、`zm_010`。这里**不能**传 `af_maple`。
- 文本上限同样是 1500。
- `synthMs` 的单位是毫秒，不是秒。

中英混合文本可以交给中文音色的 `generate`，但是没有服务端把它拆成 Piper/Phonon。`af_maple` 只在主页面的五个音色里。

**这次写文档时没有重新跑浏览器合成。** 以前在虚拟机里用 wasm 跑通过 `synthesizeKokoro`，那次耗时不要当成这份文档的新基准。

## 调用方自行分流的例子

下面不是仓库里的某个 URL。它只说明调用方可以先看文本，再选引擎。

- 含汉字，并且要走 Piper：`POST http://127.0.0.1:8800/api/tts`，正文只有 `text`。
- 不含汉字，并且本机 Phonon 已启动：`POST http://127.0.0.1:8790/api/tts`。
- 含汉字又要浏览器 Kokoro：不要发 HTTP，调用 `synthesizeKokoro` 或主页面的 `window.zhTts.synthesize`。

一句里既有汉字又有英文单词时，Phonon 会拒绝整段。Piper 不会把英文分给 Phonon。

## curl

Windows 上用 `curl.exe`，不要用 PowerShell 的 `curl` 别名。中文不要直接放在命令行引号里。先把 JSON 写成没有 BOM 的 UTF-8 文件。

PowerShell 5.1：

```powershell
$json = '{"text":"你好。"}'
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$pwd\piper-body.json", $json, $utf8)
curl.exe -sS -D piper-headers.txt -o piper.wav -H "Content-Type: application/json" --data-binary "@piper-body.json" http://127.0.0.1:8800/api/tts
```

英语、日语各自再写一个 UTF-8 文件。端口仍要是已经换成新代码的 Piper：

```powershell
$json = '{"text":"Hello.","language":"en"}'
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$pwd\piper-en.json", $json, $utf8)
curl.exe -sS -D piper-en-headers.txt -o piper-en.wav -H "Content-Type: application/json" --data-binary "@piper-en.json" http://127.0.0.1:8800/api/tts
$json = '{"text":"こんにちは。","language":"ja","speaker":"female"}'
[System.IO.File]::WriteAllText("$pwd\piper-ja.json", $json, $utf8)
curl.exe -sS -o piper-ja.wav -H "Content-Type: application/json" --data-binary "@piper-ja.json" http://127.0.0.1:8800/api/tts
```

Phonon 同样先写文件。这条假定源码默认端口，本机是否在听未确认：

```powershell
$json = '{"text":"Hello from the local English engine.","voice":"default"}'
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$pwd\phonon-body.json", $json, $utf8)
curl.exe -sS -D phonon-headers.txt -o phonon.wav -H "Content-Type: application/json" --data-binary "@phonon-body.json" http://127.0.0.1:8790/api/tts
```

健康检查：

```powershell
curl.exe -sS http://127.0.0.1:8800/api/health
curl.exe -sS http://127.0.0.1:8800/api/voices
curl.exe -sS http://127.0.0.1:8790/api/health
curl.exe -sS http://127.0.0.1:8790/api/voices
```

上面两条 8800 是 Piper。两条 8790 是 Phonon。开发虚拟机对 Piper 白名单做了结构烟测：五种默认音色各返回一条非静音的 16-bit 单声道 WAV，采样率 22050。没有记录耗时，也不表示听感已经验收。`en_US-lessac-medium`、语言和音色冲突、英语文本里的汉字都会 400。Phonon 的 curl **未验证**。

## Python

```python
import json
from pathlib import Path

import requests

body = {"text": "Bonjour.", "language": "fr", "voice": "fr_FR-siwis-medium"}
response = requests.post(
    "http://127.0.0.1:8800/api/tts",
    data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    timeout=180,
)
response.raise_for_status()
Path("piper.wav").write_bytes(response.content)
print(response.headers.get("X-Sample-Rate"), response.headers.get("X-Streaming"))
```

Phonon 把 URL 换成 `http://127.0.0.1:8790/api/tts`，正文可以带 `voice`。这次没有对 Phonon 运行这段代码。

## 浏览器

在 `http://127.0.0.1:8787` 的页面里请求用户电脑上的 Piper。8787 在 Piper 的允许来源里。

```javascript
const response = await fetch("http://127.0.0.1:8800/api/tts", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text: "안녕하세요.", language: "ko" }),
});
if (!response.ok) {
  const data = await response.json();
  throw new Error(data.error || response.statusText);
}
const blob = await response.blob();
const audio = new Audio(URL.createObjectURL(blob));
await audio.play();
const link = document.createElement("a");
link.href = audio.src;
link.download = "piper.wav";
link.click();
```

`X-Streaming` 仍是 `full-wav`。不要把 `response.body` 的到达时间写成首音延迟。

Kokoro，在 8787 页面且已经执行 `node build.cjs` 之后：

```javascript
import { loadKokoroModel, synthesizeKokoro } from "/kokoro-client.js";

const loaded = await loadKokoroModel();
const { samples, sampleRate, synthMs, device } = await synthesizeKokoro("你好。", "zf_001", 1);
```

`samples` 是浮点波形，不是 WAV 字节。主页面里用 `window.zhTts.synthesize("你好。", "zf_001", 1)` 会自己写入该页的播放器和下载链接，但必须存在主页面的那些 DOM 节点。

## 验证范围

| 项 | 结果 |
| --- | --- |
| Piper 旧的 `{text}` 中文请求、白名单校验、缓存淘汰 | 单元测试通过 |
| Piper 五种默认音色各一条 WAV | 开发虚拟机烟测通过。只检查 WAV 结构、采样率和非静音。没有新的耗时数字，也没有人工听审 |
| 用户电脑上的 8800 进程 | 未替换，未在那台机器上下载新语言 |
| Phonon 全部 HTTP | 未验证。环境里没有 `ptts.exe` |
| Kokoro 浏览器函数 | 这次未重跑。协议以 `app.js` 和 `kokoro-client.js` 为准 |
| 8787 是否正在用户电脑上返回对照页 | 未在用户电脑上检查 |
