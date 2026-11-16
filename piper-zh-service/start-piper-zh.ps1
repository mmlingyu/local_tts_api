param([int]$Port=8791)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$py=Join-Path $root '.venv\Scripts\python.exe'
if(!(Test-Path $py)){throw "未找到 $py。请先在 piper-zh-service 执行：python -m venv .venv；.\.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt"}
if(-not $env:HF_HOME){$env:HF_HOME=Join-Path $root 'models\hf-home'}
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:HF_HUB_DISABLE_TELEMETRY='1'
$env:PORT="$Port"
& $py -m piper_zh --host 127.0.0.1 --port $Port --device $(if($env:PIPER_DEVICE){$env:PIPER_DEVICE}else{'cpu'})
