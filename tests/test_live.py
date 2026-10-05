"""Browser test for live recording: a flow is replayed in a real browser and written as one GIF."""
import argparse
import os

import pytest

pytest.importorskip("playwright")
from PIL import Image  # noqa: E402

import snapshot_gif as sg  # noqa: E402
import snapshot_live as sl  # noqa: E402

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>{t}</title><style>
body{{margin:0;font-family:sans-serif}} nav{{padding:20px;background:#eee}} nav a{{margin-right:16px}}
section{{height:700px;background:{c};color:#fff;font-size:48px;padding:40px}}
</style></head><body><nav><a href="index.html">Home</a><a href="about.html">About</a><a href="contact.html">Contact</a></nav>
<section>{t}<br><a style="color:#fff" href="{nxt}">Next page</a></section></body></html>"""


@pytest.fixture()
def site(tmp_path):
    for name, title, color, nxt in (("index", "Home", "#f97316", "about.html"), ("about", "About", "#3b82f6", "contact.html"),
                                    ("contact", "Contact", "#22c55e", "index.html")):
        (tmp_path / f"{name}.html").write_text(PAGE.format(t=title, c=color, nxt=nxt), encoding="utf-8")
    return tmp_path


def test_live_recording_creates_one_smooth_gif(site, tmp_path, monkeypatch):
    exe = os.environ.get("SNAPSHOTALL_TEST_CHROMIUM")
    if exe:
        monkeypatch.setattr(sl, "launch_browser", lambda pw: pw.chromium.launch(
            executable_path=exe, args=["--no-sandbox", "--disable-setuid-sandbox"]))
    flow = [{"label": (site / f"{n}.html").as_uri(), "title": t, "kind": "screen", "parent": None, "path": None}
            for n, t in (("index", ""), ("about", "About"), ("contact", "Contact"))]
    a = argparse.Namespace(width=1280, height=800, mobile=False, storage_state=None, keep_floating=False)
    try:
        made = sl.record_flows([flow], tmp_path / "out", a, quality="compact", watermark=True)
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "BrowserUnavailable" in type(e).__name__:
            pytest.skip(f"no browser available: {e}")
        raise
    assert len(made) == 1 and made[0].suffix == ".gif"
    gif = Image.open(made[0])
    assert gif.size == (640, int(sg.H * 640 / sg.W) + int(sg.CAP * 640 / sg.W))
    assert gif.n_frames > 40                                  # moment by moment, not one frame per page
    total_ms = 0
    for i in range(gif.n_frames):
        gif.seek(i)
        total_ms += gif.info["duration"]
    assert total_ms > 5000
