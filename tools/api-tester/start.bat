@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0app.py" --host 127.0.0.1 --port 8133
  exit /b %errorlevel%
)
python "%~dp0app.py" --host 127.0.0.1 --port 8133
exit /b %errorlevel%
