$ErrorActionPreference='Stop'
$f=Join-Path $PSScriptRoot 'service-state.json'
if(!(Test-Path $f)){Write-Output 'No service state';exit 0}
$s=ConvertFrom-Json ([IO.File]::ReadAllText($f))
$p=Get-CimInstance Win32_Process -Filter "ProcessId=$($s.pid)"
if($p -and $p.Name -eq 'python.exe' -and $p.CommandLine -match 'piper_zh'){
 Stop-Process -Id $s.pid;Remove-Item $f;Write-Output "Stopped PID $($s.pid)"
}else{Write-Output 'Recorded process is absent or does not match; nothing stopped'}
