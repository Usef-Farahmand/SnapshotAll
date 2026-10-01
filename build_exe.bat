@echo off
cd /d "%~dp0"
python -m venv .venv-build
call .venv-build\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --onedir --windowed --name SnapshotAll --icon assets/icon.ico --add-data "assets;assets" --collect-all customtkinter --collect-all playwright --collect-all uiautomator2 --collect-all adbutils --collect-all pywinauto --collect-all comtypes snapshot_gui.py
echo.
echo Done: dist\SnapshotAll\SnapshotAll.exe
pause
