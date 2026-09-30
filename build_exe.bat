@echo off
cd /d "%~dp0"
set PLAYWRIGHT_BROWSERS_PATH=0
python -m venv .venv-build
call .venv-build\Scripts\activate
pip install -r requirements.txt pyinstaller
playwright install chromium
pyinstaller --noconfirm --onedir --windowed --name SnapshotAll --collect-all playwright --collect-all uiautomator2 --collect-all adbutils snapshot_gui.py
echo.
echo Done: dist\SnapshotAll\SnapshotAll.exe
pause
