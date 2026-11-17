# 统一 TTS API 第三方接入开发文档

本文给第三方应用调用本机已经部署的统一语音接口。它只描述 HTTP 调用，不提供 SDK，也没有 `client.speak()` 这一类封装方法。

| 项 | 内容 |
| --- | --- |
| 文档整理日 | 2026-11-17（Asia/Shanghai） |
| 接口核对提交 | `dfb62eb13bd7f4456a491109f5d834cb13b118ed`（短名 `dfb62eb`） |
| 核对范围 | `piper-zh-service/piper_zh/server.py`、`catalog.py`、`engine.py`，`pocket-tts-service/pocket_local/catalog.py`、`bridge.py`、`worker.py`，以及对应测试 |
| 2026-11-16 本机历史 | 见文末。那是已经发生过的部署和结构验收，不是性能承诺 |
| 2026-11-17 | 只整理本文。没有重新请求本机服务，也不知道 8800 此刻是否仍在监听 |

示例 JSON 里，凡是会随机器变化的字段（是否已下载、是否已加载、错误原因文本、进程路径）都是**示意**。采样率 22050 和 24000 来自白名单常量和 2026-11-16 的结构验收，不是 2026-11-17 新测出来的耗时。本文不记录合成秒数，也不把不同句子或第一次加载缓存拿来比速度。

## 1. 第三方要调用的地址

已部署的合成服务只有一个：

```text
POST http://127.0.0.1:8800/api/tts
```

用 JSON 字段 `engine` 区分引擎。省略 `engine`，或写 `"piper"`，就是 Piper。写 `"pocket"` 才是 Pocket。两种引擎共用这一个端口、这一条路径。

旧客户端只发下面这一段时，仍然是 Piper 中文默认音色 `zh_CN-chaowen-medium`：

```json
{"text":"银行行长到了重庆。"}
```

不要把下面几个地址当成这条统一 API：

| 地址 | 实际角色 |
| --- | --- |
| `http://127.0.0.1:8800` | 本机已部署的统一 TTS。第三方调用这个 |
| `http://127.0.0.1:8787` | 浏览器页面和静态文件。它自己不合成。对照页会再去请求 8800 |
| `http://127.0.0.1:8791` | 这台机器上被 Cursor 占用的旧服务，不能当本 API 用 |
| 源码 `--port` 默认值 8791 | 只是程序没写端口时的默认值。这台已部署机器听的是 8800 |
| `http://127.0.0.1:8790` | 另一套 Phonon 英文页面，不属于本文的 `engine=piper\|pocket` |

服务进程只绑定 `127.0.0.1` 或 `localhost`。另一台电脑、局域网 IP、云端主机都不能直接访问这台机器上的 8800。把 URL 里的 `127.0.0.1` 换成局域网 IP 也不能用，因为进程拒绝绑定非回环地址，Host 检查也只接受 `127.0.0.1:8800` 和 `localhost:8800`。

## 2. 接入顺序

客户端保持串行：上一段 HTTP 响应回来之后，再发下一段。服务进程里 Piper 和 Pocket 共用一把忙锁，同时两段会得到 429。

1. `GET http://127.0.0.1:8800/api/health`
2. 需要 Piper 时 `GET http://127.0.0.1:8800/api/voices`
3. 需要 Pocket 时 `GET http://127.0.0.1:8800/api/voices?engine=pocket`
4. 按清单组 JSON，`POST /api/tts`
5. HTTP 状态不是 200，或者 `Content-Type` 不是 `audio/wav` 时，把正文当 JSON 错误读。不要把这段正文存成 WAV

健康检查即使模型没准备好也是 HTTP 200。要看 JSON 里的字段，不能只看状态码。

## 3. GET /api/health

`Content-Type` 为 `application/json; charset=utf-8`。顶层是 Piper 语音池的状态，再附加 `busy`、`port` 和 `engines`。

### 3.1 顶层字段

这些名字里的 `modelReady`、`loaded` 说的是 **Piper 默认中文音色 chaowen**，不是 Pocket，也不是八个 Piper 音色都已经在内存里。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `ok` | bool | 默认中文音色文件在，并且中文前端 g2pW 可用 |
| `engine` | string | 固定 `piper-zh` |
| `serviceVersion` | string | 当前多语言服务为 `1.1.0`。若看到 `1.0.0`，说明连上的是旧 Piper 进程 |
| `piperPackage` | string | 声明值 `piper-tts[zh]==1.8.0` |
| `piperVersion` | string 或 null | 进程里实际装到的包版本。读不到时为 null |
| `modelId` | string 或 null | 默认中文就绪时为 `zh_CN-chaowen-medium`，否则 null |
| `modelPath` | string | 服务端本机路径。客户端不要把它回传 |
| `modelReady` | bool | 默认中文音色文件和 g2pW 是否就绪。不是 Pocket，也不是“推理刚刚成功” |
| `loaded` | bool | 默认中文音色当前是否在内存缓存里 |
| `loadedVoiceIds` | string[] | 当前驻留内存的 Piper 音色 id。默认最多 2 个 |
| `cacheLimit` | number | 默认 2 |
| `error` | string 或 null | 默认中文未就绪时的说明。其他已下载音色仍可能单独调用 |
| `phonemeType` | string 或 null | 默认中文就绪时为 `pinyin` |
| `g2p` | string 或 null | 默认中文就绪时为 `python-g2pW` |
| `sampleRate` | number 或 null | 白名单给 chaowen 写的是 22050 Hz。这是目录值，不是本次新测的耗时 |
| `configuredDevice` | string | 启动参数 `cpu` 或 `cuda` |
| `hardwareProbe` | bool | 固定 false。这个接口不探测 GPU |
| `deviceNote` | string | 说明上一行只是启动参数 |
| `supportsStreaming` | bool | 固定 false |
| `firstAudioMeasured` | bool | 固定 false。没有首音时间 |
| `responseMode` | string | 固定 `full-wav` |
| `maxTextChars` | number | Piper 文本上限 2000。Pocket 另有 500，见请求表 |
| `license` | object | Piper 引擎和默认中文音色的许可摘要，不是全部音色的许可 |
| `languages` | array | 五种语言的覆盖，含 `verifiedGenders`、`missingGenders` |
| `voices` | array | 与 `GET /api/voices` 的 `voices` 相同结构 |
| `residentModels` | string[] | 与当前驻留音色相同 |
| `modelCard` | string | 默认中文音色若已加载，最多 4000 字模型卡文本，否则空字符串 |
| `busy` | bool | 当前是否有一段合成还没结束。Piper 和 Pocket 共用 |
| `port` | number | 本进程实际监听端口。已部署机器应为 8800 |
| `engines.piper` | object | 只有 `serviceVersion` 和 `modelReady`，含义与顶层 Piper 相同 |
| `engines.pocket` | object | Pocket 状态。见下一节 |

示意形状如下。`piperVersion`、`modelPath`、`loadedVoiceIds`、`busy` 会随进程变化，这里的具体字符串不是 2026-11-17 的实测：

```json
{
  "ok": true,
  "engine": "piper-zh",
  "serviceVersion": "1.1.0",
  "modelReady": true,
  "loaded": false,
  "loadedVoiceIds": [],
  "cacheLimit": 2,
  "sampleRate": 22050,
  "supportsStreaming": false,
  "firstAudioMeasured": false,
  "responseMode": "full-wav",
  "maxTextChars": 2000,
  "busy": false,
  "port": 8800,
  "engines": {
    "piper": {"serviceVersion": "1.1.0", "modelReady": true},
    "pocket": {"installed": true, "prepared": true, "modelReady": true, "loaded": false, "inferenceReady": false}
  }
}
```

### 3.2 engines.pocket 的就绪语义

Pocket 子对象和顶层 Piper 使用同名字段时，含义不同。

| 字段 | 含义 |
| --- | --- |
| `installed` | 隔离虚拟环境里的 Python 是否存在。不是权重已下载 |
| `python` | 该解释器路径。示意值，客户端不要回传 |
| `prepared` | `ready.json` 是否是当前 18.2M 标记。文件就绪，不是 worker 已加载 |
| `modelReady` | 与 `prepared` 相同，仍是标记文件。不要把它读成“刚刚推理成功” |
| `preparedVariant` | 标记里的 variant。未准备时可能为 null |
| `loaded` | 与 `inferenceReady` 相同 |
| `inferenceReady` | worker 至少成功合成过一次，并且该进程仍在。失败后回到 false |
| `voicesComplete` | 27 个内置音色是否都写进标记 |
| `preparedVoices` | 已写入标记的音色 id |
| `missingVoices` | 尚未写入标记的音色 id |
| `voiceCount` | 固定 27 |
| `code` | `model_not_ready`、`voices_incomplete`、`inference_failed` 或 null |
| `reason` | 给人读的说明 |
| `lastError` | 上次推理失败的短文本。没有失败时为 null |
| `readinessNote` | 固定说明 prepared 不等于推理就绪 |
| `variant` | 固定 `english_18m_2026-10` |
| `parameters` | 固定 `18.2M` |
| `gated` | true。权重仓库需要事先接受许可；页面请求不会下载 |
| `languages` | 只有 `english` |
| `defaultVoice` | `alba` |
| `defaultLanguage` | `english` |
| `sampleRate` | 配置公布值 24000 |
| `package` | `pocket-tts==4.0.1` |
| `unsupported` | `zh`、`ja`、`ko`、`fr` |
| `notEnabled` | `english`（约 100M）、`english_7m_2026-10`、`english_2m_2026-10` |

`code` 的读法：

- `model_not_ready`：虚拟环境不在，或没有当前 18.2M 标记。合成会是 HTTP 503
- `voices_incomplete`：权重标记在，但 27 个音色没齐。已列出的音色可以合成；未列出的是 HTTP 503
- `inference_failed`：27 个都已标记，但上次 worker 失败并已退出。`inferenceReady` 为 false。下一次请求会新起 worker，不会自动重下模型
- null：标记完整，并且没有挂着的上次失败。这仍然不等于“进程此刻已经把模型载入内存”，除非 `inferenceReady` 同时为 true

进程没把 Pocket 接进来时，`engines.pocket` 只有 `{"installed": false}`。已部署的 `dfb62eb` 服务会接入 Pocket。

## 4. GET /api/voices

查询参数 `engine` 省略或为 `piper` 时返回 Piper。`engine=pocket` 返回 Pocket。其他值是 HTTP 400，`code` 为 `bad_engine`。

响应里没有可提交的模型 URL。客户端不能传本地路径、下载地址或 `hf://`。

### 4.1 Piper

```json
{
  "voices": [],
  "languages": [],
  "cacheLimit": 2,
  "loadedVoiceIds": [],
  "note": "列表来自白名单。没有下载地址字段，页面不能提交远程模型。"
}
```

`voices` 里每个对象的稳定字段：

| 字段 | 含义 |
| --- | --- |
| `voice` | 请求时使用的 id |
| `language` | `zh`、`en`、`ja`、`ko`、`fr` 之一 |
| `locale` | 如 `zh_CN` |
| `phonemeType` | `pinyin`、`espeak` 或 `japanese` |
| `espeakVoice` | espeak 音色名；中文和日语为 null |
| `sampleRate` | 白名单值，八个音色都是 22050 |
| `numSpeakers` | 1，或日语的 2 |
| `speakers` | 日语为 `{"female": 0, "male": 1}`，其余为 `{}` |
| `defaultSpeakerId` | 日语默认 0 |
| `defaultForLanguage` | 该语言省略 voice 时是否选它 |
| `datasetLicense` | 数据集许可原文 |
| `datasetUrl` | 数据集页面 |
| `training` | 训练来源说明 |
| `commercialNote` | 服务内的许可备注。不是法律意见 |
| `gender` | `female`、`male`、`multiple`、`unknown` |
| `genderSource` | 性别结论的出处。`unknown` 表示出处没写性别 |
| `speakerGenders` | 仅日语有 female/male |
| `licenseClass` | `attribution`、`noncommercial`、`permissive` 或 `unknown` |
| `downloaded` | 本机文件尺寸是否符合索引 |
| `filesMatchIndex` | 已下载时是否连 MD5 也符合 |
| `loaded` | 是否在当前进程内存里 |
| `frontendReady` | 该音色的前端是否可加载 |
| `frontendError` | 前端不可用时的原因，否则 null |
| `synthesisVerifiedThisProcess` | 本进程是否合成过。不表示人工听审 |
| `pronunciationReviewed` | 固定 false |
| `official` / `supported` | 白名单内固定 true |
| `onnxBytes` | 索引中的 onnx 字节数 |

`languages` 的每个对象含 `language`、`locale`、`officialVoiceCount`、`verifiedGenders`、`missingGenders`、`gap`、`voices`、`defaultVoice`、`anyDownloaded`、`anyLoaded`、`pronunciationReviewed`。`pronunciationReviewed` 固定 false。

性别缺口来自源码，不是猜测：

- 中文：没有官方模型写明男声。chaowen 为 `unknown`，xiao_ya 为女声
- 韩语：只有 kss 女声，`missingGenders` 含 `male`
- 法语：siwis 的模型卡没有写性别，`gender` 为 `unknown`
- 英语：ljspeech 女声、norman 男声。joe 的模型卡没写性别，为 `unknown`
- 日语：同一模型里 speaker 0 女声、speaker 1 男声

### 4.2 Pocket

`voices` 固定 27 项。每项：

| 字段 | 值 |
| --- | --- |
| `voice` | 下表 id |
| `language` | `english` |
| `variant` | `english_18m_2026-10` |
| `parameters` | `18.2M` |
| `defaultForLanguage` | 只有 alba 为 true |
| `gender` | 全部 `unknown` |
| `genderSource` | pocket-tts 4.0.1 的预定义表没有性别字段 |
| `sampleRate` | 24000，来自 `english_18m_2026-10.yaml` 的 `mimi.sample_rate` |
| `builtin` | true |
| `prepared` | 该 id 是否已经写入 ready 标记 |

另外还有 `voicesComplete`、`preparedVoices`、`missingVoices`、`modelReady`、`inferenceReady`、`code`、`reason`。语义与健康检查里的 Pocket 相同。`prepared: false` 时不要对该 id 重试下载；调用会得到 503 `voices_incomplete`。

## 5. POST /api/tts

请求头：

```http
Content-Type: application/json; charset=utf-8
```

`Content-Type` 必须以 `application/json` 开头。正文是 UTF-8 JSON 对象。整个请求体最大 65536 字节，空正文同样拒绝。

成功时正文是整段 WAV 二进制，不是 JSON，也不是分块流。失败时正文是 JSON。先看状态码和 `Content-Type`，失败正文不能当 WAV 保存。

### 5.1 字段

只允许这些键：`text`、`engine`、`language`、`voice`、`speaker`、`variant`。多一个键，包括 `gender`、`speed`、`format`、`model`、`path`、`url`，都是 HTTP 400，`code` 为 `bad_request`。不能传文件路径、http(s) URL 或 `hf://`。

| 字段 | 类型 | Piper | Pocket |
| --- | --- | --- | --- |
| `text` | string | 必填。去掉首尾空白后 1 到 2000 个 Unicode 字符。不能含 U+0000 | 必填。1 到 500 个 Unicode 字符。不能含 U+0000 |
| `engine` | string | 省略、JSON null 都当作 `piper`。只接受小写 `piper` 或 `pocket` | 必须是 `pocket` |
| `language` | string | 省略则随 `voice`；两者都省略则为 `zh`。见下表 | 省略则为 `english`。只接受 `en`、`en_us`、`en-us`、`english` |
| `voice` | string | 省略则用该语言默认音色。必须是第 6 节八个 id 之一 | 省略则为 `alba`。必须是第 7 节 27 个 id 之一 |
| `speaker` | string 或整数 | 只有日语可以传。省略时日语用 0。其他音色一传这个键就 400 | 只要出现这个键就 400 `speaker_not_allowed` |
| `variant` | string | 只要出现这个键就 400。Piper 没有这个字段 | 省略则为 `english_18m_2026-10`。只接受这一个 id |

Piper `language` 在去掉首尾空白并转成小写后，接受：

| 传入 | 归一成 |
| --- | --- |
| `zh`、`zh_cn`、`zh-cn` | `zh` |
| `en`、`en_us`、`en-us` | `en` |
| `ja`、`ja_jp`、`ja-jp` | `ja` |
| `ko`、`ko_kr`、`ko-kr` | `ko` |
| `fr`、`fr_fr`、`fr-fr` | `fr` |

`voice` 和 `language` 同时出现时，语言必须就是该音色的语言，否则 400 `language_voice_mismatch`。

`speaker` 可以是 JSON 整数，或 `female` / `male`。布尔值、小数都不行。日语 `female` 和 `0` 是女声，`male` 和 `1` 是男声。编号必须落在 0 到 1。单说话人音色不能带 `speaker`，即使值是 0。

Pocket 的 `variant` 若是 `english`、`english_7m_2026-10`、`english_2m_2026-10`、`english_18m_refl_2026-10`，返回 400 `variant_not_enabled`。其他字符串是 400 `bad_variant`。`language` 里放模型 id 也会 400。中文、日语、韩语、法语即使上游别的模型存在，当前接口也返回 400 `unsupported_language`，并且不会改去调用 Piper。

Piper 还有文字脚本限制，命中时是 400 `mixed_script`：

- 英语、法语文本里出现汉字、假名或韩文：拒绝，不拆句
- 日语文本里出现韩文：拒绝
- 韩语文本里出现假名：拒绝
- 中文不按这个规则拒绝英文字母

### 5.2 成功响应头

正文是 `audio/wav`。服务在写出前检查 WAV 必须是 16-bit、单声道；否则不会当成功返回。Piper 八个音色的白名单采样率都是 22050 Hz。Pocket 使用模型实际采样率，配置公布值和 2026-11-16 的 Hello 结构验收都是 24000 Hz。响应头里的 `X-Sample-Rate` 以本次 WAV 为准。

| 响应头 | 单位 | 含义 |
| --- | --- | --- |
| `Content-Type` | | `audio/wav` |
| `X-Audio-Duration` | 秒，六位小数 | WAV 里的音频时长 |
| `X-Synth-Seconds` | 秒，六位小数 | 服务端整段合成耗时。不是首音时间，也不是客户端往返 |
| `X-RTF` | 无量纲，六位小数 | `X-Synth-Seconds / X-Audio-Duration` |
| `X-Sample-Rate` | Hz | 本次 WAV 的采样率 |
| `X-Engine` | | Piper 为 `Piper-zh`，Pocket 为 `Pocket-TTS` |
| `X-Model` | | Piper 是音色 id；Pocket 是 `english_18m_2026-10` |
| `X-Phoneme-Type` | | `pinyin`、`espeak`、`japanese` 或 `pocket` |
| `X-Streaming` | | 固定 `full-wav` |
| `X-Language` | | Piper 为 `zh`/`en`/`ja`/`ko`/`fr`；Pocket 为 `english` |
| `X-Voice` | | 实际音色 id |
| `X-Speaker-Id` | | 仅当本次有说话人编号时出现。日语默认女声也会出现 `0`。Pocket 不出现 |
| `Cache-Control` | | `no-store` |
| `X-Content-Type-Options` | | `nosniff` |

`firstAudioMeasured` 为 false。不要把整段耗时、RTF 或客户端等待时间写成首音，也不要据此给音质排名。

## 6. Piper 八个音色

源码白名单正好 8 个，不是更多。

| voice | language | 默认 | gender | speaker | datasetLicense | licenseClass | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `zh_CN-chaowen-medium` | zh | 是 | unknown | 不能传 | CC0 | attribution | 录音 CC0；从 Hi-Fi TTS reader 92（CC BY 4.0）微调。分发要署名。模型卡没写性别 |
| `zh_CN-xiao_ya-medium` | zh | | female | 不能传 | Non-commercial | noncommercial | 标贝中文标准女声，非商用。不是默认音色 |
| `en_US-joe-medium` | en | 是 | unknown | 不能传 | CC0 | permissive | 模型卡没写性别。训练链备注为 CC0，引擎仍是 GPL |
| `en_US-ljspeech-medium` | en | | female | 不能传 | public domain | permissive | 模型卡写明美国英语女声 |
| `en_US-norman-medium` | en | | male | 不能传 | public domain | permissive | 模型卡写明美国英语男声 |
| `ja_JP-hi_fi_captain-medium` | ja | 是 | multiple | 0 女 / 1 男 | CC BY-NC-SA 4.0 | noncommercial | 省略 speaker 时用 0。前端是 OpenJTalk，不是 g2pW |
| `ko_KR-kss-medium` | ko | 是 | female | 不能传 | CC BY-NC-SA 4.0 | noncommercial | 没有官方韩语男声 |
| `fr_FR-siwis-medium` | fr | 是 | unknown | 不能传 | CC BY 4.0 | unknown | 模型卡没写性别。数据集和底模要按 CC BY 4.0 署名 |

中文没有已核实男声。韩语没有男声。不要用变调、换语言或未入库的音色名补这个缺口。`lessac` 不在白名单里。

## 7. Pocket 27 个音色

唯一模型是 `english_18m_2026-10`，官方配置写明 18.2M，含 decoder。`variant` 省略时仍是这个 id。下面 27 个 id 与 pocket-tts 4.0.1 `get_predefined_voice` 的映射一致，对应仓库 `kyutai/pocket-tts-without-voice-cloning`、revision `a7056f505a4a8ca72d8b5fb1440071d6f1a35739`、目录 `languages/english_18m_2026-10/embeddings/`。该目录没有第 28 个文件。性别全部是 `unknown`。

```text
alba
anna
azelma
bill_boerst
caro_davy
charles
cosette
daan
eponine
estelle
eve
fantine
george
giovanni
jane
javert
jean
juergen
lola
marius
mary
michael
paul
peter_yearsley
rafael
stuart_bell
vera
```

默认音色是 `alba`。`estelle`、`daan` 等名字可以在这个英语模型上合成，但不能把 `language` 写成 `fr` 或其他语言。

当前接口不提供、传了会 400 的模型 id：

| id | 原因 |
| --- | --- |
| `english` | 上游约 100M 的默认模型 |
| `english_7m_2026-10` | 6.9M，本服务未启用 |
| `english_2m_2026-10` | 1.9M 实验档，本服务未启用 |
| `english_18m_refl_2026-10` | 带 reward fine-tuning 的变体，本服务未启用 |

中文、日语、韩语、法语不是这个接口的 Pocket 语言。上游若在其他 variant 里有这些语言，当前 HTTP 仍然拒绝。

## 8. 错误

失败正文一般是 `{"error":"...","code":"..."}`。下表“无”表示源码没写 `code`。HTTP 状态不是 200 时，正文不是 WAV。

| HTTP | code | 何时出现 | 客户端做什么 |
| --- | --- | --- | --- |
| 400 | `bad_request` | 多余字段、空文本、类型不对、Piper 带了 variant、正文不是 JSON、`Content-Length` 不是整数 | 改请求。不要原样重试 |
| 400 | `bad_engine` | `engine` 不是 `piper` 或 `pocket`；voices 的查询值也一样 | 改请求 |
| 400 | `text_too_long` | Piper 超过 2000，或 Pocket 超过 500 | 缩短文本 |
| 400 | `unsupported_language` | 语言不在对应引擎的允许集合 | 不要换成另一个引擎重试 |
| 400 | `unknown_voice` | id 不在白名单，或带了路径 / URL / `hf://` | 改用清单里的 id |
| 400 | `language_voice_mismatch` | language 和 voice 不是同一种语言 | 改其中一个 |
| 400 | `speaker_not_allowed` | 非日语带了 speaker，或 Pocket 带了 speaker | 删掉 speaker |
| 400 | `speaker_out_of_range` | 日语 speaker 不是 0、1、`female`、`male` | 改成允许值 |
| 400 | `mixed_script` | 文本脚本不被该语言接受 | 不要自动换音色 |
| 400 | `bad_variant` | Pocket variant 不是那个 18.2M id，或像路径 / URL | 省略或写 `english_18m_2026-10` |
| 400 | `variant_not_enabled` | 100M、7M、2M 或 refl | 不要改调用未启用模型 |
| 403 | 无 | Host 不是 `127.0.0.1:8800` 或 `localhost:8800`；或者带了不允许的 `Origin` | 这是部署限制，不是换个 JSON 字段能过 |
| 404 | 无 | 路径不是健康检查、音色清单或 `POST /api/tts` | 检查路径和方法 |
| 413 | 无 | 正文为空，或大于 65536 字节 | 缩小正文 |
| 415 | 无 | `Content-Type` 不是 `application/json` 开头 | 补请求头 |
| 429 | 无 | 上一段还没结束。响应头 `Retry-After: 2` | 至少等 2 秒，串行重试同一请求 |
| 503 | `model_not_ready` | Pocket 虚拟环境或 18.2M 标记未就绪 | 不要循环重试，请求不会触发下载 |
| 503 | `voices_incomplete` | Pocket 模型标记在，但这个音色还没写入标记 | 换一个 `prepared: true` 的音色，或等操作员显式准备 |
| 503 | `pocket_not_ready` | 进程没有接入 Pocket | 不要改打 Piper 冒充 |
| 503 | `model_missing` | Piper 该音色文件还没准备好 | 不要在请求里下载 |
| 503 | `frontend_missing` | Piper 前端未就绪，例如缺 g2pW、espeak 数据或日语 OpenJTalk | 不要换前端重试 |
| 503 | 可能无 `code` | 仅当语音池对象被标成未就绪时，正文含 `modelReady: false` | 看 `error` |
| 500 | `worker_failed` | Pocket worker 初始化或合成失败。worker 会被关掉 | 可以稍后串行再试一次。不要紧循环 |
| 500 | 无 | 其他未捕获异常，或 WAV 时长无效。`error` 最长约 500 字 | 先读 JSON。不要把正文存成 WAV |
| 504 | 无 | 服务等待整段合成超过 180 秒后停止等待。模型可能仍在后台收尾 | 先看 `GET /api/health` 的 `busy`。变成 false 后再决定是否重试一次 |

429 的 `Retry-After` 值是字符串 `"2"`，单位秒。504 没有 `Retry-After`。

建议客户端超时设为 **200 秒**。服务端等待上限是源码常量 `SYNTH_TIMEOUT_SECONDS = 180`。客户端短于 180 秒会在服务器写出 504 之前自己断开，从而看不到 JSON 错误。200 秒只是为了盖住这 180 秒，不是实测速度，也不是 SLA。

重试策略：

- 同一进程同一时间只保持一个合成请求
- 400 改请求，不重试原正文
- 429 等待 `Retry-After` 的 2 秒后再发
- 503 不紧循环。`model_not_ready` 和 `voices_incomplete` 重试也不会下载权重
- 500 `worker_failed` 最多隔开再试一次。新的请求会启动新 worker
- 504 期间 `busy` 可能仍为 true。等健康检查里 `busy` 为 false 后，再决定是否重试一次
- 任何非 200 都先按 JSON 解析。只有状态 200 且 `Content-Type` 以 `audio/wav` 开头才写入文件。可再确认文件以 `RIFF` 开头

## 9. 可复制的调用示例

下面的 URL 都是 `http://127.0.0.1:8800`。示例文本是请求内容，不是耗时数据。

### 9.1 健康检查和音色清单

Windows 命令行请用 `curl.exe`。PowerShell 里的 `curl` 可能是 `Invoke-WebRequest` 的别名。

```bat
curl.exe -sS http://127.0.0.1:8800/api/health
curl.exe -sS http://127.0.0.1:8800/api/voices
curl.exe -sS "http://127.0.0.1:8800/api/voices?engine=pocket"
```

### 9.2 Windows：用 UTF-8 文件发合成

先把 JSON 存成 UTF-8 文件 `tts-request.json`，再让 curl 按字节发送。这样不会受 PowerShell 代码页影响。

Piper 中文，兼容旧客户端：

```json
{"text":"银行行长到了重庆。"}
```

```bat
curl.exe -sS -D tts-headers.txt -o tts-out.wav -H "Content-Type: application/json; charset=utf-8" --data-binary "@tts-request.json" http://127.0.0.1:8800/api/tts
```

看 `tts-headers.txt` 的第一行。不是 `HTTP/1.1 200` 时，`tts-out.wav` 里是 JSON 错误，删掉它，不要播放。是 200 时，响应头里应有 `X-Engine: Piper-zh` 和 `X-Voice: zh_CN-chaowen-medium`。

英语女声：

```json
{"engine":"piper","text":"Hello. This is the local English voice.","language":"en","voice":"en_US-ljspeech-medium"}
```

英语男声：

```json
{"engine":"piper","text":"Hello. This is the local English voice.","language":"en","voice":"en_US-norman-medium"}
```

日语女声是 speaker 0，男声是 speaker 1：

```json
{"engine":"piper","text":"こんにちは。","language":"ja","voice":"ja_JP-hi_fi_captain-medium","speaker":0}
```

```json
{"engine":"piper","text":"こんにちは。","language":"ja","voice":"ja_JP-hi_fi_captain-medium","speaker":"male"}
```

Pocket alba。`variant` 可以省略，省略后仍是 18.2M：

```json
{"engine":"pocket","text":"Hello.","language":"en","voice":"alba"}
```

Pocket 另一个内置音色：

```json
{"engine":"pocket","text":"Hello.","language":"english","voice":"marius","variant":"english_18m_2026-10"}
```

这两段 Pocket 请求都要等上一段返回后再发。若 `marius` 的 `prepared` 为 false，响应是 503 `voices_incomplete`，不会在这次请求里下载。

### 9.3 Python requests

```python
import requests

base = "http://127.0.0.1:8800"
health = requests.get(f"{base}/api/health", timeout=10)
health.raise_for_status()
print(health.json()["serviceVersion"], health.json()["busy"])

body = {
    "engine": "piper",
    "text": "Hello. This is the local English voice.",
    "language": "en",
    "voice": "en_US-norman-medium",
}
response = requests.post(f"{base}/api/tts", json=body, timeout=200)
content_type = response.headers.get("Content-Type", "")
if response.status_code != 200 or not content_type.startswith("audio/wav"):
    print(response.status_code, response.json())
else:
    open("norman.wav", "wb").write(response.content)
    print(response.headers.get("X-Sample-Rate"), response.headers.get("X-Synth-Seconds"))
```

`timeout=200` 盖住服务端 180 秒等待。`json=` 会发送 `application/json`。

### 9.4 浏览器 fetch 和 Node fetch

浏览器会带 `Origin`。页面来源必须被服务允许，否则 HTTP 403。当前远端源码允许的来源只有本服务自己的端口和 8787，见第 10 节。Node 服务端和 curl 通常不带 `Origin`，源码只在 `Origin` 存在且不在允许列表时拒绝。Host 仍然必须是 `127.0.0.1:8800` 或 `localhost:8800`。

浏览器：

```javascript
const response = await fetch("http://127.0.0.1:8800/api/tts", {
  method: "POST",
  headers: {"Content-Type": "application/json; charset=utf-8"},
  body: JSON.stringify({
    engine: "pocket",
    text: "Hello.",
    language: "en",
    voice: "alba",
  }),
});
const type = response.headers.get("Content-Type") || "";
if (!response.ok || !type.startsWith("audio/wav")) {
  const error = await response.json();
  throw new Error(error.error || response.statusText);
}
const blob = await response.blob();
const audio = new Audio(URL.createObjectURL(blob));
audio.controls = true;
document.body.append(audio);
```

Node 18 及以上，在同一台机器上调用。不要并发 `await` 两段合成：

```javascript
const response = await fetch("http://127.0.0.1:8800/api/tts", {
  method: "POST",
  headers: {"Content-Type": "application/json; charset=utf-8"},
  body: JSON.stringify({text: "银行行长到了重庆。"}),
  signal: AbortSignal.timeout(200000),
});
const type = response.headers.get("content-type") || "";
if (!response.ok || !type.startsWith("audio/wav")) {
  console.error(response.status, await response.json());
} else {
  const fs = await import("node:fs/promises");
  await fs.writeFile("chaowen.wav", Buffer.from(await response.arrayBuffer()));
  console.log(response.headers.get("x-voice"), response.headers.get("x-sample-rate"));
}
```

### 9.5 C# HttpClient

```csharp
using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(200) };
using var health = await client.GetAsync("http://127.0.0.1:8800/api/health");
health.EnsureSuccessStatusCode();

var json = """{"engine":"piper","text":"こんにちは。","language":"ja","voice":"ja_JP-hi_fi_captain-medium","speaker":1}""";
using var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
using var response = await client.PostAsync("http://127.0.0.1:8800/api/tts", content);
var mediaType = response.Content.Headers.ContentType?.MediaType;
if (!response.IsSuccessStatusCode || mediaType != "audio/wav")
{
    Console.WriteLine((int)response.StatusCode);
    Console.WriteLine(await response.Content.ReadAsStringAsync());
    return;
}
await File.WriteAllBytesAsync("ja-male.wav", await response.Content.ReadAsByteArrayAsync());
```

## 10. Host、CORS 和鉴权

本进程的绑定和 Host 检查都限制在回环地址。已部署端口是 8800 时，`Host` 只能是 `127.0.0.1:8800` 或 `localhost:8800`。其他 Host 返回 403，正文是 `只接受本机回环地址。` 启动参数若把 `--host` 设成局域网或公网地址，进程直接拒绝启动。

远端提交 `dfb62eb` 的 CORS 允许来源只有：

- `http://127.0.0.1:8800`
- `http://localhost:8800`
- `http://127.0.0.1:8787`
- `http://localhost:8787`

带了其他 `Origin` 的浏览器请求返回 403，正文是 `这个来源不能调用 Piper 服务。` 不带 `Origin` 的 curl、Python、Node 服务端和 HttpClient 不受这条来源列表限制，但仍受 Host 和回环绑定限制。

用户本机曾经在本地改过 CORS，允许这两行，并且当时实测通过：

- `http://127.0.0.1:8133`
- `http://localhost:8133`

这两行不在远端 `dfb62eb` 源码里。第三方按仓库集成时不要假设 8133 可用。若调用发生在那台仍保留本地改动的机器上，浏览器从 8133 打开页面可能被允许；这是配置差异，不是本文新增的接口能力。除此之外的 Origin，按源码是 403。

源码没有 API key，也没有 `Authorization` 或 Bearer 检查。不要在请求里发明令牌。令牌不会被读取，多出来的 JSON 字段反而会 400。

本服务目前不能给其他电脑或云端直接调用。若以后要给公网或跨机器使用，需要另做受控反向代理或网关，由那个网关负责 TLS、身份认证、限流，并按实际域名调整 Host 与 CORS。本文不提供该网关的配置，也不存在可以交给第三方的公网 URL。不要通过伪造 Host 头绕过回环检查；那样做也到不了另一台机器，因为进程没有在那些地址上监听。

## 11. 许可

这不是法律意见。本机测试能返回 WAV，不等于第三方可以把这些音色放进商业产品。引擎许可和权重许可是分开的，不能写成“全部模型可商用”。

| 对象 | 许可 | 对第三方的含义 |
| --- | --- | --- |
| Piper 实现 | GPL-3.0-or-later | 分发或改造引擎时要单独遵守 GPL。引擎许可不覆盖音色权重 |
| chaowen 录音 | CC0 | 分发微调模型时仍要按底模 CC BY 4.0 署名 Hi-Fi TTS |
| xiao_ya | 非商用 | 不能因为中文默认音色能商用讨论，就把女声也当成可商用 |
| joe | 数据集备注 CC0 | 仍要单独处理引擎 GPL。性别未知 |
| ljspeech、norman | 公有领域权重 | 模型卡分别写了女声和男声。引擎 GPL 仍在 |
| 日语 hi-fi-captain | CC BY-NC-SA 4.0 | 非商用 |
| 韩语 kss | CC BY-NC-SA 4.0 | 非商用。没有男声 |
| 法语 siwis | CC BY 4.0 | 需要署名。性别未知 |
| Pocket 代码 | MIT | 只覆盖 pocket-tts 代码 |
| Pocket 权重 `kyutai/pocket-tts` | CC BY 4.0，且 Hugging Face gated | 要接受仓库许可后才能准备权重。每个内置音色还有各自的上游声音许可，本服务没有收成一个总的商用授权 |

商业应用在接入前要自己做许可审查。服务返回 200 只说明本机文件和进程能合成。

## 12. 2026-11-16 已经发生的本机事实

以下都是那一天已经做过的事，不是 2026-11-17 重测，也不是通用 SLA：

- `dfb62eb` 的统一接口部署在 `http://127.0.0.1:8800`
- Pocket 27 个内置音色对 `Hello.` 的结构验收成功，采样率 24000
- 对照页上同一段英语可以分别播放 Piper 和 Pocket
- Piper 回归当时通过
- 结构成功不等于音质已经听审通过
- 当时各音色的合成耗时不能当成承诺，也不能把不同文本长度或第一次加载缓存放在一起比速度

2026-11-17 写本文时没有再次请求 8800，没有重启服务，也没有确认进程仍在。

## 13. 常见问题

**调用 8791 得到旧行为或连不上。** 8791 是这台机器上的 Cursor 旧服务。统一 API 用 8800。源码默认端口仍写着 8791，那只是没传 `--port` 时的默认值。

**多传了 `speed` 或 `format`。** 400 `bad_request`。只保留第 5 节的六个键。

**页面要 Ctrl+F5 才看到新对照页。** 那是静态页面缓存。HTTP 客户端调用 `/api/tts` 不需要刷新浏览器，也不需要页面上的缓存版本号。

**8787 的 fetch 返回页面 HTML。** 8787 只提供页面。合成 POST 发到 8800。

**想从另一台电脑访问。** 当前做不到。第 10 节的网关是以后的部署方案，现在没有公网地址。

**Pocket 返回 503 `model_not_ready`。** 标记或虚拟环境未就绪。重试不会下载。已有缓存时也不要据此要求用户重新登录。

**Pocket 返回 503 `voices_incomplete`。** 这个音色还没写入标记。先看 `GET /api/voices?engine=pocket` 的 `prepared`。

**健康检查 `modelReady: true`，但 Pocket 合成失败。** 顶层 `modelReady` 是 Piper 中文文件。Pocket 要看 `engines.pocket.inferenceReady`。文件标记为 true 只说明 `ready.json`，不说明 worker 已经加载成功。

**收到 500 后下一句又成功。** Pocket worker 失败后会被丢弃，下一次请求启动新进程。仍要串行，并先确认正文是 JSON 而不是半截 WAV。

**日语没写 speaker，听起来是女声。** 省略时使用 speaker 0。男声要传 `1` 或 `"male"`。
