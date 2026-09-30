"""
Folder mode - render the CONTENT of every file in a folder into screenshots.

Nothing is opened in a browser or in external programs. Files are rendered directly:
  images        -> re-saved as PNG
  PDF           -> each page rendered to an image (PyMuPDF)
  text / code   -> syntax-neutral "code card" with line numbers (HTML is shown as source)
  docx/pptx/xlsx-> extracted text on a card
  archives      -> file listing on a card
  anything else -> info card (name, size, type, modified date)
"""
import html
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from snapshot_common import STOP

IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tif", ".tiff", ".ppm"}
TEXT_EXT = {
    ".txt", ".md", ".rst", ".log", ".csv", ".tsv", ".json", ".xml", ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".conf", ".env", ".properties", ".html", ".htm", ".css", ".scss", ".less", ".svg", ".js", ".jsx", ".ts",
    ".tsx", ".vue", ".py", ".java", ".kt", ".c", ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".php", ".rb",
    ".sh", ".bat", ".cmd", ".ps1", ".sql", ".swift", ".dart", ".gradle", ".lua", ".r", ".tex", ".gitignore",
}
OFFICE_EXT = {".docx", ".pptx", ".xlsx"}
ARCHIVE_EXT = {".zip", ".jar", ".apk", ".whl"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".svn", ".idea", ".vscode", "venv", ".venv"}

# Theme (matches the app)
BG = (23, 18, 14)
HEADER = (34, 27, 21)
FG = (234, 223, 211)
MUTED = (140, 126, 113)
ORANGE = (249, 115, 22)

MONO_FONTS = [
    "C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cascadiamono.ttf", "C:/Windows/Fonts/lucon.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Courier New.ttf",
]
SANS_FONTS = [
    "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
]


def _font(candidates, size):
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


def _safe(name):
    return re.sub(r'[<>:"/\\|?*]+', "_", name)


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ───────────────────────── card renderer ─────────────────────────

def render_card(title, subtitle, lines, per_page=70, max_pages=3, cols=110):
    """Render text lines into one or more dark 'code card' images."""
    mono = _font(MONO_FONTS, 16)
    head = _font(SANS_FONTS, 22)
    small = _font(MONO_FONTS, 14)
    cw = max(int(mono.getlength("M")), 8)
    longest = max((len(l.expandtabs(4)) for l in lines), default=0)
    cols = max(60, min(cols, longest))  # card width follows the content
    lh = 24
    gutter = cw * 5
    pad = 24
    width = pad * 2 + gutter + cw * cols
    head_h = 78

    # wrap long lines
    rows = []
    for n, line in enumerate(lines, 1):
        line = line.expandtabs(4).replace("\r", "")
        chunks = [line[i:i + cols] for i in range(0, len(line), cols)] or [""]
        for i, ch in enumerate(chunks):
            rows.append((n if i == 0 else None, ch))

    pages = [rows[i:i + per_page] for i in range(0, len(rows), per_page)] or [[]]
    truncated = len(pages) > max_pages
    pages = pages[:max_pages]

    images = []
    for idx, chunk in enumerate(pages, 1):
        height = head_h + pad + lh * max(len(chunk), 1) + pad + (lh if truncated and idx == len(pages) else 0)
        img = Image.new("RGB", (width, height), BG)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, width, head_h], fill=HEADER)
        d.rectangle([0, head_h - 3, width, head_h], fill=ORANGE)
        d.text((pad, 12), title[:90], font=head, fill=ORANGE)
        d.text((pad, 46), subtitle[:150] + (f"   ·   page {idx}/{len(pages)}" if len(pages) > 1 else ""),
               font=small, fill=MUTED)
        y = head_h + pad
        for num, text in chunk:
            if num is not None:
                d.text((pad, y), str(num).rjust(4), font=mono, fill=MUTED)
            d.text((pad + gutter, y), text, font=mono, fill=FG)
            y += lh
        if truncated and idx == len(pages):
            d.text((pad + gutter, y + 4), "… content truncated", font=mono, fill=ORANGE)
        images.append(img)
    return images


# ───────────────────────── per-type extractors ─────────────────────────

def _read_text(path, limit=2_000_000):
    raw = path.read_bytes()[:limit]
    if b"\x00" in raw[:4096]:
        return None
    for enc in ("utf-8-sig", "utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig",):
        try:
            return raw.decode(enc).splitlines()
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace").splitlines()


def _office_lines(path, ext):
    lines = []
    with zipfile.ZipFile(path) as z:
        if ext == ".docx":
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
            for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
                lines.append(html.unescape("".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))))
        elif ext == ".pptx":
            slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                            key=lambda n: int(re.search(r"(\d+)", n.split("/")[-1]).group(1)))
            for i, name in enumerate(slides, 1):
                xml = z.read(name).decode("utf-8", "ignore")
                lines.append(f"--- Slide {i} ---")
                lines += [html.unescape(t) for t in re.findall(r"<a:t>(.*?)</a:t>", xml, re.S)]
                lines.append("")
        elif ext == ".xlsx":
            wb = z.read("xl/workbook.xml").decode("utf-8", "ignore")
            lines.append("Sheets: " + ", ".join(html.unescape(s) for s in re.findall(r'<sheet [^>]*name="([^"]*)"', wb)))
            lines.append("")
            if "xl/sharedStrings.xml" in z.namelist():
                ss = z.read("xl/sharedStrings.xml").decode("utf-8", "ignore")
                for si in re.findall(r"<si>(.*?)</si>", ss, re.S)[:200]:
                    lines.append(html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
    return lines


def _meta_lines(path):
    st = path.stat()
    return [
        f"Name      : {path.name}",
        f"Location  : {path.parent}",
        f"Size      : {_human(st.st_size)}",
        f"Modified  : {datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M:%S}",
        f"Type      : {path.suffix.lower() or '(no extension)'}",
    ]


# ───────────────────────── main entry ─────────────────────────

def _render_file(path: Path, a):
    """Return (kind, [PIL images]) for one file."""
    ext = path.suffix.lower()
    subtitle = f"{_human(path.stat().st_size)}  ·  {path}"

    if ext in IMG_EXT:
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)
            img.seek(0)
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
            if max(img.size) > 6000:
                img.thumbnail((6000, 6000))
            return "image", [img]
        except Exception:
            pass

    if ext == ".pdf":
        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz
            doc = fitz.open(str(path))
            out = []
            for i in range(min(doc.page_count, a.pdf_pages)):
                pix = doc[i].get_pixmap(matrix=fitz.Matrix(1.6, 1.6))
                out.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
            doc.close()
            if out:
                return "pdf", out
        except Exception as e:
            lines = _meta_lines(path) + ["", f"PDF could not be rendered: {e}"]
            return "info", render_card(path.name, subtitle, lines, max_pages=1)

    if ext in OFFICE_EXT:
        try:
            body = _office_lines(path, ext)
            lines = _meta_lines(path) + ["", "── extracted text ──"] + (body or ["(no text found)"])
            return "office", render_card(path.name, subtitle, lines, max_pages=a.text_pages)
        except Exception:
            pass

    if ext in ARCHIVE_EXT:
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            lines = _meta_lines(path) + ["", f"── {len(names)} entries ──"] + names[:400]
            return "archive", render_card(path.name, subtitle, lines, max_pages=a.text_pages)
        except Exception:
            pass

    if ext in TEXT_EXT or ext == "":
        try:
            lines = _read_text(path)
            if lines is not None:
                return "text", render_card(path.name, subtitle, lines or ["(empty file)"], max_pages=a.text_pages)
        except Exception:
            pass

    lines = _meta_lines(path) + ["", "No preview is available for this file type."]
    return "info", render_card(path.name, subtitle, lines, max_pages=1)


def run_folder(target, out: Path, a):
    top = Path(target)
    if not top.exists():
        raise SystemExit(f"Path not found: {top}")

    out_resolved = out.resolve()
    files = []
    if top.is_file():
        files = [top]
        base = top.parent
    else:
        base = top
        for root, dirs, names in os.walk(top):
            dirs[:] = sorted(d for d in dirs
                             if not d.startswith(".") and d not in SKIP_DIRS
                             and Path(root, d).resolve() != out_resolved)
            if not a.recursive:
                dirs[:] = []
            files += [Path(root, n) for n in sorted(names) if not n.startswith(".")]

    total = min(len(files), a.max_files)
    print(f"Found {len(files)} file(s); capturing {total}.")
    lines, count = [], 0
    for path in files[: a.max_files]:
        if STOP.is_set():
            break
        rel = path.relative_to(base)
        try:
            kind, images = _render_file(path, a)
        except Exception as e:
            print(f"  ! Error on {rel}: {e}")
            continue
        dest_dir = out / rel.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        stem = _safe(path.name)
        for i, img in enumerate(images, 1):
            name = f"{stem}.png" if len(images) == 1 else f"{stem}_p{i:02d}.png"
            img.save(dest_dir / name)
            lines.append(f"{(rel.parent / name).as_posix()}\t{rel.as_posix()}\t{kind}")
        count += 1
        print(f"[{count}/{total}] {rel.as_posix()}  ({kind}, {len(images)} image(s))")

    (out / "index.tsv").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDone: {count} file(s) rendered to {out}")
