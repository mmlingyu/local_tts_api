# Phonon English 本地网页服务

首页：http://127.0.0.1:8787/ （原中文测试页面，英文默认 Phonon）
独立英文页：http://127.0.0.1:8790/
试听对比：http://127.0.0.1:8790/compare.html
更新后请 Ctrl+F5 强制刷新。所有服务仅绑定 127.0.0.1，不对局域网开放，不使用 8880。

## 音色
已安装官方 gradium/phonon-voices 的全部 37 个英文音色，加模型原有 default，共 38 个选项。
分组：美式女声 6、美式男声 6、英式女声 7、英式男声 6、角色 12。
首页选择英文示例 → 引擎自动 Phonon → 在音色下拉中选择 Zoey / Easton / Maeve 等 → 合成并播放。
独立英文页也有同样音色下拉。状态明确显示实际使用的名字。
默认音色继续使用 default，不自动改成 Zoey。
中文或中英混合默认 Kokoro，音色仍为 zf_001、zf_002、zm_009、zm_010、af_maple；Phonon 不能合成中文。

音色目录固定版本：0ee17205f254b5abc43b266c8a0f215565c352f7。
许可 Apache-2.0。只下载 voices.jsonl 元数据和 37 个英文 .safetensors，共 9,477,032 bytes 的嵌入；未下载 samples/*.ogg 或其它语言嵌入。
本地文件：D:\aispace\phonon\voices\<voice-id>.safetensors。
本地清单：voices\manifest.json，含名字、ID、locale、gender、filename。
格式校验：speaker_wavs，F32，shape [1,512,125]，每文件 256136 bytes。
服务始终向 ptts 传本地音色文件，并设置 HF_HUB_OFFLINE=1；合成时不访问 HF，无需登录、克隆或额外编码器。

## 启停
```powershell
powershell -ExecutionPolicy Bypass -File D:\aispace\phonon\start-phonon-web.ps1
powershell -ExecutionPolicy Bypass -File D:\aispace\phonon\stop-phonon-web.ps1
```
只启停 8790 Phonon；不停止或重启 8787 Kokoro。
已有 ptts 0.7.0 官方 Windows x64，CPU q8、4 threads，24 kHz。
模型：D:\aispace\phonon\models\phonon-31m-en，revision 92741c5b07d085ff840e26fea8ce43110b87852f。

## API
GET /api/voices 返回 count=38、固定 catalog revision、voices（id/name/label/locale/gender/language）。
POST /api/tts，JSON：{"text":"Would you like me to leave the window open?","voice":"Zoey"}
voice 可填列表中的名字或 ID，省略时为 default。未知音色返回 400；不接受任意路径。最多 1000 字符，中文拒绝。
返回 WAV；响应头 X-Voice、X-Voice-ID、X-Audio-Duration、X-Synth-Seconds、X-RTF、X-Audio-Peak、X-Sample-Rate。
8790 仅对 http://127.0.0.1:8787 额外开放 CORS，保留 CORP 与 OPTIONS 支持。
GET /api/health 返回 PID、voiceCount、busy 等状态。

## 验收
实际 CLI 成功：Zoey、Easton、Maeve、Fairy Godmother。
实际 8787 浏览器合成：Zoey、Easton；状态与请求参数对应，WAV 不同。
实际 8790 浏览器合成：Maeve；状态、播放器时长正常。另通过公开 API 导出 Maeve 和 Fairy Godmother WAV。
中文示例切回 Kokoro 时，原 5 个音色可见。此次未重复中文合成。compare.html 仍返回 200。
证据：test-output\voices\voice-test-results.json 与各 WAV、截图。
未做人工听音评分；未逐个合成全部 37 音色，但全部 37 嵌入已下载并校验 tensor。
