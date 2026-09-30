# SnapshotAll

Take screenshots of **every page** of a website (online or local) or **every screen** of an Android app (APK) — from a simple Windows desktop app or the command line.

Created by [Usef Farahmand](https://github.com/Usef-Farahmand).

## Features

- **Websites** (online or `http://localhost:...`): crawls same-site links (plus `sitemap.xml` and SPA hash routes), scrolls to trigger lazy loading, and saves full-page screenshots.
- **Local sites**: point it at a folder or an `.html` file and it serves it automatically.
- **Mobile mode**: emulate a phone viewport.
- **Pages behind login**: supply a Playwright session file.
- **Android APK**: installs the app on an emulator/phone, taps through the UI, and captures every unique screen (with optional scrolling). Dangerous buttons (delete, logout, pay, …) are skipped.
- Output folder with all PNGs plus `index.tsv` (file → URL / tap path) and `log.txt`.

## Browser used

SnapshotAll uses **Microsoft Edge** (built into Windows) or **Google Chrome** if available — no download needed. If neither can be launched, it downloads Chromium once (about 150 MB, needs internet).

## Download (Windows)

Go to **Actions → Build Windows EXE → latest run → Artifacts**:

- `SnapshotAll_Setup` – installer
- `SnapshotAll_Portable` – no-install folder (run `SnapshotAll.exe`)

Windows SmartScreen may warn because the app is not code-signed: **More info → Run anyway**.

## Run from source

```bash
pip install -r requirements.txt
python snapshot_gui.py            # GUI
python snapshot_all.py https://example.com   # command line
```

On Windows you can also just double-click `run_gui.bat` (it sets everything up on first run).

### Command-line examples

```bash
python snapshot_all.py https://example.com
python snapshot_all.py http://localhost:3000 --max-pages 100
python snapshot_all.py ./my-site-folder
python snapshot_all.py https://example.com --mobile
python snapshot_all.py app.apk --max-screens 60 --max-depth 4
```

## Build the EXE yourself

- **GitHub Actions**: push this repo and run the *Build Windows EXE* workflow.
- **Locally on Windows**: double-click `build_exe.bat` → `dist\SnapshotAll\SnapshotAll.exe`.

## APK requirements

`adb` (Android Platform-Tools) or the bundled one from `adbutils`, plus an emulator or a phone with USB debugging enabled and connected.

## Limitations

- Websites: pages reachable only through button clicks or form submissions are not discovered.
- APK: screens that need login or specific input can't be passed automatically — log in manually first and use the *Package name* option. Flutter apps, games and WebViews expose limited UI structure.

## Responsible use

Only capture sites and apps you own or have permission to test.

## License

MIT © Usef Farahmand
