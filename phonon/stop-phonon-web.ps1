$ErrorActionPreference = 'Stop'
try { $health = Invoke-RestMethod 'http://127.0.0.1:8790/api/health' -TimeoutSec 3 } catch { Write-Output 'Phonon web service is not reachable; nothing stopped.'; exit 0 }
if ($health.engine -ne 'Phonon English') { throw 'Different service on port 8790; refusing to stop it.' }
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($health.pid)"
if (!$process -or $process.Name -ne 'node.exe' -or $process.CommandLine -notlike '*D:\aispace\phonon\web\server.cjs*') { throw 'Process identity mismatch; refusing to stop it.' }
Stop-Process -Id $health.pid
Write-Output "Stopped Phonon web service PID=$($health.pid). Kokoro service untouched."
