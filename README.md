<div align="center">

# SnapshotAll

**Take screenshots of every page of a website — or every screen of an Android app — in one click.**

[![Build](https://github.com/Usef-Farahmand/SnapshotAll/actions/workflows/build.yml/badge.svg)](https://github.com/Usef-Farahmand/SnapshotAll/actions/workflows/build.yml)
[![Latest release](https://img.shields.io/github/v/release/Usef-Farahmand/SnapshotAll?display_name=tag)](https://github.com/Usef-Farahmand/SnapshotAll/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Usef-Farahmand/SnapshotAll/total)](https://github.com/Usef-Farahmand/SnapshotAll/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

[Download](https://github.com/Usef-Farahmand/SnapshotAll/releases/latest) ·
[Report a bug](https://github.com/Usef-Farahmand/SnapshotAll/issues/new?template=bug_report.yml) ·
[Request a feature](https://github.com/Usef-Farahmand/SnapshotAll/issues/new?template=feature_request.yml)

</div>

---

## Table of contents

- [Why SnapshotAll?](#why-snapshotall)
- [Features](#features)
- [Download and install (Windows)](#download-and-install-windows)
- [Quick start](#quick-start)
- [Command-line usage](#command-line-usage)
- [How it works](#how-it-works)
- [Output](#output)
- [Run from source](#run-from-source)
- [Build the installer yourself](#build-the-installer-yourself)
- [Project structure](#project-structure)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Security](#security)
- [Responsible use](#responsible-use)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Why SnapshotAll?

Designers, QA engineers, developers and documentation writers often need a visual record of *every* page or screen of a product: for design reviews, regression checks, client hand-offs or archiving. Doing this by hand is slow. SnapshotAll automates it — give it a URL, a local folder or an `.apk` file and it walks through the product and saves the screenshots for you.

<!-- Add a screenshot of the app here:
![SnapshotAll GUI](docs/screenshot.png)
-->

## Features

**Websites (online or local)**

- Crawls same-site links, reads `sitemap.xml`, and follows SPA hash routes (`#/about`).
- Works with `http://localhost:...` dev servers.
- Point it at a **folder** or an **`.html` file** — it is served automatically, no server setup.
- Full-page screenshots, with auto-scroll so lazy-loaded content appears.
- Desktop or **mobile** (iPhone 13) viewport.
- Capture pages **behind a login** using a Playwright session file.
- Uses **Microsoft Edge / Google Chrome** if installed (no download); otherwise downloads Chromium once.

**Android apps (APK)**

- Installs the APK on an emulator or USB-connected phone.
- Taps through the UI and captures every *unique* screen (detected from the UI hierarchy).
- Optional scrolling captures for long screens.
- Skips risky buttons by default (`delete`, `logout`, `pay`, `buy`, …) — fully configurable.

**Desktop app**

- Simple GUI with live log, **Stop** button, **Copy log** button and one-click access to the results.
- Paste / copy work with any keyboard layout.
- Every run saves an `index.tsv` (file → URL or tap path) and a `log.txt`.

## Download and install (Windows)

1. Open the [**Releases**](https://github.com/Usef-Farahmand/SnapshotAll/releases/latest) page.
2. Download one of:
   - `SnapshotAll_Setup.exe` — installer (Start menu + desktop shortcut)
   - `SnapshotAll_Portable.zip` — no installation; unzip and run `SnapshotAll.exe`
3. Run it.

> **Windows SmartScreen warning?** The app is not code-signed yet. Click **More info → Run anyway**.
> You can always review the source code and build the app yourself (see below).

## Quick start

1. Start SnapshotAll.
2. Enter a website URL (e.g. `https://example.com`, or `http://localhost:3000`), or click **Folder…**, **HTML…**, or **APK…**.
3. Choose an output folder.
4. Click **Start**.
5. When it finishes, click **Open output folder**.

For APK mode, connect an emulator or phone first (see [APK requirements](#apk-requirements)).

## Command-line usage

```bash
python snapshot_all.py <target> [options]
```

`<target>` can be a URL, a local folder / HTML file, or an `.apk` file.

```bash
python snapshot_all.py https://example.com
python snapshot_all.py http://localhost:3000 --max-pages 100
python snapshot_all.py ./my-site-folder
python snapshot_all.py https://example.com --mobile
python snapshot_all.py app.apk --max-screens 60 --max-depth 4
```

| Option | Applies to | Default | Description |
|---|---|---|---|
| `-o, --out` | both | auto | Output folder |
| `--max-depth` | both | web 5 / app 3 | How deep to crawl |
| `--delay` | both | `1.0` | Seconds to wait after each load / tap |
| `--max-pages` | web | `50` | Maximum pages to capture |
| `--width`, `--height` | web | `1440`, `900` | Viewport size |
| `--mobile` | web | off | Emulate a phone (iPhone 13) |
| `--storage-state` | web | – | Playwright session file for logged-in pages |
| `--max-screens` | app | `40` | Maximum screens to capture |
| `--max-clicks` | app | `25` | Max tappable elements tried per screen |
| `--scroll` | app | `3` | Scroll steps captured per screen (`0` = off) |
| `--serial` | app | – | `adb` device serial (if several are connected) |
| `--package` | app | auto | Package name of the app |
| `--avoid` | app | see source | Regex of button labels that must never be tapped |

### Pages behind a login (web)

Record a session once with Playwright, then pass it to SnapshotAll:

```bash
playwright codegen --save-storage=auth.json https://your-site.example/login
# log in in the window that opens, then close it
python snapshot_all.py https://your-site.example --storage-state auth.json
```

## How it works

**Websites** — SnapshotAll launches a headless browser through [Playwright](https://playwright.dev/python/), visits the start page, scrolls it to trigger lazy loading, captures a full-page PNG, collects same-origin links, and repeats breadth-first until it reaches the page or depth limit.

**Android apps** — SnapshotAll installs the APK with `adb`, launches it with [uiautomator2](https://github.com/openatx/uiautomator2), fingerprints each screen from its UI hierarchy, and explores by tapping clickable elements breadth-first (restarting the app and replaying the tap path for each branch). Each new fingerprint becomes one screenshot.

## Output

```
SnapshotAll_Output/
└── example_com_20260930_101500/
    ├── 001_home.png
    ├── 002_about.png
    ├── 003_pricing.png
    ├── index.tsv        # file name → URL (web) or tap path (app)
    └── log.txt          # full run log
```

## Run from source

Requirements: **Python 3.10+**.

```bash
git clone https://github.com/Usef-Farahmand/SnapshotAll.git
cd SnapshotAll
pip install -r requirements.txt
python snapshot_gui.py
```

On Windows you can also double-click `run_gui.bat` — it creates a virtual environment and installs everything on first run.

### APK requirements

- `adb` (Android Platform-Tools) in your `PATH` — or the copy bundled with the `adbutils` package, which SnapshotAll uses automatically.
- An Android emulator (e.g. Android Studio AVD) or a phone with **USB debugging** enabled, visible in `adb devices`.

## Build the installer yourself

**With GitHub Actions (recommended).** Push to `main` (or run the *Build Windows EXE and Release* workflow manually). The workflow builds the app with PyInstaller, creates the installer with Inno Setup, and publishes both to a GitHub Release.

**Locally on Windows.** Double-click `build_exe.bat` → `dist\SnapshotAll\SnapshotAll.exe`. To also create the installer, install [Inno Setup](https://jrsoftware.org/isinfo.php) and compile `installer.iss`.

## Project structure

```
SnapshotAll/
├── snapshot_all.py        # screenshot engine + command-line interface
├── snapshot_gui.py        # Tkinter desktop app
├── installer.iss          # Inno Setup installer script
├── run_gui.bat            # run the GUI from source on Windows
├── build_exe.bat          # build the exe locally on Windows
├── requirements.txt
└── .github/               # CI, release workflow, issue & PR templates
```

## Limitations

- **Websites:** pages reachable only through button clicks or form submissions are not discovered; pages that require CAPTCHAs or bot-protection may block the crawler.
- **Android:** screens that require login or specific input can't be passed automatically — log in manually first, then run with the app's package name. Flutter apps, games and WebViews expose limited UI structure, so screen detection is weaker there.
- No code signing yet, so Windows SmartScreen may warn on first launch.

## Troubleshooting

| Problem | Fix |
|---|---|
| "No usable browser found" | SnapshotAll downloads Chromium automatically on first need (internet required). Or install Microsoft Edge / Google Chrome. |
| `adb not found` / no device | Start an emulator or connect a phone with USB debugging, and check `adb devices`. |
| Ctrl+V doesn't paste | Use right-click → Paste, or the **Paste** button next to the URL field. |
| Need to share an error | Click **Copy log**, or attach the `log.txt` from your output folder to an issue. |

## Contributing

Contributions are very welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and follow the [Code of Conduct](CODE_OF_CONDUCT.md). Good first steps: try the app and [open an issue](https://github.com/Usef-Farahmand/SnapshotAll/issues/new/choose) with bugs or ideas.

## Security

Found a vulnerability? Please do **not** open a public issue — see [SECURITY.md](SECURITY.md).

## Responsible use

Only capture websites and apps that you own or have explicit permission to test. Respect terms of service, `robots.txt` policies and applicable laws. The authors are not responsible for misuse.

## License

Released under the [MIT License](LICENSE) © 2026 [Usef Farahmand](https://github.com/Usef-Farahmand).

## Acknowledgments

- [Playwright for Python](https://playwright.dev/python/) — browser automation
- [uiautomator2](https://github.com/openatx/uiautomator2) — Android UI automation
- [PyInstaller](https://pyinstaller.org/) and [Inno Setup](https://jrsoftware.org/isinfo.php) — packaging
