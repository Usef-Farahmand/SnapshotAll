@echo off
cd /d "%~dp0"
python -m venv .venv-build
call .venv-build\Scripts\activate
pip install -r requirements.txt pyinstaller
for /f %%v in ('python tools\set_version.py') do set VER=%%v
echo Building SnapshotAll %VER%
pyinstaller --noconfirm --onedir --windowed --name SnapshotAll --icon assets/icon.ico --version-file version_info.txt --add-data "assets;assets" --collect-all customtkinter --collect-all playwright --collect-all uiautomator2 --collect-all adbutils --collect-all pywinauto --collect-all comtypes snapshot_gui.py
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DMyAppVersion=%VER% installer.iss
del _build_version.py version_info.txt 2>nul
echo.
echo Done: dist\SnapshotAll\SnapshotAll.exe  (version %VER%)
if exist Output\SnapshotAll_Setup.exe echo Installer: Output\SnapshotAll_Setup.exe
pause
