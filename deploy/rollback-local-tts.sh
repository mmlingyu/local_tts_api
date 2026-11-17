#!/usr/bin/env bash
# Dry-run unless --apply is passed. Only local-tts-api.service is in scope.
# Refuses any other argument so this cannot be pointed at DeepSeek or Caddy.
set -euo pipefail
UNIT="local-tts-api.service"
if [[ "$UNIT" != "local-tts-api.service" ]]; then
  echo "单元名被改过，停止。" >&2
  exit 2
fi
if [[ $# -gt 1 ]]; then
  echo "只接受可选的 --apply。不会操作系统里 3080 或 8080 上的服务。" >&2
  exit 2
fi
if [[ $# -eq 1 && "$1" != "--apply" ]]; then
  echo "拒绝参数 $1。不会停止 3080 或 8080 上的已有服务。" >&2
  exit 2
fi
echo "回滚范围只有 ${UNIT}。不停止 DeepSeek（3080）或 Caddy（8080），不删除模型。"
if [[ $# -eq 0 ]]; then
  echo "这是演练，没有调用服务管理器。"
  exit 0
fi
if ! command -v systemctl >/dev/null 2>&1; then
  echo "没有 systemctl，未做任何更改。" >&2
  exit 1
fi
systemctl disable --now "$UNIT"
if [[ -f /var/backups/local-tts-api.service.prev ]]; then
  install -m 0644 /var/backups/local-tts-api.service.prev /etc/systemd/system/local-tts-api.service
  systemctl daemon-reload
  echo "已从 /var/backups/local-tts-api.service.prev 放回单元文件。没有 enable。"
else
  rm -f /etc/systemd/system/local-tts-api.service
  systemctl daemon-reload
  echo "没有上一份单元文件，已删除 ${UNIT} 的单元文件。没有动其他单元。"
fi
