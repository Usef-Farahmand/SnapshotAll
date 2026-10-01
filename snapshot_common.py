"""Shared helpers for all SnapshotAll engines."""
import re
import threading
from pathlib import Path

APP_NAME = "SnapshotAll"
APP_VERSION = "1.2.1"
APP_AUTHOR = "Usef Farahmand"
APP_URL = "https://github.com/Usef-Farahmand"
APP_WEBSITE = "https://www.useffarahmand.com/"
APP_REPO = "https://github.com/Usef-Farahmand/SnapshotAll"
APP_LICENSE = "MIT License"

STOP = threading.Event()  # set by the GUI to stop a running job

# Labels of buttons that must never be tapped/clicked automatically
DEFAULT_AVOID = r"delete|remove|log ?out|sign ?out|uninstall|pay|buy|purchase|checkout|reset|erase|wipe"


def emit(a, path, label=""):
    """Tell the GUI (if any) that a new screenshot exists: a.on_item(path, label)."""
    cb = getattr(a, "on_item", None)
    if cb:
        try:
            cb(Path(path), label)
        except Exception:
            pass


def slugify(text, limit=60):
    """Turn arbitrary text into a safe file-name fragment."""
    s = re.sub(r"[^\w\u0600-\u06FF]+", "_", text).strip("_")
    return (s or "home")[:limit]
