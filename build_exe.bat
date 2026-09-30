@echo off
cd /d "%~dp0"
python -m venv .venv-build
call .venv-build\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --onedir --windowed --name SnapshotAll --collect-all playwright --collect-all uiautomator2 --collect-all adbutils snapshot_gui.py
echo.
echo Done: dist\SnapshotAll\SnapshotAll.exe
pause
