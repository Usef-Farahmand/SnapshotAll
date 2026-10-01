#!/usr/bin/env python3
"""
SnapshotAll engine + command-line interface.

Modes (auto-detected from the target):
  web      website URL (online or localhost)
  apk      Android app (.apk)                      -> needs adb + emulator/phone
  desktop  Windows app (.exe / .jar / --attach)    -> Windows only

The desktop app (snapshot_gui.py) uses the same engines with a live preview.

Examples:
  python snapshot_all.py https://example.com
  python snapshot_all.py http://localhost:3000 --max-pages 100
  python snapshot_all.py app.apk --max-screens 60 --max-depth 4
  python snapshot_all.py "C:/Program Files/MyApp/MyApp.exe"
  python snapshot_all.py --attach "Notepad"
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

from snapshot_common import DEFAULT_AVOID, STOP, emit, slugify  # noqa: F401  (re-exported for the GUI)

SKIP_EXT = re.compile(
    r"\.(pdf|zip|rar|7z|gz|tar|png|jpe?g|gif|svg|webp|ico|mp3|mp4|avi|mov|webm|"
    r"css|js|json|xml|woff2?|ttf|eot|apk|exe|dmg|docx?|xlsx?|pptx?)$", re.I)

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


def normalize_target(target):
    """Turn what a person types ('example.com', 'www.example.com', 'localhost:3000') into a full URL."""
    t = target.strip().strip('"')
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", t):
        return t
    host = t.split("/", 1)[0].rsplit("@", 1)[-1]
    hostname = host.split(":")[0].lower()
    local = (hostname == "localhost" or hostname.endswith(".local") or ":" in host
             or re.match(r"^(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)", hostname))
    return ("http://" if local else "https://") + t


def site_key(netloc):
    """Identity of a site for 'same site?' checks: lower-case, without www. or default ports."""
    host = netloc.lower().rsplit("@", 1)[-1]
    for default_port in (":80", ":443"):
        if host.endswith(default_port):
            host = host[: -len(default_port)]
    return host[4:] if host.startswith("www.") else host


def page_key(url):
    """Identity of a page for de-duplication: ignores scheme, www., trailing slash and plain #fragments."""
    u = urlparse(normalize(url))
    return (site_key(u.netloc) + (u.path.rstrip("/") or "/")
            + (f"?{u.query}" if u.query else "") + (f"#{u.fragment}" if u.fragment else ""))


def run_web(target, out: Path, a):
    from playwright.sync_api import sync_playwright

    server = None
    p = Path(target)
    if p.exists():
        root = p if p.is_dir() else p.parent
        start_url, server = serve_dir(root.resolve())
        if p.is_file():
            start_url += p.name
    else:
        start_url = normalize_target(target)
    # No scheme typed (e.g. "example.com")? We start with https and fall back to http if it can't connect.
    auto_scheme = not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target.strip()) and start_url.startswith("https://")

    origin_key = site_key(urlparse(start_url).netloc)

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
        seen = {page_key(start_url)}

        def goto_page(url, first):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                if first and auto_scheme and url.startswith("https://"):
                    print("  https failed - trying http…")
                    page.goto("http://" + url[len("https://"):], wait_until="domcontentloaded", timeout=30000)
                else:
                    raise

        # sitemap.xml (if present)
        try:
            r = ctx.request.get(f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}/sitemap.xml",
                                timeout=8000)
            if r.ok:
                for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text()):
                    n = normalize(loc)
                    if (site_key(urlparse(n).netloc) == origin_key and page_key(n) not in seen
                            and not SKIP_EXT.search(urlparse(n).path)):
                        seen.add(page_key(n))
                        queue.append((n, 1))
        except Exception:
            pass

        count = 0
        while queue and count < a.max_pages and not STOP.is_set():
            url, depth = queue.popleft()
            try:
                goto_page(url, count == 0)
                if count == 0 and page.url.startswith(("http://", "https://")):
                    # The site may have redirected us (http -> https, example.com -> www.example.com, ...):
                    # from now on "same site" means the host we actually landed on.
                    origin_key = site_key(urlparse(page.url).netloc)
                    seen.add(page_key(page.url))
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
                emit(a, out / name, url)
                print(f"[{count}] {url}")

                if depth < a.max_depth:
                    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                    for h in hrefs:
                        if not h.startswith(("http://", "https://")):
                            continue
                        n = normalize(h)
                        if (site_key(urlparse(n).netloc) == origin_key and page_key(n) not in seen
                                and not SKIP_EXT.search(urlparse(n).path)):
                            seen.add(page_key(n))
                            queue.append((n, depth + 1))
            except Exception as e:
                print(f"  ! Error on {url}: {e}")

        browser.close()
    if server:
        server.shutdown()
    print(f"\nDone: {count} page(s) captured")


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
    seen, shots = set(), 0
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
        trail = " > ".join(p[2] for p in path) or "home"
        emit(a, out / name, trail)
        print(f"[{shots}] {trail}")

        if a.scroll and d(scrollable=True).exists:
            prev = sig
            for i in range(a.scroll):
                d.swipe(W // 2, int(H * 0.75), W // 2, int(H * 0.25), 0.3)
                time.sleep(0.7)
                cur, _ = parse()
                if cur == prev or not cur:
                    break
                sname = f"{shots:03d}_{slugify(label, 30)}_scroll{i + 1}.png"
                d.screenshot(str(out / sname))
                emit(a, out / sname, f"{trail} (scroll {i + 1})")
                prev = cur

        if len(path) < a.max_depth:
            for x, y, lb in clicks[: a.max_clicks]:
                queue.append(path + [(x, y, lb)])

    print(f"\nDone: {shots} screen(s) captured")


# ───────────────────────────── CLI ─────────────────────────────

def detect_mode(target):
    t = (target or "").lower()
    if t.endswith(".apk"):
        return "apk"
    if t.endswith((".exe", ".jar")):
        return "desktop"
    p = Path(target)
    if p.exists() and not (p.is_file() and t.endswith((".html", ".htm"))):
        return "unsupported"
    return "web"


def main():
    ap = argparse.ArgumentParser(
        description="Screenshot every page of a website or every screen of an app")
    ap.add_argument("target", nargs="?", default="",
                    help="website URL, or an .apk / .exe / .jar file")
    ap.add_argument("--mode", choices=["auto", "web", "apk", "desktop"], default="auto")
    ap.add_argument("-o", "--out", help="output folder")
    ap.add_argument("--max-depth", type=int, default=None, help="crawl depth (web 5, apk 3, desktop 2)")
    ap.add_argument("--delay", type=float, default=1.0, help="wait after each load/tap (seconds)")
    # web
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--mobile", action="store_true", help="emulate a phone (iPhone 13)")
    ap.add_argument("--storage-state", help="Playwright session file for pages behind login")
    # apps (apk + desktop)
    ap.add_argument("--max-screens", type=int, default=40)
    ap.add_argument("--max-clicks", type=int, default=25, help="max tappable elements tried per screen")
    ap.add_argument("--avoid", default=DEFAULT_AVOID, help="regex of button labels that must never be tapped")
    ap.add_argument("--scroll", type=int, default=3, help="[apk] scroll steps captured per screen (0 = off)")
    ap.add_argument("--serial", help="[apk] adb device serial")
    ap.add_argument("--package", help="[apk] app package name (optional)")
    ap.add_argument("--attach", help="[desktop] attach to a running window whose title matches this regex")
    a = ap.parse_args()

    mode = a.mode if a.mode != "auto" else ("desktop" if (a.attach and not a.target) else detect_mode(a.target))
    if mode == "unsupported":
        ap.error("unsupported target: give a website URL, or an .apk / .exe / .jar file")
    if not a.target and not (mode == "desktop" and a.attach):
        ap.error("a target is required")
    if a.max_depth is None:
        a.max_depth = {"web": 5, "apk": 3, "desktop": 2}[mode]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = a.attach if (mode == "desktop" and a.attach and not a.target) else a.target
    stem = Path(label).stem if mode in ("apk", "desktop") and not a.attach else label
    out = Path(a.out or f"screenshots_{slugify(stem, 30)}_{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    if mode == "web":
        run_web(a.target, out, a)
    elif mode == "apk":
        run_apk(a.target, out, a)
    else:
        from snapshot_desktop import run_desktop
        run_desktop(a.target, out, a)
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
