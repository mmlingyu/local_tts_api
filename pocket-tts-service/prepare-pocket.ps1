# Prepare the isolated Pocket TTS virtualenv. This does not start an HTTP server
# and does not install torch into the Piper virtualenv.
param([switch]$Confirm)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host "Pocket venv is ready. Windows PyTorch wheels are CPU builds."
Write-Host "Expect about 2 GB or more for torch, plus the gated model download."
Write-Host "Accept https://huggingface.co/kyutai/pocket-tts and run huggingface-cli login before -Confirm."
if ($Confirm) {
  & .\.venv\Scripts\python.exe -m pocket_local.prepare --confirm --variant english_18m_2026-10
}
