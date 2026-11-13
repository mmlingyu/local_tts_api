$ErrorActionPreference = 'Stop'
$root = 'D:\aispace\phonon'
$url = 'http://127.0.0.1:8790'
try { $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 2; if ($health.engine -eq 'Phonon English') { Write-Output "Already running: $url/ PID=$($health.pid)"; exit 0 } } catch {}
$node = (Get-Command node -ErrorAction Stop).Source
foreach ($p in @('runtime\ptts-0.7.0-x86_64-pc-windows-msvc\ptts.exe','models\phonon-31m-en\model.q8.gguf','models\phonon-31m-en\default-voice.safetensors','models\phonon-31m-en\tokenizer.json')) { if (!(Test-Path (Join-Path $root $p))) { throw "Missing asset: $p (no automatic downloads)" } }
$env:HF_HOME = "$root\cache"
$env:HF_HUB_OFFLINE = '1'
$env:TEMP = "$root\cache"
$env:TMP = $env:TEMP
$proc = Start-Process -FilePath $node -ArgumentList "$root\web\server.cjs" -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput "$root\web-server.log" -RedirectStandardError "$root\web-server-error.log" -PassThru
$until = (Get-Date).AddSeconds(12)
do { try { $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 1; if ($health.pid -eq $proc.Id) { Write-Output "Ready: $url/ PID=$($proc.Id)"; exit 0 } } catch {}; if($proc.HasExited){throw 'Server exited. See web-server-error.log'}; Start-Sleep -Milliseconds 250 } while ((Get-Date) -lt $until)
throw 'Server did not become ready. See web-server-error.log'
