param([int]$Port=8787)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$env:npm_config_cache='D:\aispace\npm-cache'
$env:TEMP='D:\aispace\tmp';$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
if(Test-Path "$root\service-state.json"){
 $s=ConvertFrom-Json ([IO.File]::ReadAllText("$root\service-state.json"))
 if(Get-Process -Id $s.pid -ErrorAction SilentlyContinue){Write-Output "Already running: $($s.url)";exit 0}
}
if(!(Test-Path "$root\public\app.js")){& node "$root\build.cjs";if($LASTEXITCODE -ne 0){throw 'Build failed'}}
while(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue){$Port++}
$env:PORT="$Port"
$p=Start-Process -FilePath (Get-Command node).Source -ArgumentList 'server.cjs' -WorkingDirectory $root -RedirectStandardOutput "$root\server.log" -RedirectStandardError "$root\server-error.log" -WindowStyle Hidden -PassThru
Write-Output "Started PID $($p.Id): http://127.0.0.1:$Port/"