# 本机中文语音合成测试网页

入口： http://127.0.0.1:8787/ 。仅绑定 IPv4 回环地址，不向局域网开放。8787 被占用时启动脚本会选用下一个空闲端口，并显示实际地址。

## 启停

```powershell
powershell -ExecutionPolicy Bypass -File D:\aispace\zh-web-service\start-zh-web.ps1
powershell -ExecutionPolicy Bypass -File D:\aispace\zh-web-service\stop-zh-web.ps1
```

打开页面，输入文字，选择中文女声/男声或英文音色，点击“合成并播放”。生成后可通过音频控件重播，或点击“下载 WAV”。空文本会提示错误，最长 1500 字。支持 0.85/1/1.15 倍语速。

## 实现

- 独立目录。构建使用本目录 `npm install` 锁定的 `@uzen/kokoro-js@1.2.4` 和 `esbuild@0.25.12`，不再读取 `D:\aispace\chickadee\extension\node_modules`。
- `verify.cjs` 仍使用原机器上的 Playwright 与 Edge profile；那条旧测试不是 Piper 对照页的测试。
- 中文模型：onnx-community/Kokoro-82M-v1.1-zh-ONNX，FP32；优先 WebGPU，初始化不可用时回退 WASM。
- ONNX Runtime 的 wasm/mjs（含 asyncify、jsep、jspi）由本机静态托管。COOP/COEP 开启，资源设置 CORP。
- 合成发生在浏览器；Node 仅提供静态文件。没有调用 localhost:8880 或任何语音合成后端。
- 中文音色 zf_001、zf_002、zm_009、zm_010，英文音色 af_maple，均从 Hugging Face 的固定 revision 下载，详见 voice-manifest.json。
- 首次模型加载依赖外网；此后相同浏览器 profile 通常可复用模型缓存。浏览器清理站点数据、换 profile、模型缓存被回收时会重新下载。
- 不会自动添加开机启动；关闭电脑后须重新启动服务。

## 构建、测试

```powershell
cd D:\aispace\zh-web-service
node build.cjs
node download-voices.cjs
node verify.cjs
```

测试使用本机可见 Edge 窗口及先前隔离 profile：
D:\aispace\chickadee\extension\test-output\browser-profile
仅作为浏览器用户目录使用；未读取其中文件做分析。如果该 profile 正被其他 Edge 进程使用，请关闭该隔离浏览器后重试。

测试会真实点击页面，分别合成中文女声、中英混合男声、英文，并下载 WAV、解析 PCM 检查时长、峰值、RMS、非零样本；浏览器另检查原始浮点波形全部有限。最后阻断外网 HTTP(S) 请求并刷新页面，用缓存模型再合成中文，作为“浏览器级断网模拟”，不是关闭电脑网卡。

输出位于 test-output/：results.json、各例 WAV 与截图、browser.log，失败时产生 failure.txt/failure.png。

本目录没有进行 git add、commit 或 push；二进制音色、运行时、bundle、WAV、测试输出、模型缓存均不应提交。npm 缓存约定 D:\aispace\npm-cache，临时目录 D:\aispace\tmp。本程序复用既有依赖，并未 npm install。

## 注意

自动验证能证明合成成功、波形有效，不能代替真人听感验收。中文多音字、数字读法、中英混合发音仍需人工试听。若加载失败，确认网络可访问 Hugging Face、Edge 硬件加速开启，并查看页面错误信息。