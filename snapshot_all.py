#!/usr/bin/env python3
"""
SnapshotAll engine - take screenshots of every page of a website (online/local)
or every screen of an Android app (APK).

Requirements:
  Web:  pip install playwright && playwright install chromium
  APK:  pip install uiautomator2  (+ adb and an emulator/phone with USB debugging)

Examples:
  python snapshot_all.py https://example.com
  python snapshot_all.py http://localhost:3000 --max-pages 100
  python snapshot_all.py ./my-site-folder
  python snapshot_all.py ./index.html --mobile
  python snapshot_all.py app.apk --max-screens 60 --max-depth 4
"""
import argparse
import functools
import hashlib
import http.server
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urldefrag, urlparse

SKIP_EXT = re.compile(
    r"\.(pdf|zip|rar|7z|gz|tar|png|jpe?g|gif|svg|webp|ico|mp3|mp4|avi|mov|webm|"
    r"css|js|json|xml|woff2?|ttf|eot|apk|exe|dmg|docx?|xlsx?|pptx?)$", re.I)

STOP = threading.Event()  # set by the GUI to stop a running job
DEFAULT_AVOID = r"delete|remove|log ?out|sign ?out|uninstall|pay|buy|purchase|checkout|reset"


class BrowserUnavailable(Exception):
    """No usable Chromium/Edge/Chrome could be launched."""


def launch_browser(pw):
    """Try the Playwright Chromium first, then Microsoft Edge, then Google Chrome."""
    last = None
    for kw in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
        try:
            return pw.chromium.launch(**kw)
        except Exception as e:  # missing executable, etc.
            last = e
    msg = (str(last).strip().splitlines() or ["browser launch failed"])[0]
    raise BrowserUnavailable(msg)


def install_chromium():
    """Download Playwright's Chromium using the driver bundled with the playwright package."""
    from playwright._impl._driver import compute_driver_executable, get_driver_env
    drv = compute_driver_executable()
    cmd = [str(x) for x in drv] if isinstance(drv, (tuple, list)) else [str(drv)]
    try:
        env = get_driver_env()
    except Exception:
        env = None
    flags = 0x08000000 if sys.platform == "win32" else 0  # no console window flash
    p = subprocess.Popen(cmd + ["install", "chromium"], env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, creationflags=flags)
    for line in p.stdout:
        print(line.rstrip())
    p.wait()
    if p.returncode != 0:
        raise RuntimeError("Chromium download failed. Check your internet connection and try again.")


def slugify(text, limit=60):
    s = re.sub(r"[^\w\u0600-\u06FF]+", "_", text).strip("_")
    return (s or "home")[:limit]


# ───────────────────────────── WEB ─────────────────────────────

def serve_dir(root: Path):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}/", srv


def normalize(url):
    base, frag = urldefrag(url)
    # keep SPA hash routes such as #/about or #!/about
    if frag.startswith("/") or frag.startswith("!"):
        return f"{base}#{frag}"
    return base


def run_web(target, out: Path, a):
    from playwright.sync_api import sync_playwright

    server = None
    p = Path(target)
    if p.exists():
        root = p if p.is_dir() else p.parent
        start_url, server = serve_dir(root.resolve())
        if p.is_file():
            start_url += p.name
    elif re.match(r"^https?://", target):
        start_url = target
    else:
        start_url = "http://" + target

    origin = urlparse(start_url).netloc
    lines = []

    with sync_playwright() as pw:
        browser = launch_browser(pw)
        kw = {}
        if a.mobile:
            kw.update(pw.devices["iPhone 13"])
        else:
            kw["viewport"] = {"width": a.width, "height": a.height}
        if a.storage_state:  # for pages behind a login
            kw["storage_state"] = a.storage_state
        ctx = browser.new_context(ignore_https_errors=True, **kw)
        page = ctx.new_page()

        queue = deque([(normalize(start_url), 0)])
        seen = {normalize(start_url)}

        # sitemap.xml (if present)
        try:
            r = ctx.request.get(f"{urlparse(start_url).scheme}://{origin}/sitemap.xml", timeout=8000)
            if r.ok:
                for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text()):
                    n = normalize(loc)
                    if urlparse(n).netloc == origin and n not in seen and not SKIP_EXT.search(urlparse(n).path):
                        seen.add(n)
                        queue.append((n, 1))
        except Exception:
            pass

        count = 0
        while queue and count < a.max_pages and not STOP.is_set():
            url, depth = queue.popleft()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                page.wait_for_timeout(int(a.delay * 1000))
                # scroll down to trigger lazy-loaded content
                page.evaluate("""async () => {
                    await new Promise(r => { let i=0;
                      const t=setInterval(()=>{ window.scrollBy(0,600);
                        if(++i>60 || window.scrollY+innerHeight>=document.body.scrollHeight){clearInterval(t);r();}
                      },120); });
                    window.scrollTo(0,0);
                }""")
                count += 1
                path = urlparse(url)
                name = f"{count:03d}_{slugify((path.path or '/') + ('?' + path.query if path.query else '') + ('#' + path.fragment if path.fragment else ''))}.png"
                page.screenshot(path=str(out / name), full_page=True)
                lines.append(f"{name}\t{url}")
                print(f"[{count}] {url}")

                if depth < a.max_depth:
                    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                    for h in hrefs:
                        if not h.startswith(("http://", "https://")):
                            continue
                        n = normalize(h)
                        if (urlparse(n).netloc == origin and n not in seen
                                and not SKIP_EXT.search(urlparse(n).path)):
                            seen.add(n)
                            queue.append((n, depth + 1))
            except Exception as e:
                print(f"  ! Error on {url}: {e}")

        browser.close()
    if server:
        server.shutdown()
    (out / "index.tsv").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDone: {count} page(s) saved to {out}")


# ───────────────────────────── APK ─────────────────────────────

def run_apk(apk, out: Path, a):
    try:
        import uiautomator2 as u2
    except ImportError:
        sys.exit("Missing dependency. Install it with: pip install uiautomator2")

    adb_bin = shutil.which("adb")
    if not adb_bin:
        try:
            import adbutils  # installed together with uiautomator2, ships an adb binary
            adb_bin = adbutils.adb_path()
        except Exception:
            sys.exit("adb not found. Install Android Platform-Tools and add it to PATH.")

    def adb(*args):
        cmd = [adb_bin] + (["-s", a.serial] if a.serial else []) + list(args)
        return subprocess.run(cmd, capture_output=True, text=True)

    if adb("get-state").stdout.strip() != "device":
        sys.exit("No device/emulator connected (check 'adb devices').")

    before = set(adb("shell", "pm", "list", "packages", "-3").stdout.split())
    r = adb("install", "-r", "-g", apk)
    if "Success" not in r.stdout:
        sys.exit(f"APK installation failed:\n{r.stdout}{r.stderr}")
    after = set(adb("shell", "pm", "list", "packages", "-3").stdout.split())

    pkg = a.package
    if not pkg:
        new = after - before
        if new:
            pkg = new.pop().replace("package:", "")
        else:  # reinstall of an existing app; try aapt
            try:
                o = subprocess.run(["aapt", "dump", "badging", apk], capture_output=True, text=True).stdout
                pkg = re.search(r"package: name='([^']+)'", o).group(1)
            except Exception:
                sys.exit("Could not detect the package name. Set it manually (Package field / --package).")
    print(f"Package: {pkg}")

    d = u2.connect(a.serial) if a.serial else u2.connect()
    W, H = d.window_size()
    avoid = re.compile(a.avoid, re.I) if a.avoid else None

    def parse():
        root = ET.fromstring(d.dump_hierarchy())
        sig, clicks, seen_b = set(), [], set()
        for n in root.iter("node"):
            at = n.attrib
            if at.get("package") != pkg:
                continue
            txt = re.sub(r"\d+", "#", at.get("text", ""))[:30]
            sig.add(f'{at.get("class")}|{at.get("resource-id")}|{txt}')
            if at.get("clickable") == "true" and at.get("enabled") == "true":
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", at.get("bounds", ""))
                if not m:
                    continue
                x1, y1, x2, y2 = map(int, m.groups())
                if (x2 - x1) * (y2 - y1) <= 0 or (x1, y1, x2, y2) in seen_b:
                    continue
                seen_b.add((x1, y1, x2, y2))
                label = at.get("text") or at.get("content-desc") or at.get("resource-id", "").split("/")[-1] or "item"
                if avoid and avoid.search(label):
                    continue
                clicks.append(((x1 + x2) // 2, (y1 + y2) // 2, label))
        digest = hashlib.md5("\n".join(sorted(sig)).encode()).hexdigest() if sig else ""
        return digest, clicks

    queue = deque([[]])  # each path = list of taps from the app's home screen
    seen, shots, lines = set(), 0, []
    while queue and shots < a.max_screens and not STOP.is_set():
        path = queue.popleft()
        d.app_start(pkg, stop=True)
        time.sleep(a.delay + 1.5)
        for x, y, _ in path:
            d.click(x, y)
            time.sleep(a.delay)
        sig, clicks = parse()
        if not sig or sig in seen:
            continue
        seen.add(sig)
        shots += 1
        label = path[-1][2] if path else "home"
        name = f"{shots:03d}_{slugify(label, 30)}.png"
        d.screenshot(str(out / name))
        lines.append(f"{name}\t{' > '.join(p[2] for p in path) or 'home'}")
        print(f"[{shots}] {lines[-1].split(chr(9))[1]}")

        if a.scroll and d(scrollable=True).exists:
            prev = sig
            for i in range(a.scroll):
                d.swipe(W // 2, int(H * 0.75), W // 2, int(H * 0.25), 0.3)
                time.sleep(0.7)
                cur, _ = parse()
                if cur == prev or not cur:
                    break
                d.screenshot(str(out / f"{shots:03d}_{slugify(label, 30)}_scroll{i + 1}.png"))
                prev = cur

        if len(path) < a.max_depth:
            for x, y, lb in clicks[: a.max_clicks]:
                queue.append(path + [(x, y, lb)])

    (out / "index.tsv").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDone: {shots} screen(s) saved to {out}")


# ───────────────────────────── CLI ─────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Screenshot every page of a website or Android app (APK)")
    ap.add_argument("target", help="URL, local folder/HTML file, or .apk file")
    ap.add_argument("-o", "--out", help="output folder")
    ap.add_argument("--max-depth", type=int, default=None, help="crawl depth (web: 5, app: 3)")
    ap.add_argument("--delay", type=float, default=1.0, help="wait after each load/tap (seconds)")
    # web
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--mobile", action="store_true", help="emulate a phone (iPhone 13)")
    ap.add_argument("--storage-state", help="Playwright session file for pages behind login")
    # app
    ap.add_argument("--max-screens", type=int, default=40)
    ap.add_argument("--max-clicks", type=int, default=25, help="max tappable elements tried per screen")
    ap.add_argument("--scroll", type=int, default=3, help="scroll steps captured per app screen (0 = off)")
    ap.add_argument("--serial", help="adb device serial")
    ap.add_argument("--package", help="app package name (optional)")
    ap.add_argument("--avoid", default=DEFAULT_AVOID,
                    help="regex of button labels that must never be tapped")
    a = ap.parse_args()

    is_apk = a.target.lower().endswith(".apk")
    if a.max_depth is None:
        a.max_depth = 3 if is_apk else 5
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(a.out or f"screenshots_{slugify(Path(a.target).stem if is_apk else a.target, 30)}_{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    (run_apk if is_apk else run_web)(a.target, out, a)


if __name__ == "__main__":
    main()
