# Contributing to SnapshotAll

Thanks for taking the time to contribute! This document explains how to report issues, propose changes and set up a development environment.

By participating you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report a bug** — use the [bug report form](../../issues/new?template=bug_report.yml). Include your OS, app version, the target type (website / APK) and the log (**Copy log** button, or `log.txt`).
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

## Guidelines

- **Language:** all user-facing text (GUI labels, messages, README) is **English**.
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

There is no automated test suite yet (contributions welcome!). Before opening a PR please check manually:

- [ ] `python -m py_compile snapshot_all.py snapshot_gui.py` passes
- [ ] Website mode works on a real URL **and** on a local folder
- [ ] (If you touched APK code) APK mode works on an emulator or phone
- [ ] The GUI starts, runs a job, and **Stop** works
- [ ] No non-English text was added to the UI

## Pull request process

1. Fork the repo and create a branch: `git checkout -b feat/my-change`.
2. Make your changes and commit using Conventional Commits.
3. Push and open a pull request against `main`; fill in the PR template.
4. A maintainer will review it. Please respond to feedback — small follow-up commits are fine.

Releases are built automatically by GitHub Actions when changes land on `main`.

## Questions?

Open a [discussion or issue](../../issues) — happy to help.
