"""
Windows desktop apps (.exe / .jar / attach to a running window).

Uses Microsoft UI Automation (via pywinauto) to find buttons, tabs, menu items and links,
clicks them breadth-first and captures every window state it has not seen before.
For launched apps each branch restarts the app and replays the click path, like the APK explorer.
"""
import hashlib
import re
import sys
import time
from collections import deque
from pathlib import Path

from snapshot_common import STOP, slugify

# Always avoided for desktop apps (on top of the user's --avoid list)
DESKTOP_EXTRA = r"exit|quit|close|minimi[sz]e|maximi[sz]e|restore|shut ?down|save|overwrite|send|submit"
CLICK_TYPES = {"Button", "TabItem", "MenuItem", "Hyperlink", "SplitButton"}
TITLEBAR_IDS = {"Close", "Minimize", "Maximize", "Restore", "SystemMenuBar", "TitleBar"}


def run_desktop(target, out: Path, a):
    if sys.platform != "win32":
        sys.exit("Windows app capture is only supported on Windows.")
    try:
        from pywinauto import Application
        from pywinauto.keyboard import send_keys
    except ImportError:
        sys.exit("Missing dependency. Install it with: pip install pywinauto")

    avoid = re.compile("|".join(x for x in (a.avoid, DESKTOP_EXTRA) if x), re.I)
    state = {"app": None, "launched": False}

    def start():
        if a.attach:
            state["app"] = Application(backend="uia").connect(title_re=a.attach, timeout=15)
        else:
            cmd = f'java -jar "{target}"' if str(target).lower().endswith(".jar") else f'"{target}"'
            state["app"] = Application(backend="uia").start(
                cmd, timeout=20, wait_for_idle=False, work_dir=str(Path(target).parent))
            state["launched"] = True
        time.sleep(a.delay + 3)

    def stop_app():
        if state["launched"] and state["app"] is not None:
            try:
                state["app"].kill()
            except Exception:
                pass

    def windows():
        """Visible top-level windows of the app, largest first."""
        try:
            wins = [w for w in state["app"].windows() if w.is_visible()]
        except Exception:
            return []
        def area(w):
            try:
                r = w.rectangle()
                return r.width() * r.height()
            except Exception:
                return 0
        wins = [w for w in wins if area(w) > 0]
        wins.sort(key=area, reverse=True)
        return wins

    def scan(win):
        """Return (signature, candidates) where candidates = [(key, idx, label, wrapper)]."""
        title = ""
        try:
            title = win.window_text() or ""
        except Exception:
            pass
        items, cands, counts = [], [], {}
        try:
            descs = win.descendants()
        except Exception:
            descs = []
        for c in descs[:1500]:
            try:
                ei = c.element_info
                if not ei.visible:
                    continue
                ctype = ei.control_type
                name = (ei.name or "").strip()
                aid = ei.automation_id or ""
                items.append(re.sub(r"\d+", "#", f"{ctype}|{name[:30]}|{aid}"))
                if ctype not in CLICK_TYPES or not ei.enabled or aid in TITLEBAR_IDS:
                    continue
                if avoid.search(f"{name} {aid}"):
                    continue
                r = ei.rectangle
                if r.width() <= 0 or r.height() <= 0:
                    continue
                key = (title, ctype, name, aid)
                idx = counts.get(key, 0)
                counts[key] = idx + 1
                cands.append((key, idx, name or aid or ctype, c))
            except Exception:
                continue
        sig = hashlib.md5((title + "\n" + "\n".join(sorted(set(items)))).encode("utf-8", "ignore")).hexdigest()
        return sig, cands

    def find(key, idx):
        for w in windows():
            _, cands = scan(w)
            matches = [c for k, _, _, c in cands if k == key]
            if idx < len(matches):
                return matches[idx]
        return None

    def shoot(win, name):
        try:
            win.set_focus()
        except Exception:
            pass
        time.sleep(0.3)
        win.capture_as_image().save(str(out / name))

    start()
    queue = deque([[]])
    seen, shots, lines = set(), 0, []
    first = True
    while queue and shots < a.max_screens and not STOP.is_set():
        path = queue.popleft()
        try:
            if not first and path:
                if state["launched"]:
                    stop_app()
                    start()
                # attached apps can't be restarted: only single-click paths are tried, in place
                elif len(path) > 1:
                    continue
            first = False

            ok = True
            for key, idx, _label in path:
                ctrl = find(key, idx)
                if ctrl is None:
                    ok = False
                    break
                ctrl.click_input()
                time.sleep(a.delay)
            if not ok:
                continue

            label = path[-1][2] if path else "home"
            for win in windows():
                sig, cands = scan(win)
                if sig in seen:
                    continue
                seen.add(sig)
                shots += 1
                name = f"{shots:03d}_{slugify(label, 30)}.png"
                shoot(win, name)
                lines.append(f"{name}\t{' > '.join(p[2] for p in path) or 'home'}")
                print(f"[{shots}] {lines[-1].split(chr(9))[1]}")
                if len(path) < a.max_depth and (state["launched"] or not path):
                    for key, idx, lb, _c in cands[: a.max_clicks]:
                        queue.append(path + [(key, idx, lb)])
                if shots >= a.max_screens:
                    break
            if not state["launched"]:
                send_keys("{ESC}")  # dismiss menus/dialogs opened while attached
        except Exception as e:
            print(f"  ! Error while exploring: {e}")

    stop_app()
    (out / "index.tsv").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDone: {shots} window state(s) saved to {out}")
