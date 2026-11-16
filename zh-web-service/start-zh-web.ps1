param([int]$Port=8787)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
Set-Location $root
if(Test-Path 'D:\aispace\npm-cache'){$env:npm_config_cache='D:\aispace\npm-cache'}
if(Test-Path 'D:\aispace'){
  $env:TEMP='D:\aispace\tmp';$env:TMP=$env:TEMP
  New-Item -ItemType Directory -Force $env:TEMP | Out-Null
}
& node (Join-Path $root 'sync-compare.cjs')
if($LASTEXITCODE -ne 0){throw '对照页复制失败'}
if(Test-Path "$root\service-state.json"){
  $s=ConvertFrom-Json ([IO.File]::ReadAllText("$root\service-state.json"))
  $old=Get-Process -Id $s.pid -ErrorAction SilentlyContinue
  if($old -and $old.ProcessName -eq 'node'){
    Stop-Process -Id $s.pid -Force
    Start-Sleep -Milliseconds 400
  }
}
if(!(Test-Path "$root\public\app.js")){& node "$root\build.cjs";if($LASTEXITCODE -ne 0){throw 'Build failed'}}
$busy=Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if($busy){
  Write-Output "端口 $Port 仍被占用，所以 http://127.0.0.1:$Port/piper-compare.html 可能仍是旧进程返回的 404。没有改到别的端口。"
  $busy | ForEach-Object { Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue | Format-List Id,ProcessName,Path }
  exit 1
}
$env:PORT="$Port"
$p=Start-Process -FilePath (Get-Command node).Source -ArgumentList 'server.cjs' -WorkingDirectory $root -RedirectStandardOutput "$root\server.log" -RedirectStandardError "$root\server-error.log" -WindowStyle Hidden -PassThru
Write-Output "Started PID $($p.Id): http://127.0.0.1:$Port/piper-compare.html"
