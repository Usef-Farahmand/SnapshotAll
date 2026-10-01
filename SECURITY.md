# Security Policy

## Supported versions

Only the **latest release** receives security fixes. Please update to the newest version from the [Releases](../../releases/latest) page before reporting.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately using GitHub's *private vulnerability reporting*:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue, how to reproduce it, and its potential impact.

You can expect an initial response within about 7 days. If the report is confirmed, we will work on a fix and credit you in the release notes unless you prefer to stay anonymous.

## Scope notes

SnapshotAll runs a local browser, installs and taps through Android apps on a device you connect, and launches and clicks through Windows apps. Please keep in mind:

- Only test targets you own or have permission to test. App modes click real buttons — use a test account or an emulator, and keep the default *never tap* list.
- Session files (`--storage-state`) contain login cookies. Treat them like passwords and never commit or share them.
- Screenshots may contain sensitive data from the pages or apps you capture. Store and share them carefully.
