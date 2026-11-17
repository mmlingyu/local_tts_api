# Ubuntu 部署草稿

这份说明只记录已经核对过的事实，以及还不能做的事。它不是一次成功的部署。

## 还没完成

`D:\aispace\local_tts_api\piper-zh-service\piper_zh\server.py` 有一份未提交的本地改动。拷贝被本机执行根目录限制拦住了，没有用别的办法把文件内容转写过来。

因此：

- 仓库里的 `piper-zh-service/piper_zh/server.py` 仍是提交 `dfb62eb` 里的版本，后面的 `c7517cb` 只加了文档，没有改这个文件。
- **不能说用户的本地改动已经保留。** 覆盖层还没到，也就还没有对账。
- 没有改 `server.py`。`POST /api/tts` 现在仍只接受 `engine` 为 `piper` 或 `pocket`。传 `phonon` 会是 HTTP 400，`code` 为 `bad_engine`。
- 没有在目标机器上安装 systemd，没有启动服务，没有改 3080 或 8080 上已有的 DeepSeek 和 Caddy。
- 没有模型文件，所以没有做过任何一次真实合成，也不能把健康检查说成推理就绪。

第三方现在能依赖的请求行为仍以 [`docs/API-INTEGRATION.zh-CN.md`](../docs/API-INTEGRATION.zh-CN.md) 为准。

## 官方 Phonon 0.7.0 Linux 运行时

已核对的上游是 [gradium-ai/xn-ptts v0.7.0](https://github.com/gradium-ai/xn-ptts/releases/tag/v0.7.0)，发布时间 `2026-11-09T11:14:41Z`。

| 文件 | 大小 | SHA256 |
| --- | --- | --- |
| [ptts-0.7.0-x86_64-unknown-linux-gnu.tar.gz](https://github.com/gradium-ai/xn-ptts/releases/download/v0.7.0/ptts-0.7.0-x86_64-unknown-linux-gnu.tar.gz) | 9366828 | `5c0b2b3da0a1e1d64337df865754cefd480102d24c0438f80e3043c8a2bbbcc6` |
| [SHA256SUMS](https://github.com/gradium-ai/xn-ptts/releases/download/v0.7.0/SHA256SUMS) | 712 | `7d401d0a2326b75cea671bbe4a9a4f4e750718f7b2ad22f2ba98279c4e643023` |
| 解压后的 `ptts` | 30323496 | `0ce7735f7c5c6c27de30268a30d1e1f825cd1344e1786935148598f8f09aa555` |

同一份 `SHA256SUMS` 里的 Windows 包 `ptts-0.7.0-x86_64-pc-windows-msvc.zip` 是 `7eda22dc3878937e6db5c52ef98cf8649d22093f90d29b9492aefa4dd38eccd6`。Linux 上不运行 `ptts.exe`。

官方说明要求 glibc 2.35 或更高，以及 x86-64-v3（AVX2、FMA、F16C）。压缩包内的 README 把源码安装写成 `cargo install --path ptts --locked --features cli`。这次没有走源码编译，因为官方 Linux 压缩包可以运行。

这个二进制的 `--help` 把默认模型写成 `hf://gradium/phonon-31m-en@92741c5b07d085ff840e26fea8ce43110b87852f`，和现有 Windows 说明里的模型 revision 相同。它自己的音色目录默认 revision 是 `da6c9ec0d47be8df5c87c730a3aa97187f3229c3`，比仓库里钉住的 `0ee17205f254b5abc43b266c8a0f215565c352f7` 新。服务侧必须把 `--voice-catalog` 指到本地的 `voices.jsonl`，并设置 `HF_HUB_OFFLINE=1`，避免它自己去 Hugging Face 拉模型或另外 65 条非英语目录。

`voices.jsonl` 有 102 行：英语 37、西班牙语 25、德语 13、法语 15、葡萄牙语 12。本地只准备了清单里的 37 个英语嵌入，共 9477032 字节，每个 256136 字节，再加模型自带的 `default`。请求不能提交路径、URL 或 `hf://`。

`phonon/fetch-ptts-linux.sh` 只下载上面的 Linux 压缩包，核对压缩包和可执行文件的 SHA256，再执行 `ptts --version`。它不启动 HTTP，也不读取模型。这次在开发虚拟机上跑过该脚本，输出是 `archive sha256 ok` 和 `ptts 0.7.0`。运行时目录 `phonon/runtime/` 已在 `.gitignore` 里，可执行文件没有进仓库。

## 这次实际跑过的命令

开发虚拟机是 x86_64，glibc 2.39，4 个逻辑 CPU，有 AVX2、FMA、F16C。`ldd` 只看到 `libgcc_s`、`libm` 和 `libc`。

- 下载的压缩包 SHA256 与上表一致，也与 GitHub API 给出的 digest 一致。
- 解压后的 `ptts --version` 输出 `ptts 0.7.0`。`--version` 时读到的 VmRSS 大约 1236 KiB。
- `HF_HUB_OFFLINE=1` 时指定一个不存在的模型目录，进程退出码 1，标准错误是 `no checkpoint`，并且带有 `avx: true, fma` 所在的那一行（`f16c: true`）。没有生成 WAV。退出前读到的 VmRSS 大约 1328 KiB。这只说明它在加载模型之前就退出了，**不是**合成时的内存。
- `deploy/report-host.py` 在这台开发虚拟机上读到：4 个逻辑 CPU，glibc 2.39，AVX2/FMA/F16C 都在，MemTotal 16387328 KiB，MemAvailable 5054644 KiB，SwapTotal 0，磁盘剩余 263917154304 字节。3080 和 8080 都没有在监听。这不是用户描述的那台 3.6GiB、1.9GiB swap、32GiB 剩余磁盘的 Ubuntu 24.04.4，不能把这些数字当成目标机的结果。

没有安装 Piper、Pocket、torch 或 Phonon 模型。Pocket 的 CPU 轮检查只覆盖版本字符串的判断，没有下载 torch。

## 目标机上的资产位置

代码现在按仓库里的相对路径找文件。在 `server.py` 对账之前，不要另造一套它还不读取的根目录。模型不要提交。

| 资产 | 放到检出目录中的位置 |
| --- | --- |
| Piper 八个白名单音色和 g2pW | `piper-zh-service/models/` |
| 日语 OpenJTalk | 装进 Piper 自己的虚拟环境：`pip install -r piper-zh-service/requirements-ja.txt` |
| Pocket 虚拟环境和 CPU torch | `pocket-tts-service/.venv/`，用 `prepare-pocket.sh` |
| Pocket 的 Hugging Face 缓存 | `pocket-tts-service/models/hf-home/` |
| Pocket 就绪标记 | `pocket-tts-service/models/ready.json` |
| Phonon 模型目录 | `phonon/models/phonon-31m-en/`，里面要有 `config.json`、`tokenizer.json`、`model.q8.gguf`、`default-voice.safetensors` |
| 37 个英语嵌入 | `phonon/voices/<清单 filename>` |
| Linux ptts | `phonon/runtime/ptts-0.7.0-x86_64-unknown-linux-gnu/ptts` |

从 Windows 拷来的 Pocket 缓存如果还指着 `D:\` 一类路径，先在缓存副本上跑检查，确认只会把链接改到缓存内部已经存在的 blob：

```bash
python - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "pocket-tts-service")
from pocket_local.hf_cache import plan
for item in plan(Path("pocket-tts-service/models/hf-home")):
    print(item.kind, item.path, item.applied)
PY
```

`applied` 为 false 是因为 `plan` 不改文件。确认每条都能在缓存里找到唯一 blob 之后，再由操作员显式调用 `apply_plan`。这个工具不下载，也不删除 blob。

Piper 仍最多在内存里留 2 个音色。Pocket worker 由现有桥接按需拉起，失败后关掉。Phonon 官方命令是每次起一个进程；HTTP 接上之后也应一次只跑一个引擎，请求结束就退出 `ptts`，不要和 Piper、Pocket 的权重同时留在内存里。这些卸载策略还没有接到 `server.py`，所以现在的进程行为没有变。

目标机大约 3.6GiB 内存。草稿单元把 `MemoryMax` 写成 2G，是为了给已经在跑的服务留余量，不是测得的峰值。4 个 vCPU 上 Phonon 线程默认收成 2，请求不能改。

## 访问

进程继续只绑定 `127.0.0.1` 或 `localhost`。Host 仍只接受这个端口的回环名。不要把绑定改成 `0.0.0.0`，不要把 CORS 改成 `*`，也不要靠删掉检查来对外开放。

`deploy/access_policy.py` 写了以后要用的规则：对外基址必须配至少 16 个字符的 token；额外来源逐条填写，例如以后若要保留用户机器上的 8133，把它写进 `TTS_EXTRA_ORIGINS`，而不是现在就默认放开。**`server.py` 还没有 import 这个模块，所以当前进程不会执行这些新规则。** 现有 8787 和本进程来源的行为没有被这段草稿改变。

不要占用 3080 和 8080。示例端口仍是 8800，因为那是已经部署过的统一 Piper/Pocket 端口；源码默认仍是 8791。这台开发虚拟机没有替目标机选择最终端口。

## 安装和回滚

`deploy/install-draft.sh` 只打印步骤，不复制单元、不启动进程。

`deploy/rollback-local-tts.sh` 默认也是演练。加上 `--apply` 时只处理 `local-tts-api.service`：`disable --now`，若有 `/var/backups/local-tts-api.service.prev` 就放回去，否则删除这个单元文件。它不接受别的参数，不删除模型，也不停止其他服务。这次没有执行 `--apply`。

`deploy/local-tts-api.service` 是草稿。它的 `ExecStart` 仍是现在的 `python -m piper_zh`，也就是还没有 `engine=phonon` 的那个进程。不要 enable。

## 接口示例

下面是**现在**已经在 `server.py` 里的行为，不是 Phonon。

```json
{"text":"银行行长到了重庆。"}
```

```json
{"engine":"pocket","text":"Hello.","language":"en","voice":"alba"}
```

Phonon 接上之后，计划中的请求仍使用白名单里的名字或 ID，不接受路径：

```json
{"engine":"phonon","text":"Hello.","voice":"Zoey"}
```

这条在覆盖层对账并改完路由之前会返回 400。不要把它写成已经可用。成功时仍应是整段 `audio/wav`，失败时仍是 JSON。Phonon 旧的 Windows 页另外还有 `X-Audio-Peak` 和 `X-Voice-ID`；并入同一端口时要沿用那些头，而不是另造一种成功正文。这一步还没做。
