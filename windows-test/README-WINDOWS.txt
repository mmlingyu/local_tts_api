Windows test package for local_tts_api
======================================

This zip is a source and page package. It is not a no-install offline bundle.
The first run needs network access for npm, pip, and the model download.
It does not contain node_modules, a Python virtualenv, browser profiles,
credentials, logs, ONNX weights, or the Phonon executable.

English speech still uses the Phonon files already on your machine. Those files
are not in this zip. The two engines this package can start are:

- Chinese Kokoro, in the browser, after npm ci and node build.cjs
- Optional local Piper Mandarin, after the Python install below

Do not stop whatever is already listening on port 8791. On this project that
port may be Cursor. Choose another free port for Piper, for example 8800.

Layout
------

D:\aispace\local_tts_api\zh-web-service
D:\aispace\local_tts_api\piper-zh-service

Replace that root if you unzip somewhere else. Keep the two directories side
by side.

1. Chinese compare page
-----------------------

Open PowerShell 5.1 in zh-web-service:

    cd D:\aispace\local_tts_api\zh-web-service
    node sync-compare.cjs
    node server.cjs

The compare page does not need npm for the page itself:

    http://127.0.0.1:8787/piper-compare.html

If public\app.js is missing, Kokoro synthesis is not built yet. The page still
opens. To enable Kokoro:

    cd D:\aispace\local_tts_api\zh-web-service
    npm ci
    node build.cjs
    node download-voices.cjs

Then start again with:

    powershell -ExecutionPolicy Bypass -File .\start-zh-web.ps1

The script refuses to move to another port when 8787 is busy. Stop the old
node server.cjs for this directory first. Press Ctrl+F5 after replacing an
old 404.

2. Optional Piper
-----------------

    cd D:\aispace\local_tts_api\piper-zh-service
    py -3 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
    .\.venv\Scripts\python.exe -m piper_zh.download --confirm
    $env:HF_HOME = "D:\aispace\local_tts_api\piper-zh-service\models\hf-home"
    $env:HF_HUB_OFFLINE = "1"
    $env:TRANSFORMERS_OFFLINE = "1"
    $env:HF_HUB_DISABLE_TELEMETRY = "1"
    .\.venv\Scripts\python.exe -m piper_zh --host 127.0.0.1 --port 8800 --device cpu

Or, after the virtualenv exists:

    powershell -ExecutionPolicy Bypass -File .\start-piper-zh.ps1 -Port 8800

Without the downloaded model, Piper still starts and /api/health says the model
is not ready. It does not download weights during a page click.

On the compare page, set Piper address to http://127.0.0.1:8800 and click
"使用这个 Piper 地址". Only loopback http addresses are accepted. The Piper
process allows the page at http://127.0.0.1:8787 to call that port.

3. Licenses
-----------

Piper engine: GPL-3.0-or-later
https://github.com/OHF-Voice/piper1-gpl/blob/d76f335d9eb5dea5ef6d7d70b2d6114e6303fa08/docs/LICENSING.md

zh_CN-chaowen-medium recordings: CC0
https://github.com/OHF-Voice/voice-datasets

Base voice en_US-hifi_tts_92-medium: CC BY 4.0, Hi-Fi TTS reader 92
(Cori Samuel), https://www.openslr.org/109/

Kokoro-82M-v1.1-zh and @uzen/kokoro-js: Apache-2.0.

The engine license does not replace the voice license. This note is not legal
advice.

4. Timing
---------

This package does not include benchmark numbers. Use the compare page on your
own PC. Each result shows full-synthesis seconds, audio duration, and RTF.
RTF is synthesis seconds divided by audio seconds. It is not time-to-first-audio.
