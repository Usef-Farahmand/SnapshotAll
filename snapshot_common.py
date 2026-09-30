"""Shared helpers for all SnapshotAll engines."""
import re
import threading

STOP = threading.Event()  # set by the GUI to stop a running job

# Labels of buttons that must never be tapped/clicked automatically
DEFAULT_AVOID = r"delete|remove|log ?out|sign ?out|uninstall|pay|buy|purchase|checkout|reset|erase|wipe"


def slugify(text, limit=60):
    """Turn arbitrary text into a safe file-name fragment."""
    s = re.sub(r"[^\w\u0600-\u06FF]+", "_", text).strip("_")
    return (s or "home")[:limit]
