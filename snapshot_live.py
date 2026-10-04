"""
Live recording - replay a flow in a real browser and record it moment by moment.

For every flow the browser opens the first page, scrolls through it, moves a mouse pointer to the link
that leads to the next page, clicks it, cross-fades to the new page and so on. Frames are captured at a
fixed rate while this happens, then written as ONE smooth GIF (with the same caption and watermark as the
slideshow GIFs). Websites only: apps are never launched by SnapshotAll's static modes.
"""
import io
import time
from pathlib import Path

from PIL import Image, ImageDraw

import snapshot_gif as sg
from snapshot_all import SCROLL_JS, TIDY_JS, launch_browser
from snapshot_common import STOP

# output picture width (pixels) and frames per second
QUALITY = {"compact": (640, 8), "standard": (800, 10), "high": (960, 12)}

FIND_LINK_JS = """(target) => {
    const key = u => { try { const x = new URL(u, location.href);
        return x.host.replace(/^www\\./, '').toLowerCase() + (x.pathname.replace(/\\/+$/, '') || '/') + x.search;
    } catch (e) { return ''; } };
    const want = key(target);
    document.querySelectorAll('[data-snapshotall-next]').forEach(e => e.removeAttribute('data-snapshotall-next'));
    const visible = a => { const r = a.getBoundingClientRect(), cs = getComputedStyle(a);
        return r.width > 4 && r.height > 4 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
    const ok = [...document.querySelectorAll('a[href]')].filter(a => key(a.href) === want && visible(a));
    const pick = ok.find(a => !a.closest('nav, header, footer')) || ok[0];
    if (!pick) return null;
    pick.setAttribute('data-snapshotall-next', '1');
    const r = pick.getBoundingClientRect();
    return { top: r.top + window.scrollY, height: r.height };
}"""
NEXT_SELECTOR = "[data-snapshotall-next='1']"
PAGE_HEIGHT_JS = "Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0)"


def _ease(t):
    return t * t * (3 - 2 * t)


def _snap(page):
    return Image.open(io.BytesIO(page.screenshot(type="jpeg", quality=82))).convert("RGB")


def _draw_pointer(view, x, y, ring=0.0):
    """Mouse pointer (and, while clicking, an expanding ring) drawn onto a copy of the frame."""
    img = view.copy()
    d = ImageDraw.Draw(img)
    s = max(view.width / 760.0, 0.8) * 1.15
    if ring > 0:
        r = (10 + 26 * ring) * s
        d.ellipse([x - r, y - r, x + r, y + r], outline=sg.ORANGE, width=max(int(3 * s), 2))
    pts = [(0, 0), (0, 17), (4.5, 13), (8, 21), (11, 19.5), (7.5, 12), (13, 12)]
    d.polygon([(x + px * s, y + py * s) for px, py in pts], fill=(255, 255, 255), outline=(0, 0, 0))
    return img


class _Flow:
    """Collects the frames of one flow."""

    def __init__(self, names, items, k, fps, watermark):
        self.names, self.items, self.k, self.fps, self.watermark = names, items, k, fps, watermark
        self.frame_ms = int(1000 / fps)
        self.frames, self.durations, self.idx = [], [], 0

    def add(self, view, ms=None, idx=None):
        i = self.idx if idx is None else idx
        it = self.items[i]
        self.frames.append(sg.compose_frame(view, self.names, i, sg._location(it, i), self.k, self.watermark))
        self.durations.append(ms or self.frame_ms)


def _prepare(page, keep_floating):
    """Settle a freshly loaded page: load lazy content, switch off smooth scrolling, tidy floating bars."""
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass
    page.evaluate(SCROLL_JS)                       # (not recorded) makes lazy images / content appear
    if not keep_floating:
        page.evaluate(TIDY_JS)
    page.wait_for_timeout(200)


def _scroll(page, rec, y_from, y_to):
    n = max(6, min(int(abs(y_to - y_from) / 45), 40))
    for s in range(1, n + 1):
        page.evaluate("y => window.scrollTo(0, y)", y_from + (y_to - y_from) * _ease(s / n))
        page.wait_for_timeout(15)
        rec.add(_snap(page))


def _record_flow(pw, browser, a, flow, names, k, fps, watermark):
    rec = _Flow(names, flow, k, fps, watermark)
    mobile = bool(getattr(a, "mobile", False))
    keep_floating = bool(getattr(a, "keep_floating", False))
    out_w = int(sg.W * k)
    if mobile:
        kw = dict(pw.devices["iPhone 13"])
        kw["device_scale_factor"] = 1
    else:
        vw, vh = int(getattr(a, "width", 1440)), int(getattr(a, "height", 900))
        kw = {"viewport": {"width": vw, "height": vh}, "device_scale_factor": min(out_w / vw, 1.0)}
    if getattr(a, "storage_state", None):
        kw["storage_state"] = a.storage_state
    ctx = browser.new_context(ignore_https_errors=True, **kw)
    page = ctx.new_page()
    try:
        page.goto(flow[0]["label"], wait_until="domcontentloaded", timeout=30000)
        _prepare(page, keep_floating)
        prev_view = None
        for i, item in enumerate(flow):
            rec.idx = i
            vp = page.viewport_size
            nxt = flow[i + 1]["label"] if i + 1 < len(flow) else None
            view = _snap(page)
            if prev_view is not None:                                   # cross-fade from the previous page
                for t in range(1, 5):
                    rec.add(Image.blend(prev_view, view, t / 5), idx=i - 1 if t <= 2 else i)
            rec.add(view, ms=700)                                       # arrival: hold
            total = max(int(page.evaluate(PAGE_HEIGHT_JS)) - vp["height"], 0)

            link = page.evaluate(FIND_LINK_JS, nxt) if nxt else None
            if link:
                want = max(0.0, min(float(total), link["top"] - vp["height"] * 0.4))
                if want < 80 and total > 0:                             # link is near the top: look around first
                    look = min(float(total), vp["height"] * 0.9)
                    _scroll(page, rec, 0, look)
                    _scroll(page, rec, look, 0)
                else:
                    _scroll(page, rec, 0, want)
            elif total > 0:
                look = min(float(total), vp["height"] * (1.2 if nxt else 1.0))
                _scroll(page, rec, 0, look)

            if not nxt:
                rec.add(_snap(page), ms=1200)                           # last page: hold
                break

            if link:
                box = page.locator(NEXT_SELECTOR).first.bounding_box()
                sx = _snap(page).width / vp["width"]
                tx, ty = (box["x"] + box["width"] / 2) * sx, (box["y"] + box["height"] / 2) * sx
                base = _snap(page)
                sx0, sy0 = base.width * 0.78, base.height * 0.82        # the pointer enters from the lower right
                for s in range(1, 9):                                    # travel to the link
                    e = _ease(s / 8)
                    rec.add(_draw_pointer(base, sx0 + (tx - sx0) * e, sy0 + (ty - sy0) * e))
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.wait_for_timeout(120)
                hover = _snap(page)
                for s in range(1, 4):                                    # click ripple
                    rec.add(_draw_pointer(hover, tx, ty, ring=s / 3), ms=rec.frame_ms * 2)
                prev_view = _draw_pointer(hover, tx, ty, ring=1.0)
                try:
                    with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                        page.locator(NEXT_SELECTOR).first.click(timeout=5000)
                except Exception:
                    page.goto(nxt, wait_until="domcontentloaded", timeout=30000)
            else:
                prev_view = _snap(page)
                page.goto(nxt, wait_until="domcontentloaded", timeout=30000)
            _prepare(page, keep_floating)
    finally:
        ctx.close()
    return rec.frames, rec.durations


def record_flows(flows, dest_dir, a, quality="standard", watermark=True, progress=None):
    """Record every flow (lists of items whose `label` is the page URL) as a live GIF.

    a  the scan settings (width, height, mobile, storage_state, keep_floating)
    progress(n, total, breadcrumb) is called before each flow.
    """
    from playwright.sync_api import sync_playwright
    out_w, fps = QUALITY.get(quality, QUALITY["standard"])
    k = out_w / sg.W
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    made, last_error = [], None
    with sync_playwright() as pw:
        browser = launch_browser(pw)
        try:
            for n, flow in enumerate(flows, 1):
                if STOP.is_set():
                    break
                names = sg.crumbs(flow)
                if progress:
                    progress(n, len(flows), sg.SEP.join(names))
                t0 = time.time()
                try:
                    frames, durations = _record_flow(pw, browser, a, flow, names, k, fps, watermark)
                except Exception as e:           # one flow failing must not lose the others
                    print(f"  ! Could not record flow {n} ({sg.SEP.join(names)}): {e}")
                    last_error = e
                    continue
                durations[-1] = max(durations[-1], 1600)
                out = dest_dir / sg.flow_filename(n, names)
                sg.save_frames_gif(frames, durations, out)
                print(f"  live GIF {out.name}: {len(frames)} frames, {out.stat().st_size / 1e6:.1f} MB, "
                      f"{time.time() - t0:.0f}s")
                made.append(out)
        finally:
            browser.close()
    if not made and last_error is not None:
        raise last_error
    return made
