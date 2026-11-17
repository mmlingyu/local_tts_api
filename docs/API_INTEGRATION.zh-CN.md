# 语音接口接入说明

本文给调用方使用已经部署的 HTTPS 接口。它只描述 Piper 和 Phonon。Pocket 没有部署，本文不提供它的安装或调用方法。

| 项 | 内容 |
| --- | --- |
| 文档对应提交 | `410532b28e839c77cb5fbf7d760156e487900e4a` |
| 核对的源码 | `piper-zh-service/piper_zh/server.py`、`catalog.py`、`engine.py`，`phonon/linux_runtime.py`、`phonon_bridge.py`，`phonon/voices/manifest.json` |
| 生产事实来源 | 部署方提供的 SSH 与公网实测。写本文时没有再次请求生产，也没有读取或生成令牌 |
| 调用基址 | `https://124.222.128.61` |

成功时正文是整段 WAV。失败时正文是 JSON。先看 HTTP 状态和 `Content-Type`，不要把错误正文存成 WAV。

## 1. 快速开始

1. 向管理员领取令牌，保存到当前用户主目录下的 `.local-tts-api/client-token.txt`。文件只给本人读。本文没有令牌。
2. 只请求 `https://124.222.128.61`。不要先访问 `http://`，不要关闭证书校验。
3. `GET /api/health` 确认进程在，并看 JSON，不要只看状态码 200。
4. 需要 Piper 音色时 `GET /api/voices`。需要 Phonon 时 `GET /api/voices?engine=phonon`。
5. 同一客户端串行调用 `POST /api/tts`。上一段结束再发下一段。
6. 状态不是 200，或 `Content-Type` 不是 `audio/wav` 时，按 JSON 读错误。

推荐用第 8 节的 Python 示例。它从文件读令牌，校验证书，并把超时分开设置。

## 2. 地址、TLS 和边缘

公网调用基址是：

```text
https://124.222.128.61
```

已验证的证书是受信任的 Let's Encrypt 证书，使用者可选名称包含这个 IP。客户端必须校验这条证书。不要使用 `curl -k`、`verify=False` 或任何跳过校验的开关。

80 端口只做 ACME 和 308 跳转。合成请求必须直接发到 HTTPS。先打 HTTP 再跟随跳转，POST 正文可能丢失。

公网路径只有这三个：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/health` | 进程、Piper 语音池、Phonon 文件状态 |
| GET | `/api/voices` | 默认是 Piper 白名单 |
| GET | `/api/voices?engine=phonon` | Phonon 的 default 和 37 个英语音色 |
| GET | `/api/voices?engine=all` | Piper 与 Phonon 放在一起。响应里可能还有未部署的 pocket 键，忽略它 |
| POST | `/api/tts` | 合成一段 WAV |

其他公网路径是 404。不要把 `/piper-compare.html` 或其他页面路径当成这个 HTTPS 主机上的接口。

边缘把上游的 `Host` 设为 `127.0.0.1:8800`。后端只接受 `127.0.0.1:8800` 和 `localhost:8800`。调用方不要自己改 `Host`，也不要去连 8800、3080 或 8080。

`/api/health` 里的 `port` 是后端进程端口，生产上是 8800。它不是给公网客户端填的端口。`access.publicBase` 不是这份源码写进健康检查的字段。若线上响应里出现 `publicBase` 且值为 null，不要把它当成公网基址。公网基址以上面的 `https://124.222.128.61` 为准。

边缘和后端都把请求体限制在 65536 字节，等待整段合成的上限是 180 秒。这是实现里的上限，不是速度承诺。

## 3. 令牌

生产已启用 Bearer 鉴权。没有 `Authorization`，或令牌不对，公网返回 401，正文是：

```json
{"error":"需要 Bearer token。Host 和来源检查仍然有效。","code":"unauthorized"}
```

比较是常量时间比较，格式必须是：

```text
Authorization: Bearer <令牌>
```

`Bearer` 和令牌之间有一个空格。令牌放在请求头里，不放在 JSON、URL、查询字符串或本文里。

管理员从服务器上权限为 600 的 `/root/local-tts-api-client-token` 取出凭据，再交给调用方。那个路径是管理员取凭据的位置，不是客户端要去读的路径。

调用方把同一份凭据保存为：

```text
<当前用户主目录>/.local-tts-api/client-token.txt
```

Windows、Linux 和 macOS 都用主目录，不要写死用户名。文件权限只给本人读。程序只读取第一行并去掉首尾空白。

不要把令牌写进源代码、命令行参数或 shell 历史。`curl -H "Authorization: Bearer $TOKEN"` 会让令牌出现在进程参数里，别人能从进程列表看到。第 8 节的 curl 用权限 600 的配置文件，避免把令牌放进 argv。Python 示例把令牌放在 HTTP 头里，不放进子进程参数。

## 4. 浏览器和 CORS

后端的 CORS 允许来源只有：

- `http://127.0.0.1:8787`
- `http://localhost:8787`
- `http://127.0.0.1:8133`
- `http://localhost:8133`
- 后端自己的 `http://127.0.0.1:8800` 和 `http://localhost:8800`

公网上的网页不在这个名单里。浏览器从其他源直接 `fetch` 会在后端得到 403，正文是 `这个来源不能调用 Piper 服务。` 这条 403 没有 `code`。

不要把令牌放进前端页面、移动应用包或公开的 JavaScript。网页需要语音时，由调用方自己的后端保管令牌，再由那个后端请求本接口。

`OPTIONS` 预检不检查令牌，但仍然检查 Host 和 Origin。允许的请求头是 `Content-Type` 和 `Authorization`。`Access-Control-Max-Age` 为 600 秒。预检成功是 204。这不能让任意网页通过鉴权。

## 5. GET /api/health

`Content-Type` 为 `application/json; charset=utf-8`。模型没准备好时也可以是 HTTP 200。要读 JSON。

顶层先是 Piper 语音池的状态，再附上 `busy`、`port`、`apiVersion`、`engines` 和 `access`。源码在 `410532b` 里把这些字段设成下面的含义。本文不贴一份伪造的生产 JSON。

顶层里和调用有关的稳定事实：

| 字段 | 含义 |
| --- | --- |
| `ok` / `modelReady` | 默认中文音色 `zh_CN-chaowen-medium` 的文件和 g2pW 是否都在。不是八个音色都在内存里，也不是 Phonon |
| `engine` | `piper-zh` |
| `serviceVersion` | `1.1.0`。这是 Piper 语音池的版本 |
| `apiVersion` | `1.2.0`。这是带 Phonon 的 HTTP 层版本 |
| `loadedVoiceIds` / `residentModels` | 当前留在内存里的 Piper 音色 id。默认最多 2 个 |
| `cacheLimit` | 默认 2 |
| `sampleRate` | 白名单给 chaowen 的 22050。单位 Hz |
| `supportsStreaming` | `false` |
| `firstAudioMeasured` | `false`。没有首音时间 |
| `responseMode` | `full-wav` |
| `maxTextChars` | 2000。这是 Piper 上限。Phonon 另是 1000 |
| `hardwareProbe` | `false`。这个接口不探测 GPU |
| `configuredDevice` | 启动参数。生产是 CPU，没有 GPU |
| `busy` | 是否有一段合成还没结束。Piper 和 Phonon 共用 |
| `port` | 后端监听端口。公网客户端仍用 HTTPS 443 |
| `languages` / `voices` | 与默认的 `GET /api/voices` 同一套 Piper 白名单 |
| `pronunciationReviewed` | 固定 `false`。自动 WAV 不是人工听审 |

`engines.piper` 只有 `serviceVersion`、`modelReady`、`loadedVoiceIds`。

`engines.phonon` 里要这样读：

| 字段 | 含义 |
| --- | --- |
| `modelReady` | 四个模型文件都在：`config.json`、`tokenizer.json`、`model.q8.gguf`、`default-voice.safetensors` |
| `runtimeAuthentic` | 磁盘上的 `ptts` 与官方 0.7.0 Linux 可执行文件的 SHA256 一致 |
| `inferenceReady` | 源码固定为 `false` |
| `resident` | 源码固定为 `false`。请求结束后子进程已退出 |
| `lastSynthesisOk` | 本进程里最近一次 Phonon 是否写出过合格 WAV |
| `lifecycle` | `per-request-process` |

`inferenceReady` 和 `resident` 为 `false` 是进程生命周期，不是“现在不能合成”。每次请求都会新起 `ptts`，写完 WAV 就退出。能否合成要看 `modelReady`、`runtimeAuthentic`，以及 `POST` 的结果。

`engines.pocket` 可能出现，并且 `code` 为 `model_not_ready`。那是进程里留下的检查。Pocket 没有部署，不可用。不要调用它，也不要按它的字段重试。

`access` 在这份源码里是：

| 字段 | 含义 |
| --- | --- |
| `bind` | `loopback` |
| `authorization` | 配置了令牌时为 `bearer` |
| `tokenConfigured` | 是否配置了令牌。不返回令牌本身 |
| `origins` | 第 4 节的来源名单 |

## 6. GET /api/voices

查询参数 `engine` 省略时返回 Piper。响应形状来自白名单，没有可提交的模型 URL 或本地路径。

```json
{
  "voices": [],
  "languages": [],
  "cacheLimit": 2,
  "loadedVoiceIds": [],
  "note": "列表来自白名单。没有下载地址字段，页面不能提交远程模型。"
}
```

上面的空数组只说明有哪些键，不是一份真实响应。已核对的生产 `GET /api/voices`（HTTP 200，不含令牌）里，顶层 `voices` 是 8 个对象，音色 id 在 `voice`，不是 `id` 或 `name`。`languages` 是 5 个对象，它们的 `voices` 是字符串 id 数组，不能当成音色对象来读。这份正文约 10 KB。调用方必须读完再解析，不能先截断再当 JSON。每条音色对象还有 `language`、`locale`、`phonemeType`、`sampleRate`、`numSpeakers`、`speakers`、`defaultSpeakerId`、`defaultForLanguage`、`datasetLicense`、`commercialNote`、`gender`、`licenseClass`。日语对象的 `speakers` 是 `{"female": 0, "male": 1}`。`pronunciationReviewed` 固定 `false`。`sampleRate` 八条都是 22050。

`?engine=phonon` 返回 `engine`、`repo`、`revision`、`count`、`presentCount`、`voices`、`modelReady`、`runtimeAuthentic`、`inferenceReady`。`count` 为 38：`default` 再加清单里的 37 个。`inferenceReady` 固定 `false`，理由见上一节。每条有 `id`、`voice`、`name`、`label`、`locale`、`gender`、`language`、`present`、`official`。没有文件路径，也没有下载地址。`repo` 是 `gradium/phonon-voices`，`revision` 是 `0ee17205f254b5abc43b266c8a0f215565c352f7`。

`?engine=all` 返回三个键：`piper`、`phonon`、`pocket`。只用前两个。`pocket` 是未部署遗留，不要读它的音色，也不要据此发请求。

其他 `engine` 值是 HTTP 400，`code` 为 `bad_engine`。

## 7. POST /api/tts

请求头：

```http
Authorization: Bearer <从文件读取的令牌>
Content-Type: application/json
```

`Content-Type` 必须以 `application/json` 开头。正文是 UTF-8 JSON 对象。`Content-Length` 必须是 1 到 65536 的整数。空正文或不合法的长度分别是 413 或 400。

只允许这些键：`text`、`engine`、`language`、`voice`、`speaker`。多一个键，包括 `gender`、`speed`、`format`、`model`、`path`、`url`、`command`，都是 400，`code` 为 `bad_request`。不要传 `variant`。Piper 和 Phonon 见到这个键都是 400。

| 字段 | Piper | Phonon |
| --- | --- | --- |
| `text` | 必填。去掉首尾空白后按 Unicode 码位计 1 到 2000。不能含 U+0000 | 必填。原始字符串按码位计不超过 1000，去掉空白后不能为空。不能含 U+0000。不能含汉字 |
| `engine` | 省略或 JSON `null` 都当作 `piper`。公开取值是小写 `piper` | 必须是小写 `phonon` |
| `language` | 省略则随 `voice`；两者都省略则为 `zh` | 省略则为 `en`。只接受 `en`、`en_us`、`en-us`、`english` |
| `voice` | 省略则用该语言的默认音色。必须是第 9 节的八个 id | 省略则为 `default`。可以是 `default`、第 10 节的名字或 id，比较时忽略大小写 |
| `speaker` | 只有日语可以传。省略时日语用 0。其他音色一出现这个键就是 400 | 一出现这个键就是 400 `speaker_not_allowed` |

Piper 的 `language` 去掉首尾空白并转成小写后：

| 传入 | 归成 |
| --- | --- |
| `zh`、`zh_cn`、`zh-cn` | `zh` |
| `en`、`en_us`、`en-us` | `en` |
| `ja`、`ja_jp`、`ja-jp` | `ja` |
| `ko`、`ko_kr`、`ko-kr` | `ko` |
| `fr`、`fr_fr`、`fr-fr` | `fr` |

`en_GB` 不在 Piper 白名单里。`voice` 和 `language` 同时出现时，语言必须就是该音色的语言，否则 400 `language_voice_mismatch`。

`speaker` 可以是 JSON 整数，或 `female`、`male`。布尔值和小数都不行。日语 `female` 和 `0` 是女声，`male` 和 `1` 是男声。单说话人音色不能带 `speaker`，即使值是 0。

Piper 的文字限制，命中时是 400 `mixed_script`：

- 英语、法语文本里出现汉字、平假名、片假名或韩文音节：拒绝，不拆句
- 日语文本里出现韩文音节：拒绝
- 韩语文本里出现平假名或片假名：拒绝
- 中文不按这个规则拒绝英文字母

Phonon 的汉字范围是 U+3400–U+9FFF。命中时是 400 `han_text`，不会改去调用 Piper。路径、盘符、`http://`、`https://` 和 `hf://` 都不能当 `voice`，结果是 400 `bad_voice`。未知名字是 400 `unknown_voice`。

`engine` 的其他字符串，包括大写的 `Piper`，是 400 `bad_engine`。

## 8. 成功时的 WAV

HTTP 200，`Content-Type: audio/wav`。正文是整段 WAV，不是 JSON，也不是分块音频流。服务在写出前要求 16-bit 单声道。

这些头在源码里按本次 WAV 填写：

| 头 | 含义 |
| --- | --- |
| `X-Audio-Duration` | 秒，六位小数 |
| `X-Synth-Seconds` | 服务端整段合成耗时，六位小数。不是首音，也不含客户端网络时间 |
| `X-RTF` | `X-Synth-Seconds / X-Audio-Duration`，六位小数 |
| `X-Sample-Rate` | 本次 WAV 的采样率，单位 Hz |
| `X-Engine` | Piper 为 `Piper-zh`。Phonon 为 `Phonon-English` |
| `X-Model` | Piper 是音色 id。Phonon 是 `phonon-31m-en` |
| `X-Phoneme-Type` | `pinyin`、`espeak`、`japanese` 或 `phonon` |
| `X-Streaming` | `full-wav` |
| `X-Language` | Piper 为 `zh`、`en`、`ja`、`ko` 或 `fr`。Phonon 为 `en` |
| `X-Voice` | Piper 为音色 id。Phonon 为音色显示名，`default` 或清单里的名字 |
| `X-Speaker-Id` | 仅本次有说话人编号时出现。日语省略 speaker 时也会出现 `0` |
| `X-Voice-ID` | 仅 Phonon 出现，是 `default` 或清单里的 id |
| `X-Audio-Peak` | 仅 Phonon 出现，峰值绝对值相对满幅，九位小数 |
| `Cache-Control` | `no-store` |
| `X-Content-Type-Options` | `nosniff` |

`supportsStreaming` 为 `false`，`X-Streaming` 为 `full-wav`。不要把整段耗时、RTF 或客户端等待时间写成首音，也不要按流式接口去读 `response.body`。

生产实测：八个 Piper 音色都返回过 22050 Hz、16-bit 单声道 WAV。Phonon 的 `default` 和 `Zoey` 都返回过 24000 Hz、16-bit 单声道 WAV。那次实测不是本文新打的请求，也没有记录成速度承诺。

## 9. Piper 的八个音色

生产上这八个都做过真实合成。性别和许可来自源码白名单，不是听感判断。许可说明不是法律意见。Piper 引擎是 GPL-3.0-or-later，引擎许可不覆盖音色权重。

| voice | language | 默认 | gender | speaker | datasetLicense | licenseClass | 调用时要注意 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `zh_CN-chaowen-medium` | zh | 是 | unknown | 不能传 | CC0 | attribution | 录音 CC0。从 Hi-Fi TTS reader 92（CC BY 4.0）微调，分发要署名。模型卡没写性别 |
| `zh_CN-xiao_ya-medium` | zh | 否 | female | 不能传 | Non-commercial | noncommercial | 标贝中文标准女声。非商用。不是默认音色 |
| `en_US-joe-medium` | en | 是 | unknown | 不能传 | CC0 | permissive | 省略英语 voice 时用它。模型卡没写性别。训练链备注为 CC0，引擎 GPL 仍在 |
| `en_US-ljspeech-medium` | en | 否 | female | 不能传 | public domain | permissive | 模型卡写明美国英语女声 |
| `en_US-norman-medium` | en | 否 | male | 不能传 | public domain | permissive | 模型卡写明美国英语男声 |
| `fr_FR-siwis-medium` | fr | 是 | unknown | 不能传 | CC BY 4.0 | unknown | 数据集和底模要按 CC BY 4.0 署名。源码没写性别，`licenseClass` 保持默认的 `unknown` |
| `ja_JP-hi_fi_captain-medium` | ja | 是 | multiple | `female`/`0`，`male`/`1` | CC BY-NC-SA 4.0 | noncommercial | 非商用。省略 speaker 时用 0，响应头会带 `X-Speaker-Id: 0` |
| `ko_KR-kss-medium` | ko | 是 | female | 不能传 | CC BY-NC-SA 4.0 | noncommercial | 非商用。没有官方韩语男声 |

`zh_CN-xiao_ya-medium`、`ja_JP-hi_fi_captain-medium` 和 `ko_KR-kss-medium` 不能用于商业用途。不能因为默认中文音色的录音是 CC0，就把小雅、日语或韩语音色也当成可商用。中文没有已核实男声。韩语没有男声。不要用变调或别的语言补这个缺口。`en_US-lessac-medium` 不在白名单里。

中文前端是 g2pW 拼音。英语、法语、韩语是 espeak。日语是 OpenJTalk，不是 g2pW。

## 10. Phonon 音色

Phonon 只合成英语。文本里有汉字会整段拒绝。上限是 1000 个 Unicode 码位。

`default` 使用模型自带的默认音色。另外 37 个来自仓库 `phonon/voices/manifest.json`，许可字段是 Apache-2.0。这是音色目录的许可，不要把它写成模型权重的许可。权重要另看模型自己的许可。本文不把目录许可说成商业授权。

名字和 id 都可以放进 `voice`。下面按清单顺序列出。`id` 是请求和 `X-Voice-ID` 用的值，`voice` 是显示名。

| voice | id | locale | gender |
| --- | --- | --- | --- |
| default | default | en | 清单没有给 default 填性别 |
| Zoey | NbpkqMVS3CJeq2j8 | en-US | female |
| Juniper | NIWIOv5vTi5eRMj8 | en-US | female |
| Everly | vjFyp2BcCyTlUmYb | en-US | female |
| Harper | 4SZHfMpw-p46Ywgs | en-US | female |
| Hadley | bXwrkHhURL1VFJdG | en-US | female |
| Delia | nGzMHMPAWGaJFHOo | en-US | female |
| Easton | LMDIYE0Oa377Qh6Z | en-US | male |
| Micah | 40QrMVgAxFiUnP9f | en-US | male |
| Trevor | 0zLApsZfVLLNaEGl | en-US | male |
| Russell | _6Aslh2DxfmnRLmP | en-US | male |
| Preston | qIxlZ7Ei8KvWlyQH | en-US | male |
| Miles | d9XCyhjo4JhkHF1d | en-US | male |
| Maeve | 6PWnV0Nq4wu7RVBT | en-GB | female |
| Freya | GgfEkEJtxZR7gnpy | en-GB | female |
| Pippa | uem82D50GRv2Dwma | en-GB | female |
| Elodie-Rose | y9bQqIDnyxwqK01t | en-GB | female |
| Imogen | gDT1nz7Ie36ZhL-C | en-GB | female |
| Lottie | m9MxpY6IUGXtWp76 | en-GB | female |
| Alfie | X6NceqF285Gr04gb | en-GB | male |
| Hugh | YyKcxPG7iIgS3jsK | en-GB | male |
| Edwin | zUCxzrOrugTSis03 | en-GB | male |
| Spencer | JOW0vchyswkQUMDS | en-GB | male |
| Toby | dME3IWyZBvmh1n1q | en-GB | male |
| Teddy | Zn7g6NxLqXlJb7Qi | en-GB | male |
| Bryony | gfP44RlHwr2kEwk7 | en-GB | female |
| Captain Silas Blackwater | xPDpsV3F592srkjA | character | 清单为 null |
| Morwenna of the Deep | nOykTmcH9ydsGGIc | character | 清单为 null |
| Old Mortlake | lX3LavMNdlIbgEHH | character | 清单为 null |
| Azgorath | dGyGDKo2osj7h3s7 | character | 清单为 null |
| Fennick the Young Elf | cXoIXJ2llS8S0WOW | character | 清单为 null |
| The Thing Under the Stairs | GXaSqMEmOg12OIYb | character | 清单为 null |
| Vyrmathrax the Ancient | xO8xQo3BrB8FuI6J | character | 清单为 null |
| Grub the Ogre | cYtsRSxV5q9IMehn | character | 清单为 null |
| Master Aldric | gSgG5Tor0GPEnqzC | character | 清单为 null |
| The Snow Queen | NIWoEurJHMJjyUTe | character | 清单为 null |
| Sir Bramwell | y2eiKxtQo2B67deU | character | 清单为 null |
| Fairy Godmother | QXNr0SvkukLB4wPq | character | 清单为 null |

分组是美式女声 6、美式男声 6、英式女声 7、英式男声 6、角色 12，再加 `default`。角色行的 `gender` 在清单里是 JSON null。生产上 `default` 和 `Zoey` 已做过真实合成。其余 36 个名字以这份清单和 `GET /api/voices?engine=phonon` 为准，本文没有把它们都说成这次听过或合成过。

## 11. 错误和处理

失败正文一般是 `{"error":"...","code":"..."}`。下表写“无”的，是源码没放 `code`。非 200 的正文不是 WAV。

| HTTP | code | 何时 | 客户端做什么 |
| --- | --- | --- | --- |
| 400 | `bad_request` | 多余字段、空文本、类型不对、正文不是 JSON、`Content-Length` 不是整数、Piper 或 Phonon 带了 `variant` | 改请求。不要原样重试 |
| 400 | `bad_engine` | `engine` 不是 `piper`、`phonon` 或 `pocket`。`GET /api/voices` 的查询值同样限制，但那里还接受 `all` | 改请求 |
| 400 | `text_too_long` | Piper 去掉空白后超过 2000 | 缩短文本 |
| 400 | `bad_text` | Phonon 文本为空、超过 1000，或含 U+0000 | 改文本 |
| 400 | `han_text` | Phonon 文本含汉字 | 不要改成 Piper 自动重试 |
| 400 | `unsupported_language` | 语言不在该引擎的允许集合 | 不要换成另一个引擎重试 |
| 400 | `unknown_voice` | id 不在白名单 | 改用清单里的 id |
| 400 | `bad_voice` | Phonon 的 `voice` 不是字符串，或像路径、URL | 改用名字或 id |
| 400 | `language_voice_mismatch` | Piper 的 language 和 voice 不是同一种语言 | 改其中一个 |
| 400 | `speaker_not_allowed` | 非日语带了 speaker，或 Phonon 带了 speaker | 删掉 speaker |
| 400 | `speaker_out_of_range` | 日语 speaker 不是 0、1、`female`、`male` | 改成允许值 |
| 400 | `mixed_script` | Piper 文本脚本不被该语言接受 | 不要自动换音色 |
| 401 | `unauthorized` | 没有令牌或令牌不对 | 检查文件和请求头。不要改去重试同一错误令牌，也不要关掉 TLS 校验 |
| 403 | 无 | Host 不是后端允许的回环名，或 `Origin` 不在允许名单 | 公网程序不要带网页 Origin。不要伪造 Host |
| 404 | 无 | 公网非 API 路径；后端路径不是健康检查、音色清单或 `POST /api/tts` | 检查路径和方法 |
| 413 | 无 | 正文为空，或大于 65536 字节 | 缩小正文 |
| 415 | 无 | `Content-Type` 不是 `application/json` 开头 | 补请求头 |
| 429 | 无 | 上一段还没结束。响应头 `Retry-After: 2` | 至少等 2 秒，串行重试，并做有限的指数退避 |
| 500 | 无 | 未捕获异常，或 WAV 时长无效。`error` 最长约 500 字 | 先读 JSON |
| 500 | `synth_failed` | Phonon 进程失败或没有写出 WAV | 不要紧循环 |
| 500 | `bad_wav` | Phonon 写出的内容不是合格的 16-bit 单声道 WAV | 不要把正文存成 WAV |
| 503 | `model_missing` | Piper 该音色文件不在，或 Phonon 四个模型文件不齐 | 不要在请求里下载 |
| 503 | `frontend_missing` | Piper 前端未就绪，例如缺 g2pW、espeak 数据或日语 OpenJTalk | 不要换前端重试 |
| 503 | `runtime_not_ready` | Phonon 运行时不是官方 Linux 可执行文件 | 不要改用 Windows 的 `ptts.exe` |
| 503 | `voice_file_missing` | Phonon 清单里的这个音色文件不在服务器上 | 换一个 `present` 为 true 的音色，或等操作员补文件 |
| 503 | 可能无 `code` | Piper 语音池被标成未就绪时，正文含 `modelReady: false` | 看 `error` |
| 504 | 无 | 服务等待整段合成超过 180 秒后停止等待。模型可能仍在后台收尾 | 先看 `busy`。变成 false 后再决定是否重试一次 |
| 504 | `timeout` | Phonon 子进程超过 120 秒后被结束 | 同上，不要紧循环 |

400、401、403 不要自动重试原来的请求。429 要排队。客户端同一时间只保持一个合成请求。

建议的客户端超时是连接 10 秒、读取至少 180 秒。Python 示例用读取 200 秒，只为了盖住服务端 180 秒的等待，不是协议承诺，也不是实测速度。短于 180 秒的读取超时会在服务器写出 504 之前自己断开。

`engines.phonon.inferenceReady` 为 false 时不要据此判断故障。那是子进程已经退出。

## 12. 排队

服务同一时间只合成一段。第二段在第一段结束前得到 429，`Retry-After` 的值是字符串 `"2"`，单位秒。边缘等待上限也是 180 秒。机器是 4 个 vCPU、3.6GiB 内存、没有 GPU。Piper 内存里默认最多留 2 个音色。

调用方要自己排队：

1. 上一个 HTTP 响应回来之后再发下一个。
2. 收到 429 后至少等 2 秒。若继续 429，再按 2 秒、4 秒、8 秒退避，设置一个上限后停止，把失败交给人看。
3. 不要并发打同一服务。
4. 400、401、403 不进入退避。

## 13. 示例

示例里的 URL 是生产基址。令牌从主目录文件读取。这些示例只检查了语法和 JSON，没有拿假令牌去请求生产，因此不能当成一次成功调用。

### 13.1 Python

这是推荐的完整示例。`timeout=(10, 200)` 里，10 秒是连接超时，200 秒是读取超时。

```python
from pathlib import Path

import requests

BASE = "https://124.222.128.61"
TOKEN_PATH = Path.home() / ".local-tts-api" / "client-token.txt"


def load_token() -> str:
    token = TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not token or "\n" in token:
        raise RuntimeError("令牌文件必须是一行，且不能为空。")
    return token


def speak(payload: dict, destination: Path) -> None:
    response = requests.post(
        BASE + "/api/tts",
        json=payload,
        headers={"Authorization": "Bearer " + load_token()},
        timeout=(10, 200),
    )
    media = response.headers.get("Content-Type", "")
    if response.status_code != 200 or not media.startswith("audio/wav"):
        raise RuntimeError(f"{response.status_code} {response.text[:500]}")
    if not response.content.startswith(b"RIFF"):
        raise RuntimeError("响应不是 WAV。")
    destination.write_bytes(response.content)


speak({"text": "银行行长到了重庆。"}, Path("chaowen.wav"))
speak(
    {
        "engine": "piper",
        "text": "Hello.",
        "language": "en",
        "voice": "en_US-norman-medium",
    },
    Path("norman.wav"),
)
speak(
    {
        "engine": "piper",
        "text": "こんにちは。",
        "language": "ja",
        "voice": "ja_JP-hi_fi_captain-medium",
        "speaker": "male",
    },
    Path("ja-male.wav"),
)
speak(
    {"engine": "phonon", "text": "Hello.", "voice": "Zoey"},
    Path("zoey.wav"),
)
```

`requests` 默认校验 TLS。不要把 `verify` 设成 `False`。令牌不在 JSON 里。

### 13.2 curl

先把请求 JSON 写成文件。配置文件单独放令牌，权限设为仅本人可读。不要把令牌写进 `-H` 的命令行参数，否则它会出现在进程列表和 shell 历史里。配置文件路径本身可能出现在进程参数里，令牌原文不会。

```bash
umask 077
mkdir -p "$HOME/.config/local-tts-api"
python3 -c 'from pathlib import Path; token=Path.home().joinpath(".local-tts-api/client-token.txt").read_text(encoding="utf-8").strip(); Path.home().joinpath(".config/local-tts-api/curl.cfg").write_text("header = \"Authorization: Bearer %s\"\n" % token, encoding="utf-8")'
printf '%s\n' '{"text":"银行行长到了重庆。"}' > tts-body.json
curl --config "$HOME/.config/local-tts-api/curl.cfg" \
  -D tts-headers.txt \
  -o tts-out.wav \
  -H "Content-Type: application/json" \
  --data-binary @tts-body.json \
  "https://124.222.128.61/api/tts"
```

看 `tts-headers.txt` 的状态行。不是 200，或 `Content-Type` 不是 `audio/wav` 时，删掉 `tts-out.wav`。不要加 `-k` 或 `--insecure`。

### 13.3 Node.js 18 及以上

```javascript
import { readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const base = "https://124.222.128.61";
const tokenPath = path.join(os.homedir(), ".local-tts-api", "client-token.txt");
const token = (await readFile(tokenPath, "utf8")).trim();
const response = await fetch(base + "/api/tts", {
  method: "POST",
  headers: {
    Authorization: "Bearer " + token,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ engine: "phonon", text: "Hello.", voice: "default" }),
  signal: AbortSignal.timeout(200000),
});
const media = response.headers.get("content-type") || "";
if (!response.ok || !media.startsWith("audio/wav")) {
  throw new Error(response.status + " " + (await response.text()));
}
const bytes = Buffer.from(await response.arrayBuffer());
if (!bytes.subarray(0, 4).equals(Buffer.from("RIFF"))) {
  throw new Error("响应不是 WAV。");
}
await writeFile("phonon-default.wav", bytes);
```

Node 的 `fetch` 校验 TLS。不要设置拒绝校验的 agent。这段要放在调用方后端，不要放进浏览器。

### 13.4 Windows PowerShell

Windows 上优先用上一节的 Python。当前环境里 Schannel 取 CRL 可能失败，PowerShell 的 `Invoke-WebRequest` 会受影响。下面这段只说明令牌仍从主目录文件读取，不把令牌写进命令文本。

```powershell
$tokenPath = Join-Path $env:USERPROFILE ".local-tts-api\client-token.txt"
$token = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Uri "https://124.222.128.61/api/health" -Headers $headers
```

合成并保存文件时，用第 13.1 节的 Python。那样可以先确认状态码和 `Content-Type`，再写 WAV。

## 14. 机器和未提供的能力

生产机器是 4 个 vCPU、3.6GiB 内存，没有 GPU。Piper 默认只在内存里保留 2 个音色。这些数字说明服务为什么要串行，不是调用方可以依赖的耗时。

接口不提供流式合成。`supportsStreaming` 是 `false`，成功响应的 `X-Streaming` 是 `full-wav`。

Pocket 没有部署。健康检查里的 `engines.pocket` 可以是未就绪，例如 `code` 为 `model_not_ready`。那不是可用引擎。不要发送 `engine` 为 `pocket` 的请求，本文也不说明怎样安装或调用它。

## 15. 本地自测页

仓库里的 `tools/api-tester/` 是一个只监听本机的小页面。它在本机代理 HTTPS 请求，避免浏览器直接跨域。页面默认填入 `https://124.222.128.61`，令牌框是空的，不会读取 `Path.home() / ".local-tts-api" / "client-token.txt"`，也不会把令牌写进本地存储或网址。启动方式和限制见该目录的 `README.zh-CN.md`。

