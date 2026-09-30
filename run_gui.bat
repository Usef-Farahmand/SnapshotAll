@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Install it from python.org and tick "Add to PATH".
  pause
  exit /b 1
)
if not exist .venv (
  echo First run: installing requirements, please wait...
  python -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
python snapshot_gui.py
