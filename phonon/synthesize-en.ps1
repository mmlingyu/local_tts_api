param(
  [string]$Text = 'Hello! This is the official Phonon English voice, running locally on this computer.',
  [string]$Output = 'D:\aispace\zh-web-service\test-output\phonon-en-cli.wav'
)
$ErrorActionPreference = 'Stop'
$env:HF_HOME = 'D:\aispace\phonon\cache'
$env:HF_HUB_OFFLINE = '1'
$env:TEMP = 'D:\aispace\phonon\cache'
$env:TMP = $env:TEMP
& 'D:\aispace\phonon\runtime\ptts-0.7.0-x86_64-pc-windows-msvc\ptts.exe' --model 'D:\aispace\phonon\models\phonon-31m-en' --lang en --quant q8 --device cpu --threads 4 --voice 'D:\aispace\phonon\models\phonon-31m-en\default-voice.safetensors' $Text -o $Output
if ($LASTEXITCODE -ne 0) { throw "Phonon exited with code $LASTEXITCODE" }
