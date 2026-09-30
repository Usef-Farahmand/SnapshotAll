#!/usr/bin/env python3
"""SnapshotAll - desktop GUI: screenshots of websites, apps (APK / EXE) and folders."""
import os
import sys
from pathlib import Path

# Where a downloaded Chromium (fallback only) is stored.
# The app first tries Microsoft Edge / Google Chrome, which need no download.
if getattr(sys, "frozen", False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "SnapshotAll" / "browsers")
else:
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

import argparse
import queue
import subprocess
import threading
import traceback
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import snapshot_all as sa
import snapshot_desktop as sd
import snapshot_folder as sf

APP_NAME = "SnapshotAll"
APP_TITLE = "SnapshotAll - Screenshot Every Page, Screen & File"

# ── Dark + orange theme ─────────────────────────────────────────────
BG = "#14100D"
PANEL = "#1C1612"
FIELD = "#261E18"
FIELD_H = "#33281F"
BORDER = "#3B2F25"
FG = "#F4EDE6"
MUTED = "#A99B8E"
ORANGE = "#F97316"
ORANGE_H = "#FB923C"
ON_ORANGE = "#1A0E05"
LOG_BG = "#0F0C0A"
LOG_FG = "#EADFD3"


def asset(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / name


def apply_theme(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    root.configure(bg=BG)
    s.configure(".", background=BG, foreground=FG, fieldbackground=FIELD, bordercolor=BORDER,
                lightcolor=BORDER, darkcolor=BORDER, troughcolor=PANEL, focuscolor=ORANGE,
                font=("Segoe UI", 10))
    for suffix, bg in (("", BG), ("Panel.", PANEL)):
        s.configure(f"{suffix}TFrame", background=bg)
        s.configure(f"{suffix}TLabel", background=bg, foreground=FG)
        s.configure(f"{suffix}Muted.TLabel", background=bg, foreground=MUTED, font=("Segoe UI", 9))
        s.configure(f"{suffix}Section.TLabel", background=bg, foreground=ORANGE, font=("Segoe UI", 10, "bold"))
        s.configure(f"{suffix}TCheckbutton", background=bg, foreground=FG, indicatorbackground=FIELD,
                    indicatorforeground=ORANGE)
        s.map(f"{suffix}TCheckbutton", background=[("active", bg)],
              indicatorbackground=[("selected", ORANGE), ("!selected", FIELD)],
              indicatorforeground=[("selected", ON_ORANGE)])
    s.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground=ORANGE)
    s.configure("Sub.TLabel", foreground=MUTED, font=("Segoe UI", 10))

    s.configure("TEntry", fieldbackground=FIELD, foreground=FG, insertcolor=FG, bordercolor=BORDER, padding=6)
    s.map("TEntry", bordercolor=[("focus", ORANGE)], lightcolor=[("focus", ORANGE)],
          darkcolor=[("focus", ORANGE)])

    s.configure("TButton", background=FIELD, foreground=FG, bordercolor=BORDER, padding=(12, 6), relief="flat")
    s.map("TButton", background=[("active", FIELD_H), ("disabled", PANEL)],
          foreground=[("disabled", "#6E6259")], bordercolor=[("active", ORANGE)])
    s.configure("Accent.TButton", background=ORANGE, foreground=ON_ORANGE, bordercolor=ORANGE,
                font=("Segoe UI", 10, "bold"), padding=(20, 7))
    s.map("Accent.TButton", background=[("active", ORANGE_H), ("disabled", "#5A3A1E")],
          foreground=[("disabled", "#2A1A0C")], bordercolor=[("active", ORANGE_H)])

    s.configure("TNotebook", background=BG, borderwidth=0, bordercolor=BORDER, lightcolor=BG, darkcolor=BG,
                tabmargins=(0, 0, 0, 0))
    s.configure("TNotebook.Tab", background=BG, foreground=MUTED, padding=(22, 9), borderwidth=0,
                bordercolor=BG, lightcolor=BG, darkcolor=BG, font=("Segoe UI", 10, "bold"))
    s.map("TNotebook.Tab", background=[("selected", PANEL), ("active", FIELD)],
          foreground=[("selected", ORANGE), ("active", FG)],
          bordercolor=[("selected", PANEL)], lightcolor=[("selected", PANEL)], darkcolor=[("selected", PANEL)])

    s.configure("Orange.Horizontal.TProgressbar", troughcolor=PANEL, background=ORANGE, bordercolor=PANEL,
                lightcolor=ORANGE, darkcolor=ORANGE, thickness=6)
    s.configure("Vertical.TScrollbar", background=FIELD, troughcolor=LOG_BG, bordercolor=LOG_BG,
                arrowcolor=MUTED, lightcolor=FIELD, darkcolor=FIELD)
    s.map("Vertical.TScrollbar", background=[("active", ORANGE)])


def dark_titlebar(win):
    """Ask Windows 10/11 for a dark title bar (ignored elsewhere)."""
    try:
        import ctypes
        win.update()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new / old id)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ctypes.c_int(1)), 4)
    except Exception:
        pass


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

    menu = tk.Menu(w, tearoff=0, bg=FIELD, fg=FG, activebackground=ORANGE, activeforeground=ON_ORANGE,
                   bd=0, relief="flat")
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
        self.geometry("920x900")
        self.minsize(820, 720)
        apply_theme(self)
        self._set_icon()

        self.q = queue.Queue()
        self.thread = None
        self.last_out = None
        self.buf = []

        self._build_header()
        self._build_tabs()
        self._build_run_area()
        dark_titlebar(self)
        self.after(100, self.poll)

    # ───────────── UI construction ─────────────
    def _set_icon(self):
        try:
            self.icon_img = tk.PhotoImage(file=str(asset("logo_64.png")))
            self.iconphoto(True, self.icon_img)
            if sys.platform == "win32":
                self.iconbitmap(default=str(asset("icon.ico")))
        except Exception:
            self.icon_img = None

    def _build_header(self):
        head = ttk.Frame(self)
        head.pack(fill="x", padx=18, pady=(14, 8))
        if self.icon_img:
            ttk.Label(head, image=self.icon_img).pack(side="left", padx=(0, 12))
        box = ttk.Frame(head)
        box.pack(side="left")
        ttk.Label(box, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(box, text="Screenshot every page, screen and file — websites, apps and folders",
                  style="Sub.TLabel").pack(anchor="w")

    def _entry_row(self, parent, r, label, var, width=None, span=1):
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=r, column=0, sticky="w", padx=(4, 12), pady=5)
        e = ttk.Entry(parent, textvariable=var, width=width or 12)
        e.grid(row=r, column=1, sticky="w" if width else "ew", pady=5, columnspan=span)
        add_edit_support(e)
        return e

    def _target_row(self, parent, label, var, buttons):
        """Big input row: label, entry, action buttons."""
        ttk.Label(parent, text=label, style="Panel.Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w",
                                                                        padx=4, pady=(4, 4))
        e = ttk.Entry(parent, textvariable=var, font=("Segoe UI", 11))
        e.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 2), ipady=3)
        add_edit_support(e)
        bar = ttk.Frame(parent, style="Panel.TFrame")
        bar.grid(row=1, column=2, sticky="e", padx=(8, 4))
        for text, cmd in buttons:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 6))
        parent.columnconfigure(1, weight=1)

    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="x", padx=18)

        # ── Website tab ──
        web = ttk.Frame(self.nb, style="Panel.TFrame", padding=16)
        self.nb.add(web, text="  Website  ")
        self.web_target = tk.StringVar()
        self._target_row(web, "Website address (online or local)", self.web_target,
                         [("Paste", lambda: self.paste_into(self.web_target))])
        ttk.Label(web, text="Any public site or a local dev server, e.g.  https://example.com   or   http://localhost:3000",
                  style="Panel.Muted.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", padx=4, pady=(0, 10))
        opt = ttk.Frame(web, style="Panel.TFrame")
        opt.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.max_pages = tk.IntVar(value=50)
        self.depth_web = tk.IntVar(value=5)
        self.width = tk.IntVar(value=1440)
        self.height = tk.IntVar(value=900)
        self.delay_web = tk.DoubleVar(value=1.0)
        self.mobile = tk.BooleanVar(value=False)
        self.state_file = tk.StringVar()
        left = ttk.Frame(opt, style="Panel.TFrame")
        left.pack(side="left", anchor="n", padx=(0, 40))
        self._entry_row(left, 0, "Max pages", self.max_pages)
        self._entry_row(left, 1, "Crawl depth", self.depth_web)
        self._entry_row(left, 2, "Delay per page (s)", self.delay_web)
        right = ttk.Frame(opt, style="Panel.TFrame")
        right.pack(side="left", anchor="n", fill="x", expand=True)
        right.columnconfigure(1, weight=1)
        self._entry_row(right, 0, "Window width", self.width)
        self._entry_row(right, 1, "Window height", self.height)
        ttk.Checkbutton(right, text="Mobile mode (iPhone 13)", variable=self.mobile,
                        style="Panel.TCheckbutton").grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=5)
        sess = ttk.Frame(web, style="Panel.TFrame")
        sess.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        sess.columnconfigure(1, weight=1)
        ttk.Label(sess, text="Session file (pages behind login)", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(4, 12))
        se = ttk.Entry(sess, textvariable=self.state_file)
        se.grid(row=0, column=1, sticky="ew")
        add_edit_support(se)
        ttk.Button(sess, text="Browse…", command=self.pick_session).grid(row=0, column=2, padx=(6, 4))

        # ── App tab ──
        app = ttk.Frame(self.nb, style="Panel.TFrame", padding=16)
        self.nb.add(app, text="  App (APK / EXE)  ")
        self.app_target = tk.StringVar()
        self._target_row(app, "App file", self.app_target,
                         [("Paste", lambda: self.paste_into(self.app_target)), ("Browse…", self.pick_app)])
        ttk.Label(app, text="Android .apk  ·  Windows .exe / .jar  ·  or attach to a window that is already running (below)",
                  style="Panel.Muted.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", padx=4, pady=(0, 10))
        self.max_screens = tk.IntVar(value=40)
        self.depth_app = tk.IntVar(value=3)
        self.max_clicks = tk.IntVar(value=25)
        self.delay_app = tk.DoubleVar(value=1.0)
        self.scroll = tk.IntVar(value=3)
        self.serial = tk.StringVar()
        self.package = tk.StringVar()
        self.attach = tk.StringVar()
        self.avoid = tk.StringVar(value=sa.DEFAULT_AVOID)
        cols = ttk.Frame(app, style="Panel.TFrame")
        cols.grid(row=3, column=0, columnspan=3, sticky="ew")
        c1 = ttk.Frame(cols, style="Panel.TFrame")
        c1.pack(side="left", anchor="n", padx=(0, 36))
        ttk.Label(c1, text="Common", style="Panel.Section.TLabel").grid(row=0, column=0, sticky="w", padx=4)
        self._entry_row(c1, 1, "Max screens", self.max_screens)
        self._entry_row(c1, 2, "Crawl depth", self.depth_app)
        self._entry_row(c1, 3, "Max taps per screen", self.max_clicks)
        self._entry_row(c1, 4, "Delay per tap (s)", self.delay_app)
        c2 = ttk.Frame(cols, style="Panel.TFrame")
        c2.pack(side="left", anchor="n")
        ttk.Label(c2, text="Android only", style="Panel.Section.TLabel").grid(row=0, column=0, sticky="w", padx=4)
        self._entry_row(c2, 1, "Scroll steps (0 = off)", self.scroll)
        self._entry_row(c2, 2, "Device serial", self.serial, 16)
        self._entry_row(c2, 3, "Package name", self.package, 16)
        win = ttk.Frame(app, style="Panel.TFrame")
        win.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        win.columnconfigure(1, weight=1)
        ttk.Label(win, text="Windows only", style="Panel.Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4)
        ttk.Label(win, text="Attach to running window (title regex)", style="Panel.TLabel").grid(
            row=1, column=0, sticky="w", padx=(4, 12), pady=5)
        ae = ttk.Entry(win, textvariable=self.attach)
        ae.grid(row=1, column=1, sticky="ew", padx=(0, 4))
        add_edit_support(ae)
        ttk.Label(win, text="Leave the app file empty to attach instead of launching.",
                  style="Panel.Muted.TLabel").grid(row=2, column=1, sticky="w", pady=(0, 2))
        av = ttk.Frame(app, style="Panel.TFrame")
        av.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        av.columnconfigure(1, weight=1)
        ttk.Label(av, text="Never tap / click (regex)", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(4, 12))
        avoid_e = ttk.Entry(av, textvariable=self.avoid)
        avoid_e.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        add_edit_support(avoid_e)

        # ── Folder tab ──
        fol = ttk.Frame(self.nb, style="Panel.TFrame", padding=16)
        self.nb.add(fol, text="  Folder  ")
        self.folder_target = tk.StringVar()
        self._target_row(fol, "Folder", self.folder_target,
                         [("Paste", lambda: self.paste_into(self.folder_target)), ("Choose…", self.pick_folder)])
        ttk.Label(fol, text="Renders the content of every file — images, PDFs, text & code, Word / PowerPoint / Excel, "
                            "archives.\nNothing is opened in a browser or in another program.",
                  style="Panel.Muted.TLabel", justify="left").grid(row=2, column=0, columnspan=3, sticky="w", padx=4,
                                                                   pady=(0, 10))
        self.recursive = tk.BooleanVar(value=True)
        self.max_files = tk.IntVar(value=500)
        self.pdf_pages = tk.IntVar(value=10)
        self.text_pages = tk.IntVar(value=3)
        fo = ttk.Frame(fol, style="Panel.TFrame")
        fo.grid(row=3, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(fo, text="Include subfolders", variable=self.recursive, style="Panel.TCheckbutton").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=5)
        self._entry_row(fo, 1, "Max files", self.max_files)
        self._entry_row(fo, 2, "Max pages per PDF", self.pdf_pages)
        self._entry_row(fo, 3, "Max images per text/code file", self.text_pages)

    def _build_run_area(self):
        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=18, pady=(12, 14))

        out_row = ttk.Frame(wrap)
        out_row.pack(fill="x")
        out_row.columnconfigure(1, weight=1)
        ttk.Label(out_row, text="Output folder").grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.out = tk.StringVar(value=str(Path.home() / "SnapshotAll_Output"))
        oe = ttk.Entry(out_row, textvariable=self.out)
        oe.grid(row=0, column=1, sticky="ew")
        add_edit_support(oe)
        ttk.Button(out_row, text="Browse…", command=self.pick_out).grid(row=0, column=2, padx=(6, 0))

        bar = ttk.Frame(wrap)
        bar.pack(fill="x", pady=(12, 8))
        self.start_btn = ttk.Button(bar, text="▶  Start", style="Accent.TButton", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar, text="■  Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        self.open_btn = ttk.Button(bar, text="Open output folder", command=self.open_out, state="disabled")
        self.open_btn.pack(side="right")
        ttk.Button(bar, text="Copy log", command=self.copy_log).pack(side="right", padx=8)

        self.progress = ttk.Progressbar(wrap, mode="determinate", value=0, style="Orange.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(0, 8))

        logf = ttk.Frame(wrap)
        logf.pack(fill="both", expand=True)
        self.log = tk.Text(logf, height=10, state="disabled", bg=LOG_BG, fg=LOG_FG, insertbackground=ORANGE,
                           selectbackground=ORANGE, selectforeground=ON_ORANGE, relief="flat", bd=0, padx=10,
                           pady=8, font=("Consolas", 10), wrap="word", highlightthickness=1,
                           highlightbackground=BORDER, highlightcolor=BORDER)
        sb = ttk.Scrollbar(logf, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        add_edit_support(self.log)

    # ───────────── helpers ─────────────
    def paste_into(self, var):
        try:
            var.set(self.clipboard_get().strip().strip('"'))
        except tk.TclError:
            messagebox.showinfo("Clipboard", "The clipboard is empty.")

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append("".join(self.buf))
        self.append("\n(Log copied to clipboard)\n")

    def pick_app(self):
        f = filedialog.askopenfilename(filetypes=[("Apps", "*.apk *.exe *.jar"), ("Android APK", "*.apk"),
                                                  ("Windows app", "*.exe"), ("Java app", "*.jar")])
        if f:
            self.app_target.set(f)

    def pick_folder(self):
        f = filedialog.askdirectory()
        if f:
            self.folder_target.set(f)

    def pick_session(self):
        f = filedialog.askopenfilename(filetypes=[("Session JSON", "*.json"), ("All files", "*.*")])
        if f:
            self.state_file.set(f)

    def pick_out(self):
        f = filedialog.askdirectory()
        if f:
            self.out.set(f)

    def _resolve_job(self):
        """Return (mode, target, label) for the active tab, or None after showing a warning."""
        tab = self.nb.index(self.nb.select())
        if tab == 0:
            t = self.web_target.get().strip()
            if not t:
                messagebox.showwarning("Missing input", "Enter a website address first.")
                return None
            return "web", t, t
        if tab == 1:
            t = self.app_target.get().strip().strip('"')
            att = self.attach.get().strip()
            low = t.lower()
            if low.endswith(".apk"):
                return "apk", t, Path(t).stem
            if low.endswith((".exe", ".jar")):
                return "desktop", t, Path(t).stem
            if not t and att:
                return "desktop", "", att
            if not t:
                messagebox.showwarning("Missing input", "Choose an .apk / .exe / .jar file, or enter a window title "
                                                        "to attach to.")
            else:
                messagebox.showwarning("Unsupported file", "Supported app files: .apk, .exe, .jar.")
            return None
        t = self.folder_target.get().strip().strip('"')
        if not t or not Path(t).exists():
            messagebox.showwarning("Missing input", "Choose an existing folder first.")
            return None
        return "folder", t, Path(t).name

    # ───────────── run ─────────────
    def start(self):
        job = self._resolve_job()
        if not job:
            return
        mode, target, label = job
        out = Path(self.out.get()) / f"{sa.slugify(label, 30)}_{datetime.now():%Y%m%d_%H%M%S}"
        out.mkdir(parents=True, exist_ok=True)
        self.last_out = out

        is_web = mode == "web"
        ns = argparse.Namespace(
            max_depth=self.depth_web.get() if is_web else self.depth_app.get(),
            delay=self.delay_web.get() if is_web else self.delay_app.get(),
            max_pages=self.max_pages.get(), width=self.width.get(), height=self.height.get(),
            mobile=self.mobile.get(), storage_state=self.state_file.get().strip() or None,
            max_screens=self.max_screens.get(), max_clicks=self.max_clicks.get(), scroll=self.scroll.get(),
            serial=self.serial.get().strip() or None, package=self.package.get().strip() or None,
            avoid=self.avoid.get().strip(), attach=self.attach.get().strip() or None,
            recursive=self.recursive.get(), max_files=self.max_files.get(),
            pdf_pages=self.pdf_pages.get(), text_pages=self.text_pages.get(),
        )
        runner = {"web": sa.run_web, "apk": sa.run_apk, "desktop": sd.run_desktop, "folder": sf.run_folder}[mode]

        self.clear_log()
        self.buf.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.open_btn.config(state="disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        sa.STOP.clear()

        def worker():
            sys.stdout = sys.stderr = QWriter(self.q, self.buf)
            try:
                try:
                    runner(target, out, ns)
                except sa.BrowserUnavailable as e:
                    print(f"No usable browser found ({e}).")
                    print("Downloading Chromium (one-time, about 150 MB)…")
                    sa.install_chromium()
                    runner(target, out, ns)
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
        self.append("\nStopping… (after the current item finishes)\n")

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
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
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
