# Contributing to SnapshotAll

Thanks for taking the time to contribute! This document explains how to report issues, propose changes and set up a development environment.

By participating you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug** — use the [bug report form](../../issues/new?template=bug_report.yml). Include your OS, app version, the target type (website / APK / Windows app) and the error text (Scan page → **Details → Copy details**).
- **Suggest a feature** — use the [feature request form](../../issues/new?template=feature_request.yml).
- **Improve the docs** — typos, clearer explanations and examples are always welcome.
- **Send a pull request** — see below.

For larger changes, please open an issue first so we can agree on the approach before you invest time.

## Development setup

Requirements: Python 3.10+.

```bash
git clone https://github.com/Usef-Farahmand/SnapshotAll.git
cd SnapshotAll
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python snapshot_gui.py                 # GUI
python snapshot_all.py https://example.com   # CLI
```

## Code layout

- `snapshot_gui.py` — wizard-style desktop app (customtkinter)
- `snapshot_all.py` — CLI plus website and Android engines
- `snapshot_desktop.py` — Windows app engine
- `snapshot_common.py` — shared helpers (stop flag, `emit`, slugify, app name/version/author)

Every engine exposes `run_*(target, out_dir, args)`, checks `snapshot_common.STOP` so the GUI can stop it, and reports each new screenshot through `snapshot_common.emit(args, path, label)` — that is how the GUI shows live previews.

## Guidelines

- **Language:** all user-facing text (GUI labels, messages, README) is **English**.
- **Theme:** the GUI is dark with an orange accent — reuse the color constants at the top of `snapshot_gui.py`.
- **Style:** follow PEP 8; keep functions small and readable; add short comments for non-obvious logic.
- **Scope:** keep pull requests focused — one logical change per PR.
- **Dependencies:** avoid adding new dependencies unless clearly necessary.
- **Safety:** the APK explorer must never perform destructive actions by default; keep the default `--avoid` list conservative.

### Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add PDF export of all screenshots
fix(gui): keep the Stop button enabled while a page loads
docs: clarify APK requirements
build: bump PyInstaller
ci: run lint on pull requests
refactor: split web crawler into its own module
```

## Testing your change

Browser tests for full-page capture live in `tests/` (`pip install playwright pytest && playwright install chromium && python -m pytest`). Everything else is checked manually — before opening a PR please check:

- [ ] `python -m py_compile snapshot_*.py` passes
- [ ] Website mode works on a real URL and on a `localhost` server
- [ ] (If you touched APK code) APK mode works on an emulator or phone
- [ ] (If you touched Windows-app code) it works on a real Windows app, e.g. Notepad in attach mode
- [ ] The GUI wizard works end to end: Source → Settings → Scan (previews, selection, **Stop**) → Save
- [ ] No non-English text was added to the UI

## Pull request process

1. Fork the repo and create a branch: `git checkout -b feat/my-change`.
2. Make your changes and commit using Conventional Commits.
3. Push and open a pull request against `main`; fill in the PR template.
4. A maintainer will review it. Please respond to feedback — small follow-up commits are fine.

Releases are built automatically by GitHub Actions when changes land on `main`.

## Questions?

Open a [discussion or issue](../../issues) — happy to help.
