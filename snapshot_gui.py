#!/usr/bin/env python3
"""SnapshotAll - desktop GUI (website / APK screenshot tool)"""
import os
import sys

# Keep the Chromium browser inside the playwright package (needed for the frozen .exe)
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

import argparse
import queue
import subprocess
import threading
import traceback
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import snapshot_all as sa

APP_TITLE = "SnapshotAll - Website & App Screenshot Tool"


def add_edit_support(w):
    """Make Ctrl+C/V/X/A work with any keyboard layout, and add a right-click menu."""
    def select_all():
        if isinstance(w, tk.Text):
            w.tag_add("sel", "1.0", "end-1c")
        else:
            w.select_range(0, "end")
            w.icursor("end")

    def is_editable():
        return str(w.cget("state")) != "disabled"

    def on_key(e):
        if e.state & 0x4:  # Ctrl held
            k = e.keycode  # physical key code, independent of keyboard language
            if k == 86:
                if is_editable():
                    w.event_generate("<<Paste>>")
                return "break"
            if k == 67:
                w.event_generate("<<Copy>>")
                return "break"
            if k == 88:
                if is_editable():
                    w.event_generate("<<Cut>>")
                return "break"
            if k == 65:
                select_all()
                return "break"

    menu = tk.Menu(w, tearoff=0)
    menu.add_command(label="Paste", command=lambda: is_editable() and w.event_generate("<<Paste>>"))
    menu.add_command(label="Copy", command=lambda: w.event_generate("<<Copy>>"))
    menu.add_command(label="Cut", command=lambda: is_editable() and w.event_generate("<<Cut>>"))
    menu.add_command(label="Select all", command=select_all)
    w.bind("<Key>", on_key, add="+")
    w.bind("<Button-1>", lambda e: w.focus_set(), add="+")
    w.bind("<Button-3>", lambda e: (w.focus_set(), menu.tk_popup(e.x_root, e.y_root)))


class QWriter:
    def __init__(self, q, buf):
        self.q = q
        self.buf = buf

    def write(self, s):
        if s:
            self.buf.append(s)
            self.q.put(s)

    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("780x680")
        self.q = queue.Queue()
        self.thread = None
        self.last_out = None
        self.buf = []

        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(self)
        frm.pack(fill="x", **pad)
        frm.columnconfigure(1, weight=1)

        # target
        ttk.Label(frm, text="Website URL / folder / APK file:").grid(row=0, column=0, sticky="w")
        self.target = tk.StringVar()
        te = ttk.Entry(frm, textvariable=self.target)
        te.grid(row=0, column=1, sticky="ew", **pad)
        add_edit_support(te)
        bf = ttk.Frame(frm)
        bf.grid(row=0, column=2)
        ttk.Button(bf, text="Paste", width=7, command=self.paste_target).pack(side="left", padx=(0, 6))
        ttk.Button(bf, text="APK…", width=6, command=self.pick_apk).pack(side="left")
        ttk.Button(bf, text="Folder…", width=7, command=self.pick_dir).pack(side="left", padx=2)
        ttk.Button(bf, text="HTML…", width=6, command=self.pick_html).pack(side="left")

        # output
        ttk.Label(frm, text="Output folder:").grid(row=1, column=0, sticky="w")
        self.out = tk.StringVar(value=str(Path.home() / "SnapshotAll_Output"))
        oe = ttk.Entry(frm, textvariable=self.out)
        oe.grid(row=1, column=1, sticky="ew", **pad)
        add_edit_support(oe)
        ttk.Button(frm, text="Browse…", command=self.pick_out).grid(row=1, column=2)

        # settings
        nb = ttk.Notebook(self)
        nb.pack(fill="x", **pad)

        web = ttk.Frame(nb)
        nb.add(web, text="Website settings")
        self.max_pages = tk.IntVar(value=50)
        self.depth_web = tk.IntVar(value=5)
        self.width = tk.IntVar(value=1440)
        self.height = tk.IntVar(value=900)
        self.delay_web = tk.DoubleVar(value=1.0)
        self.mobile = tk.BooleanVar(value=False)
        self.state_file = tk.StringVar()
        self._row(web, 0, "Max pages", self.max_pages)
        self._row(web, 1, "Crawl depth", self.depth_web)
        self._row(web, 2, "Window width", self.width)
        self._row(web, 3, "Window height", self.height)
        self._row(web, 4, "Delay per page (seconds)", self.delay_web)
        ttk.Checkbutton(web, text="Mobile mode (iPhone 13)", variable=self.mobile).grid(
            row=5, column=0, columnspan=2, sticky="w", **pad)
        ttk.Label(web, text="Session file (pages behind login):").grid(row=6, column=0, sticky="w", **pad)
        se = ttk.Entry(web, textvariable=self.state_file, width=30)
        se.grid(row=6, column=1, **pad)
        add_edit_support(se)

        apk = ttk.Frame(nb)
        nb.add(apk, text="APK settings")
        self.max_screens = tk.IntVar(value=40)
        self.depth_apk = tk.IntVar(value=3)
        self.max_clicks = tk.IntVar(value=25)
        self.scroll = tk.IntVar(value=3)
        self.delay_apk = tk.DoubleVar(value=1.0)
        self.serial = tk.StringVar()
        self.package = tk.StringVar()
        self.avoid = tk.StringVar(value=sa.DEFAULT_AVOID)
        self._row(apk, 0, "Max screens", self.max_screens)
        self._row(apk, 1, "Crawl depth", self.depth_apk)
        self._row(apk, 2, "Max taps per screen", self.max_clicks)
        self._row(apk, 3, "Scroll steps (0 = off)", self.scroll)
        self._row(apk, 4, "Delay per tap (seconds)", self.delay_apk)
        self._row(apk, 5, "Device serial (optional)", self.serial, 22)
        self._row(apk, 6, "Package name (optional)", self.package, 22)
        self._row(apk, 7, "Never tap (regex)", self.avoid, 46)

        # buttons
        bar = ttk.Frame(self)
        bar.pack(fill="x", **pad)
        self.start_btn = ttk.Button(bar, text="▶ Start", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar, text="■ Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=6)
        self.open_btn = ttk.Button(bar, text="Open output folder", command=self.open_out, state="disabled")
        self.open_btn.pack(side="right")
        ttk.Button(bar, text="Copy log", command=self.copy_log).pack(side="right", padx=6)

        self.log = scrolledtext.ScrolledText(self, height=14, state="disabled")
        self.log.pack(fill="both", expand=True, **pad)
        add_edit_support(self.log)
        self.after(100, self.poll)

    def _row(self, parent, r, label, var, width=10):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=8, pady=3)
        e = ttk.Entry(parent, textvariable=var, width=width)
        e.grid(row=r, column=1, sticky="w", padx=8, pady=3)
        add_edit_support(e)

    def paste_target(self):
        try:
            self.target.set(self.clipboard_get().strip().strip('"'))
        except tk.TclError:
            messagebox.showinfo("Clipboard", "The clipboard is empty.")

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append("".join(self.buf))
        self.append("\n(Log copied to clipboard)\n")

    def pick_apk(self):
        f = filedialog.askopenfilename(filetypes=[("Android APK", "*.apk")])
        if f:
            self.target.set(f)

    def pick_dir(self):
        f = filedialog.askdirectory()
        if f:
            self.target.set(f)

    def pick_html(self):
        f = filedialog.askopenfilename(filetypes=[("HTML", "*.html *.htm")])
        if f:
            self.target.set(f)

    def pick_out(self):
        f = filedialog.askdirectory()
        if f:
            self.out.set(f)

    def start(self):
        target = self.target.get().strip().strip('"')
        if not target:
            messagebox.showwarning("Missing input", "Enter a website URL, or choose a folder / HTML / APK file.")
            return
        is_apk = target.lower().endswith(".apk")
        base = Path(self.out.get())
        name = sa.slugify(Path(target).stem if is_apk else target, 30)
        out = base / f"{name}_{datetime.now():%Y%m%d_%H%M%S}"
        out.mkdir(parents=True, exist_ok=True)
        self.last_out = out

        ns = argparse.Namespace(
            max_depth=self.depth_apk.get() if is_apk else self.depth_web.get(),
            delay=self.delay_apk.get() if is_apk else self.delay_web.get(),
            max_pages=self.max_pages.get(), width=self.width.get(), height=self.height.get(),
            mobile=self.mobile.get(), storage_state=self.state_file.get().strip() or None,
            max_screens=self.max_screens.get(), max_clicks=self.max_clicks.get(),
            scroll=self.scroll.get(), serial=self.serial.get().strip() or None,
            package=self.package.get().strip() or None, avoid=self.avoid.get().strip(),
        )

        self.clear_log()
        self.buf.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.open_btn.config(state="disabled")
        sa.STOP.clear()

        def worker():
            sys.stdout = sys.stderr = QWriter(self.q, self.buf)
            runner = sa.run_apk if is_apk else sa.run_web
            try:
                try:
                    runner(target, out, ns)
                except Exception as e:
                    if "Executable doesn't exist" in str(e) and not getattr(sys, "frozen", False):
                        print("Chromium is not installed. Installing it now (this can take a few minutes)…")
                        r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                                           capture_output=True, text=True)
                        print(r.stdout, r.stderr)
                        runner(target, out, ns)
                    else:
                        raise
            except SystemExit as e:
                print(e.code if e.code else "")
            except Exception:
                print("\n===== ERROR =====")
                print(traceback.format_exc())
            finally:
                try:
                    (out / "log.txt").write_text("".join(self.buf), encoding="utf-8")
                except Exception:
                    pass
                self.q.put(None)

        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def stop(self):
        sa.STOP.set()
        self.append("\nStopping… (after the current page finishes)\n")

    def open_out(self):
        if self.last_out and self.last_out.exists():
            if sys.platform == "win32":
                os.startfile(self.last_out)
            else:
                subprocess.Popen(["xdg-open", str(self.last_out)])

    def append(self, s):
        self.log.config(state="normal")
        self.log.insert("end", s)
        self.log.see("end")
        self.log.config(state="disabled")

    def clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item is None:
                    self.start_btn.config(state="normal")
                    self.stop_btn.config(state="disabled")
                    self.open_btn.config(state="normal")
                else:
                    self.append(item)
        except queue.Empty:
            pass
        self.after(100, self.poll)


if __name__ == "__main__":
    App().mainloop()
