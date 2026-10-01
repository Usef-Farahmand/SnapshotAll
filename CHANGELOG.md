# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
