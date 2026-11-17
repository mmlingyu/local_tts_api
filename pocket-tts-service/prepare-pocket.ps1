# Prepare the isolated Pocket TTS virtualenv. This does not start an HTTP server
# and does not install torch into the Piper virtualenv.
param([switch]$Confirm)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $python) {
  Write-Host "复用已有 .venv，不重新安装 torch。"
} else {
  py -3.12 -m venv .venv
  & $python -m pip install --upgrade pip
  & $python -m pip install -r requirements.txt
  Write-Host "Pocket venv is ready. Windows PyTorch wheels are CPU builds."
  Write-Host "Expect about 2 GB or more for torch, plus the gated model download."
}
Write-Host "已有 models\hf-home 会复用。只有缓存里没有权重时才需要 huggingface-cli login。"
if ($Confirm) {
  & $python -m pocket_local.prepare --confirm --variant english_18m_2026-10
}
