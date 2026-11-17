param([int]$Port=8791)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
Set-Location $root
$py=Join-Path $root '.venv\Scripts\python.exe'
if(!(Test-Path $py)){throw "Python venv not found: $py. Create it with: py -3 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt"}
$busy=Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if($busy){
  Write-Output "Port $Port is already in use. Do not stop Cursor if it owns 8791. Run: powershell -ExecutionPolicy Bypass -File .\start-piper-zh.ps1 -Port 8800"
  exit 1
}
if(-not $env:HF_HOME){$env:HF_HOME=Join-Path $root 'models\hf-home'}
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:HF_HUB_DISABLE_TELEMETRY='1'
& $py -m piper_zh --host 127.0.0.1 --port $Port --device $(if($env:PIPER_DEVICE){$env:PIPER_DEVICE}else{'cpu'})
