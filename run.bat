@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv
  if errorlevel 1 exit /b 1
)
if exist wheelhouse (
  .venv\Scripts\python.exe -m pip install --no-index --find-links wheelhouse -r requirements.txt
) else (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m app
