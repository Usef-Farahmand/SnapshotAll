# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-09-30

### Added
- **Folder mode**: renders the content of every file (images, PDFs, text/code, Word/PowerPoint/Excel, archives) directly — no browser.
- **Windows app mode**: capture `.exe` / `.jar` apps, or attach to a running window, via UI Automation.
- Project logo, application icon and installer icon.

### Changed
- New dark and orange GUI with three separate tabs: **Website**, **App (APK / EXE)** and **Folder**.
- Removed the folder/HTML source buttons from the website input; local sites are captured through `localhost` URLs.
- CLI auto-detects the mode (`--mode` to override) and gained folder and desktop options.

## [1.0.0] - 2026-09-30

### Added
- Website crawler with full-page screenshots, sitemap and SPA hash-route support.
- Local folder / HTML file support (served automatically).
- Mobile viewport mode and session-file support for pages behind login.
- Android APK explorer that captures every unique screen, with optional scrolling.
- English Windows desktop GUI with live log, Stop button, Copy log button and keyboard-layout-independent copy/paste.
- Automatic browser selection: Chromium → Microsoft Edge → Google Chrome, with on-demand Chromium download.
- GitHub Actions workflow that builds the exe and installer and publishes them as a GitHub Release.
- Open-source project files: license, contributing guide, code of conduct, security policy, issue and PR templates.
