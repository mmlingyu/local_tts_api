# 语音接口接入说明

| 项 | 内容 |
| --- | --- |
| 定稿日期 | 2026-11-17（Asia/Shanghai） |
| 接口实现 | `410532b28e839c77cb5fbf7d760156e487900e4a` |
| 公网基址 | `https://124.222.128.61` |
| 支持引擎 | Piper、Phonon |
| 本文范围 | 给接入方调用。不包含部署步骤，也不包含本地自测程序的实现 |

成功时正文是整段 WAV。失败时正文是 JSON。先看状态码和 `Content-Type`，不要把错误正文存成音频。

客户端修复 `6209a8b` 只影响本机自测页如何解析这份 JSON，不改变生产接口。

## 1. 调用约定

公网只使用：

```text
https://124.222.128.61
```

证书由 Let's Encrypt 签发并自动续期，客户端按正常信任链校验。不要使用 `curl -k`、`--insecure` 或 `verify=False`。

80 端口只做跳转。API 必须直接请求 HTTPS，不要先发 HTTP 再跟随跳转，否则 POST 正文可能丢失。

三个路径都要带 Bearer 令牌：

| 方法 | 路径 |
| --- | --- |
| GET | `/api/health` |
| GET | `/api/voices` |
| GET | `/api/voices?engine=phonon` |
| GET | `/api/voices?engine=all` |
| POST | `/api/tts` |

普通应用从自己的后端调用。浏览器页面受 CORS 限制，公网网页不能直接 `fetch` 这个地址。本机自测页通过本地代理访问，当前机器上的代理是 `http://127.0.0.1:8134`（8133 已被占用）。那个代理不是公网 API。

健康检查里如果出现 `publicBase` 且值为 null，不能据此判断服务未上线。公网基址以上面的 HTTPS 地址为准。`410532b` 写进 `access` 的字段是 `bind`、`authorization`、`tokenConfigured`、`origins`。

## 2. 令牌

请求头：

```http
Authorization: Bearer <令牌值>
```

`Bearer` 和令牌之间有一个空格。令牌不放进 URL、JSON 或日志。

本机文件 `Path.home() / ".local-tts-api" / "client-token.txt"` 不是单独一行令牌。它是环境文件，至少包含：

```text
TTS_API_TOKEN=<令牌值>
```

另外还有基址相关的一行。程序必须只取 `TTS_API_TOKEN=` 后面的值。对整个文件做 `strip()` 会把变量名和其他行一起送出去，鉴权会失败。

优先读进程环境变量 `TTS_API_TOKEN`。没有该变量时再解析环境文件。找不到这一行，或等号后面为空，就报错并停止，不要用文件全文顶替。

自测页的令牌框只粘贴令牌值。不要粘贴 `TTS_API_TOKEN=` 前缀，也不要粘贴整份文件。刷新页面后需要重新输入，页面不保存。

缺失或错误令牌返回 HTTP 401：

```json
{"error":"需要 Bearer token。Host 和来源检查仍然有效。","code":"unauthorized"}
```

401 不要原样重试，也不要改成不校验证书。

## 3. 快速开始

下面的 Python 是推荐写法。连接超时 10 秒，读取超时 200 秒。200 秒只为盖住服务端 180 秒等待，不是速度承诺。

```python
import os
from pathlib import Path

import requests

BASE = "https://124.222.128.61"
ENV_PATH = Path.home() / ".local-tts-api" / "client-token.txt"


def load_token() -> str:
    from_env = os.environ.get("TTS_API_TOKEN", "").strip()
    if from_env:
        return from_env
    if not ENV_PATH.is_file():
        raise RuntimeError("没有 TTS_API_TOKEN，也没有环境文件。")
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("TTS_API_TOKEN="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if not value or value.startswith("TTS_API_TOKEN"):
                break
            return value
    raise RuntimeError("环境文件里没有可用的 TTS_API_TOKEN。不要把整份文件当作令牌。")


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
```

`requests` 默认校验 TLS。同一进程请串行调用 `speak`。

## 4. GET /api/health

返回 `application/json; charset=utf-8`。HTTP 200 只说明进程在应答。默认中文音色是否就绪看 `modelReady`，不要只看状态码。

和调用有关的字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `ok` / `modelReady` | bool | 默认音色 `zh_CN-chaowen-medium` 的文件和 g2pW 是否都在 |
| `engine` | string | `piper-zh` |
| `serviceVersion` | string | `1.1.0`，Piper 语音池版本 |
| `apiVersion` | string | `1.2.0`，带 Phonon 的 HTTP 版本 |
| `loadedVoiceIds` | string[] | 当前留在内存里的 Piper 音色，默认最多 2 个 |
| `cacheLimit` | number | `2` |
| `sampleRate` | number | 白名单值 22050 |
| `supportsStreaming` | bool | `false` |
| `firstAudioMeasured` | bool | `false` |
| `responseMode` | string | `full-wav` |
| `maxTextChars` | number | `2000`，这是 Piper 上限 |
| `busy` | bool | 是否有一段合成尚未结束 |
| `port` | number | 后端监听端口。公网客户端仍用 HTTPS 443 |
| `engines.phonon.modelReady` | bool | 四个模型文件是否都在 |
| `engines.phonon.runtimeAuthentic` | bool | `ptts` 是否为官方 Linux 0.7.0 |
| `engines.phonon.inferenceReady` | bool | 固定 `false` |
| `engines.phonon.resident` | bool | 固定 `false` |
| `engines.phonon.lastSynthesisOk` | bool | 本进程最近一次 Phonon 是否写出过合格 WAV |
| `access.authorization` | string | 已配置令牌时为 `bearer` |
| `access.tokenConfigured` | bool | 是否配置了令牌，不返回令牌 |

`inferenceReady` 和 `resident` 为 false，是因为 Phonon 每次请求单独起进程，写完就退出。这不表示不能合成。

脚注：响应里可能仍有 `engines.pocket`，且 `code` 为 `model_not_ready`。Pocket 未部署，不是本文支持的引擎。这也不表示该路由已从进程中删除。不要调用它。

## 5. GET /api/voices

省略 `engine` 时返回 Piper。生产样本是 HTTP 200 的 JSON，约 10151 字节，不含令牌。顶层 `voices` 是 8 个对象。音色 id 在 `voice`。`languages` 是 5 个对象，其中 `voices` 是字符串 id，不是对象。

下面是合法形状。生产响应还有其余 7 个音色对象，字段与第一条相同，本文不重复粘贴整份 10 KB。

```json
{
  "voices": [
    {
      "voice": "zh_CN-chaowen-medium",
      "language": "zh",
      "locale": "zh_CN",
      "phonemeType": "pinyin",
      "espeakVoice": null,
      "sampleRate": 22050,
      "numSpeakers": 1,
      "speakers": {},
      "defaultSpeakerId": 0,
      "defaultForLanguage": true,
      "gender": "unknown",
      "licenseClass": "attribution",
      "datasetLicense": "CC0",
      "pronunciationReviewed": false
    }
  ],
  "languages": [
    {
      "language": "zh",
      "locale": "zh_CN",
      "voices": ["zh_CN-chaowen-medium", "zh_CN-xiao_ya-medium"],
      "defaultVoice": "zh_CN-chaowen-medium"
    }
  ],
  "cacheLimit": 2,
  "loadedVoiceIds": [],
  "note": "列表来自白名单。没有下载地址字段，页面不能提交远程模型。"
}
```

必须读完正文再解析。日语对象的 `speakers` 是：

```json
{"female": 0, "male": 1}
```

`?engine=phonon` 的结构来自 `phonon/linux_runtime.py` 的 `public_voices`，不是 Piper 那份名单。`count` 为 38。每条同时有 `id`、`voice`、`name`。`voice` 和 `name` 对清单音色都是显示名，`id` 才是目录 id。`default` 三条都是 `default`。

```json
{
  "engine": "phonon",
  "repo": "gradium/phonon-voices",
  "revision": "0ee17205f254b5abc43b266c8a0f215565c352f7",
  "count": 38,
  "voices": [
    {
      "id": "NbpkqMVS3CJeq2j8",
      "voice": "Zoey",
      "name": "Zoey",
      "label": "美式女声 · Zoey",
      "locale": "en-US",
      "gender": "female",
      "language": "en",
      "official": true
    }
  ],
  "inferenceReady": false
}
```

请求 Phonon 时，`voice` 可以填显示名或 `id`，比较忽略大小写。`inferenceReady` 在这个接口里也是 false，理由见健康检查。

`?engine=all` 同时给出 `piper`、`phonon` 和 `pocket`。只用前两个。`pocket` 按上一节脚注处理。

其他 `engine` 查询值是 HTTP 400，`code` 为 `bad_engine`。

## 6. POST /api/tts

`Content-Type` 必须以 `application/json` 开头。正文是 UTF-8 对象。`Content-Length` 为 1 到 65536。允许的键只有 `text`、`engine`、`language`、`voice`、`speaker`。多一个键，包括 `speed`、`model`、`path`、`url`、`variant`，都是 400 `bad_request`。

| 字段 | Piper | Phonon |
| --- | --- | --- |
| `text` | 必填。去掉首尾空白后 1 到 2000 个码位。不能含 U+0000 | 必填。原始字符串不超过 1000 个码位，去掉空白后不能为空。不能含 U+0000 或汉字 |
| `engine` | 省略或 JSON null 都是 `piper`。公开取值是小写 `piper` | 小写 `phonon` |
| `language` | 省略则随音色；都省略则为 `zh` | 省略则为 `en`。只接受 `en`、`en_us`、`en-us`、`english` |
| `voice` | 省略则用该语言默认音色。必须是下表八个 id | 省略则为 `default`。可填显示名或目录 id |
| `speaker` | 只有日语可传。省略时用 0 | 出现这个键就是 400 `speaker_not_allowed` |

Piper 的 `language` 去掉空白并转小写后：`zh` / `zh_cn` / `zh-cn` 归为 `zh`；`en` / `en_us` / `en-us` 归为 `en`；`ja` / `ja_jp` / `ja-jp` 归为 `ja`；`ko` / `ko_kr` / `ko-kr` 归为 `ko`；`fr` / `fr_fr` / `fr-fr` 归为 `fr`。`voice` 与 `language` 同时出现时必须是同一种语言，否则 400 `language_voice_mismatch`。

日语 `speaker` 可以是 `female`、`male`、`0` 或 `1`。`female` 与 `0` 是女声，`male` 与 `1` 是男声。布尔值和小数不行。其他 Piper 音色不能带 `speaker`。

英语或法语文本里的汉字、假名或韩文，日语文本里的韩文，韩语文本里的假名，都是 400 `mixed_script`，不会拆句。Phonon 文本里的汉字是 400 `han_text`，不会改去调用 Piper。

合法请求：

```json
{"text":"银行行长到了重庆。"}
```

```json
{"engine":"piper","text":"Hello.","language":"en","voice":"en_US-norman-medium"}
```

```json
{"engine":"piper","text":"こんにちは。","language":"ja","voice":"ja_JP-hi_fi_captain-medium","speaker":"male"}
```

```json
{"engine":"phonon","text":"Hello.","voice":"Zoey"}
```

## 7. 成功时的 WAV

HTTP 200，`Content-Type: audio/wav`。正文是 16-bit 单声道整段 WAV，不是流。

| 头 | 含义 |
| --- | --- |
| `X-Audio-Duration` | 秒，六位小数 |
| `X-Synth-Seconds` | 服务端整段耗时，六位小数。不是首音 |
| `X-RTF` | 上面两项相除，六位小数 |
| `X-Sample-Rate` | 本次 WAV 的采样率 |
| `X-Engine` | Piper 为 `Piper-zh`，Phonon 为 `Phonon-English` |
| `X-Model` | Piper 是音色 id。Phonon 是 `phonon-31m-en` |
| `X-Phoneme-Type` | `pinyin`、`espeak`、`japanese` 或 `phonon` |
| `X-Streaming` | `full-wav` |
| `X-Language` | Piper 为 `zh`、`en`、`ja`、`ko`、`fr`。Phonon 为 `en` |
| `X-Voice` | Piper 为音色 id。Phonon 为显示名 |
| `X-Speaker-Id` | 仅有说话人编号时出现。日语省略 speaker 时为 `0` |
| `X-Voice-ID` | 仅 Phonon，为 `default` 或目录 id |
| `X-Audio-Peak` | 仅 Phonon，九位小数 |
| `Cache-Control` | `no-store` |

`supportsStreaming` 为 false。不要把整段耗时写成首音。

生产上八个 Piper 音色都返回过 22050 Hz、16-bit 单声道 WAV。Phonon 的 `default` 和 `Zoey` 返回过 24000 Hz、16-bit 单声道 WAV。其余 36 个 Phonon 名字没有逐条宣称已合成。

## 8. Piper 八个音色

性别和许可来自白名单与模型卡，不是听感，也不是法律意见。引擎是 GPL-3.0-or-later，不覆盖音色权重。

| voice | 语言 | 默认 | 性别 | speaker | 数据集许可 | licenseClass |
| --- | --- | --- | --- | --- | --- | --- |
| `zh_CN-chaowen-medium` | zh | 是 | unknown | 不能传 | CC0 | attribution |
| `zh_CN-xiao_ya-medium` | zh | 否 | female | 不能传 | Non-commercial | noncommercial |
| `en_US-joe-medium` | en | 是 | unknown | 不能传 | CC0 | permissive |
| `en_US-ljspeech-medium` | en | 否 | female | 不能传 | public domain | permissive |
| `en_US-norman-medium` | en | 否 | male | 不能传 | public domain | permissive |
| `fr_FR-siwis-medium` | fr | 是 | unknown | 不能传 | CC BY 4.0 | unknown |
| `ja_JP-hi_fi_captain-medium` | ja | 是 | multiple | `female`/`0`，`male`/`1` | CC BY-NC-SA 4.0 | noncommercial |
| `ko_KR-kss-medium` | ko | 是 | female | 不能传 | CC BY-NC-SA 4.0 | noncommercial |

`zh_CN-xiao_ya-medium`、`ja_JP-hi_fi_captain-medium`、`ko_KR-kss-medium` 是非商用。不能因为超文录音是 CC0，就把这三条也当成可商用。超文分发仍要按底模 CC BY 4.0 署名。法语 siwis 要按 CC BY 4.0 署名，模型卡没写性别。中文没有已核实男声，韩语没有男声。`en_US-lessac-medium` 不在名单里。

发现新列表时读顶层 `voices[].voice`，并用 `language` 与 `locale` 分组。不要把 `languages[].voices` 里的字符串当成对象。

## 9. Phonon 38 个音色

只合成英语，文本上限 1000 个码位，不能含汉字。`default` 使用模型自带音色。其余 37 个来自 `phonon/voices/manifest.json`，revision `0ee17205f254b5abc43b266c8a0f215565c352f7`。目录许可是 Apache-2.0，这不等于模型权重许可。

| 显示名 voice | id | locale | gender |
| --- | --- | --- | --- |
| default | default | en | null |
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
| Captain Silas Blackwater | xPDpsV3F592srkjA | character | null |
| Morwenna of the Deep | nOykTmcH9ydsGGIc | character | null |
| Old Mortlake | lX3LavMNdlIbgEHH | character | null |
| Azgorath | dGyGDKo2osj7h3s7 | character | null |
| Fennick the Young Elf | cXoIXJ2llS8S0WOW | character | null |
| The Thing Under the Stairs | GXaSqMEmOg12OIYb | character | null |
| Vyrmathrax the Ancient | xO8xQo3BrB8FuI6J | character | null |
| Grub the Ogre | cYtsRSxV5q9IMehn | character | null |
| Master Aldric | gSgG5Tor0GPEnqzC | character | null |
| The Snow Queen | NIWoEurJHMJjyUTe | character | null |
| Sir Bramwell | y2eiKxtQo2B67deU | character | null |
| Fairy Godmother | QXNr0SvkukLB4wPq | character | null |

分组是美式女 6、美式男 6、英式女 7、英式男 6、角色 12，再加 `default`。角色的 `gender` 在清单里是 null。

## 10. 错误

非 200 的正文不是 WAV。写“无”的状态没有 `code`。

| HTTP | code | 何时 | 处理 |
| --- | --- | --- | --- |
| 400 | `bad_request` | 多余字段、空文本、JSON 无效、`Content-Length` 不是整数、带了 `variant` | 改请求，不重试原正文 |
| 400 | `bad_engine` | `engine` 不是小写 `piper` 或 `phonon`。音色查询还接受 `all` | 改请求 |
| 400 | `text_too_long` | Piper 超过 2000 | 缩短 |
| 400 | `bad_text` | Phonon 为空、超过 1000，或含 U+0000 | 改文本 |
| 400 | `han_text` | Phonon 含汉字 | 不要自动改打 Piper |
| 400 | `unsupported_language` | 语言不在该引擎允许集合 | 不要自动换引擎 |
| 400 | `unknown_voice` | 不在白名单 | 改用清单 |
| 400 | `bad_voice` | Phonon 的 voice 像路径或 URL | 改用名字或 id |
| 400 | `language_voice_mismatch` | Piper 的语言和音色不一致 | 改其中一个 |
| 400 | `speaker_not_allowed` | 非日语或 Phonon 带了 speaker | 删掉 speaker |
| 400 | `speaker_out_of_range` | 日语 speaker 不是 0、1、`female`、`male` | 改正 |
| 400 | `mixed_script` | Piper 文本脚本不被该语言接受 | 不要自动换音色 |
| 401 | `unauthorized` | 令牌缺失或错误 | 检查提取出的值。不重试，不关 TLS |
| 403 | 无 | Host 或 Origin 不被接受 | 从后端调用。不要伪造 Host |
| 404 | 无 | 不是上述 API 路径 | 改路径 |
| 413 | 无 | 正文为空或大于 65536 字节 | 缩小 |
| 415 | 无 | Content-Type 不是 JSON | 补请求头 |
| 429 | 无 | 已有一段合成。`Retry-After: 2` | 排队，至少等 2 秒 |
| 500 | 无，或 `synth_failed`、`bad_wav` | 合成失败或 WAV 不合格 | 先读 JSON |
| 503 | `model_missing`、`frontend_missing`、`runtime_not_ready`、`voice_file_missing` | 文件或前端或运行时未就绪 | 不要在请求里下载 |
| 504 | 无，或 Phonon 的 `timeout` | 整段等待超过 180 秒，或 Phonon 子进程超过 120 秒 | 看 `busy` 后再决定是否再试一次 |

400、401、403 不自动重试。

## 11. 排队和机器

同一时间只合成一段。第二段得到 429。收到后至少等 2 秒；若仍是 429，再按 4 秒、8 秒退避，设上限后停止。不要并发。

服务端等待上限是 180 秒。客户端读取超时不要短于 180 秒。建议连接 10 秒、读取 200 秒。没有流式接口。

机器是 4 个 vCPU、3.6GiB 内存，没有 GPU。Piper 默认最多在内存里留 2 个音色。这些数字说明为什么要串行，不是耗时承诺。

## 12. Node.js 18 及以上

放在调用方后端，不要放进浏览器，也不要把令牌写进页面。

```javascript
import { readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const base = "https://124.222.128.61";

function tokenFromText(text) {
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (line.startsWith("TTS_API_TOKEN=")) {
      const value = line.slice("TTS_API_TOKEN=".length).trim().replace(/^['"]|['"]$/g, "");
      if (value && !value.startsWith("TTS_API_TOKEN")) return value;
    }
  }
  return "";
}

async function loadToken() {
  if (process.env.TTS_API_TOKEN && process.env.TTS_API_TOKEN.trim()) {
    return process.env.TTS_API_TOKEN.trim();
  }
  const file = path.join(os.homedir(), ".local-tts-api", "client-token.txt");
  const value = tokenFromText(await readFile(file, "utf8"));
  if (!value) throw new Error("环境文件里没有可用的 TTS_API_TOKEN。");
  return value;
}

const token = await loadToken();
const response = await fetch(base + "/api/tts", {
  method: "POST",
  headers: {
    Authorization: "Bearer " + token,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ engine: "phonon", text: "Hello.", voice: "Zoey" }),
  signal: AbortSignal.timeout(200000),
});
const media = response.headers.get("content-type") || "";
if (!response.ok || !media.startsWith("audio/wav")) {
  throw new Error(response.status + " " + (await response.text()).slice(0, 500));
}
const bytes = Buffer.from(await response.arrayBuffer());
if (!bytes.subarray(0, 4).equals(Buffer.from("RIFF"))) {
  throw new Error("响应不是 WAV。");
}
await writeFile("zoey.wav", bytes);
```

Node 的 `fetch` 校验 TLS。不要安装会跳过校验的 agent。

## 13. curl

先用 Python 把 `TTS_API_TOKEN` 的值写入仅本人可读的 curl 配置。令牌不出现在 curl 的参数里。不要写 `curl -H "Authorization: Bearer $TOKEN"`，那会进入进程列表。

```bash
umask 077
mkdir -p "$HOME/.config/local-tts-api"
python3 - <<'PY'
import os
from pathlib import Path
env = os.environ.get("TTS_API_TOKEN", "").strip()
if not env:
    file = Path.home() / ".local-tts-api" / "client-token.txt"
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("TTS_API_TOKEN="):
            env = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
if not env:
    raise SystemExit("环境文件里没有可用的 TTS_API_TOKEN。")
dest = Path.home() / ".config" / "local-tts-api" / "curl.cfg"
dest.write_text('header = "Authorization: Bearer %s"\n' % env, encoding="utf-8")
PY
printf '%s\n' '{"engine":"phonon","text":"Hello.","voice":"default"}' > tts-body.json
curl --config "$HOME/.config/local-tts-api/curl.cfg" \
  -D tts-headers.txt \
  -o tts-out.wav \
  -H "Content-Type: application/json" \
  --data-binary @tts-body.json \
  "https://124.222.128.61/api/tts"
```

状态行不是 200，或 `Content-Type` 不是 `audio/wav` 时，删掉 `tts-out.wav`。不要加 `-k`。

## 14. Windows PowerShell

Windows 上优先用第 3 节的 Python。本文没有在 PowerShell 里运行过下面的片段，不能把它写成已经跑通。它同样只取 `TTS_API_TOKEN=` 的值。

```powershell
$path = Join-Path $env:USERPROFILE ".local-tts-api\client-token.txt"
$line = Get-Content -LiteralPath $path | Where-Object { $_.Trim().StartsWith("TTS_API_TOKEN=") } | Select-Object -First 1
if (-not $line) { throw "环境文件里没有 TTS_API_TOKEN。" }
$token = $line.Trim().Substring("TTS_API_TOKEN=".Length).Trim().Trim('"')
if (-not $token) { throw "TTS_API_TOKEN 为空。" }
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Uri "https://124.222.128.61/api/health" -Headers $headers
```

保存 WAV 仍用 Python，以便先确认状态码和 `Content-Type`。当前环境里 Schannel 取 CRL 可能影响 `Invoke-WebRequest`。

## 15. 边界

已在生产验证的是：HTTPS 可直接调用、令牌错误为 401、八个 Piper 音色和 Phonon 的 `default` 与 `Zoey` 能返回 WAV。健康检查 200 且默认中文 `modelReady` 为 true。Phonon 清单共 38 条。

未支持或不应依赖的是：流式合成、Pocket、把 `publicBase: null` 当成下线、浏览器从任意网站直接调用、在请求里下载模型、以及把全部 38 个 Phonon 音色都说成已经逐条合成过。
