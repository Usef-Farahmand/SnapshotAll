# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- CI: pushes to `develop` and pull requests to `main` now build the app and keep the installer, portable zip and checksums as downloadable artifacts (14 days). Public GitHub Releases are still published only from `main` and from version tags. Release tags follow the app version (`v1.3.N`).

## [1.3.0] - 2026-10-02

### Added
- **GIF flows**: one animated GIF per navigation flow (a path from the start page / home screen to a page with nothing further down). Each frame shows the page with a caption of the whole path, the current step highlighted, the page address and a step counter.
- Save step: choose **Screenshots (PNG)**, **GIF flows** or both, with seconds per step, a maximum number of flows and a preview of the flows that will be created. The Save button now lives in the footer so it is always visible.
- Command line: `--gif`, `--gif-seconds`, `--max-flows`.
- The engines now report how each page was reached (parent page and link text; tap trail for apps).
- Unit tests for flows (`tests/test_flows.py`).

## [1.2.2] - 2026-10-01

### Fixed
- Website screenshots sometimes showed the footer (or a cookie banner, chat bubble, sticky bar, side bar) in the middle of the page. Full-page screenshots draw `position: fixed` / `sticky` elements relative to the first screen; they are now tidied before capture: sticky elements return to normal flow, fixed footers move to the end of the page, floating widgets are hidden and fixed headers stay at the top.
- Pages with smooth scrolling (`scroll-behavior: smooth`) were sometimes captured while still scrolling back to the top. Smooth scrolling is now disabled during capture, and the scroll pass waits until lazy-loaded content stops growing.

### Added
- **Tidy floating bars** switch in the website settings (`--keep-floating` on the command line to turn it off).
- Browser regression tests (`tests/`) that run in CI.

## [1.2.1] - 2026-09-30

### Added
- Developer website (<https://www.useffarahmand.com/>) in **Settings → About** and in the README.
- Windows title bar painted in the app's color (Windows 11; Windows 10 gets the dark title bar).
- `CODE_SIGNING.md`: code-signing policy, SmartScreen explanation and the available options (Microsoft Store, low-cost open-source certificate, SignPath Foundation).
- Releases now include `SHA256SUMS.txt`.

### Fixed
- Addresses typed without `https://` or `www.` (for example `example.com`) found only one page when the site redirected to another host form. The crawler now treats `example.com` and `www.example.com` as the same site, follows redirects (including to a different domain) and no longer captures the same page twice under `http://` and `https://`.
- Addresses typed without a scheme now start with `https://` (and fall back to `http://` if it cannot connect); `localhost`, private IPs and `host:port` addresses use `http://`.
- The application icon now appears in the Windows taskbar and title bar (CustomTkinter was replacing it with its own icon); the Settings window uses it too.

## [1.2.0] - 2026-09-30

### Added
- Wizard-style interface with four steps: **Source**, **Settings**, **Scan** and **Save**.
- Live scan page with a progress bar and a preview card for every page or screen found, with per-item selection, *Select all / none* and a *View* button.
- Toolbar with *New capture* and *Settings*; Settings contains the default save location and an About section with the app version and developer.
- Windows app capture (`.exe` / `.jar` / attach to a running window) via UI Automation.
- Project logo, application icon and installer icon.

### Changed
- Modern dark and orange design (rounded cards, sidebar stepper) built with CustomTkinter.
- Screenshots are kept in a temporary folder during the scan and only the selected ones are copied to the chosen save location.
- The app no longer writes log or index files; errors are shown in a *Details* panel with a *Copy details* button.

### Removed
- Folder / local-file source and its buttons. Local sites are captured through `localhost` URLs.

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
