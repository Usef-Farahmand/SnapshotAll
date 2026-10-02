"""Shared helpers for all SnapshotAll engines."""
import re
import threading
from pathlib import Path

APP_NAME = "SnapshotAll"
APP_VERSION = "1.3.0"
APP_AUTHOR = "Usef Farahmand"
APP_URL = "https://github.com/Usef-Farahmand"
APP_WEBSITE = "https://www.useffarahmand.com/"
APP_REPO = "https://github.com/Usef-Farahmand/SnapshotAll"
APP_LICENSE = "MIT License"

STOP = threading.Event()  # set by the GUI to stop a running job

# Labels of buttons that must never be tapped/clicked automatically
DEFAULT_AVOID = r"delete|remove|log ?out|sign ?out|uninstall|pay|buy|purchase|checkout|reset|erase|wipe"


def emit(a, path, label="", parent=None, title="", kind="screen"):
    """Tell the GUI (if any) that a new screenshot exists.

    label   unique name of the page / screen (URL for websites, tap trail for apps)
    parent  label of the page / screen it was reached from (None for the start)
    title   short human name: the text of the link / button that led here
    kind    "screen" for a page or screen, "scroll" for an extra scrolled capture
    """
    cb = getattr(a, "on_item", None)
    if cb:
        try:
            cb(Path(path), label, parent, title, kind)
        except Exception:
            pass


def slugify(text, limit=60):
    """Turn arbitrary text into a safe file-name fragment."""
    s = re.sub(r"[^\w\u0600-\u06FF]+", "_", text).strip("_")
    return (s or "home")[:limit]
