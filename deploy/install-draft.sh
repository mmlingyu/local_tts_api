#!/usr/bin/env bash
# Print the install steps. This script never copies a unit or starts a process.
set -euo pipefail
if [[ $# -ne 0 ]]; then
  echo "这个草稿不接受参数，也不会安装服务。" >&2
  exit 2
fi
cat <<'EOF'
这是草稿，没有安装，也没有启动。

未完成，所以不要在目标机器上执行下面的复制：
- piper-zh-service/piper_zh/server.py 的未提交本地改动还没有附上，不能并入。
- POST /api/tts 仍然只接受 engine=piper|pocket。Phonon 还没有接到这个进程。
- 模型、音色和 Pocket 缓存都不在 git 里，本脚本不下载它们。

资产放到检出目录里现有代码已经使用的相对路径，不要写进仓库：
- piper-zh-service/models/          Piper 八个白名单音色、g2pW、日语前端缓存
- pocket-tts-service/.venv/         单独的虚拟环境，CPU 版 torch
- pocket-tts-service/models/hf-home Pocket 缓存。Windows 绝对链接先用 pocket_local.hf_cache 检查
- pocket-tts-service/models/ready.json
- phonon/models/phonon-31m-en/      config.json、tokenizer.json、model.q8.gguf、default-voice.safetensors
- phonon/voices/*.safetensors       清单里的 37 个英文嵌入，每个 256136 字节
- phonon/runtime/ptts-0.7.0-x86_64-unknown-linux-gnu/ptts

Phonon 运行时只从这条官方地址取得，校验和见 phonon/upstream/ptts-0.7.0-SHA256SUMS：
https://github.com/gradium-ai/xn-ptts/releases/download/v0.7.0/ptts-0.7.0-x86_64-unknown-linux-gnu.tar.gz

准备命令，仍要等人确认模型已经拷贝之后才执行：
  phonon/fetch-ptts-linux.sh
  piper-zh-service/.venv 使用 requirements.txt，日语另装 requirements-ja.txt
  pocket-tts-service/prepare-pocket.sh

监听保持 127.0.0.1。不要占用 3080 或 8080。示例环境文件是 deploy/tts-api.env.example。
回滚演练：deploy/rollback-local-tts.sh
真正停掉本单元才加 --apply，并且只影响 local-tts-api.service。
EOF
