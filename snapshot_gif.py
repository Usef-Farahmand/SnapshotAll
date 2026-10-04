"""
GIF flows - one animated GIF per navigation path ("flow") through the captured pages / screens.

A flow is an ordered list of pages (any length >= 2). Every frame shows the page and, underneath, a
caption with the whole path, the current step highlighted, so you always see where you are:

    Home  ›  Projects  ›  Project A  ›  Contact           3 / 4

The caption never contains Persian / Arabic / Hebrew text (it cannot be shaped reliably): such titles are
replaced by the last part of the address, or by "Page 3" / "Screen 3". The app icon is added as a watermark.
"""
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image, ImageDraw, ImageFont

from snapshot_common import page_key, slugify

W, H, CAP = 960, 600, 84          # picture area and caption bar at scale 1.0 (pixels)
BG = (15, 12, 10)
BAR = (23, 18, 14)
FG = (245, 238, 232)
MUTED = (140, 126, 113)
FAINT = (122, 109, 97)
ORANGE = (249, 115, 22)
SEP = "  ›  "
RTL = re.compile("[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]")

SANS = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Helvetica.ttc"]
SANS_BOLD = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]


def _asset(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / name


def _font(candidates, size):
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


@lru_cache(maxsize=8)
def _fonts(k):
    return _font(SANS, max(int(22 * k), 9)), _font(SANS_BOLD, max(int(22 * k), 9)), _font(SANS, max(int(15 * k), 8))


@lru_cache(maxsize=8)
def _watermark(size):
    """The app icon as (rgb, alpha-mask), semi transparent."""
    try:
        im = Image.open(_asset("logo.png")).convert("RGBA").resize((size, size), Image.LANCZOS)
        return im.convert("RGB"), im.getchannel("A").point(lambda a: int(a * 0.75))
    except Exception:
        return None


# ───────────────────────── titles ─────────────────────────

def _clean(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return re.sub(r"^[\s→←↗↘➜➔»«›‹>|•·:]+|[\s→←↗↘➜➔»«›‹>|•·:]+$", "", text)


def _is_page(item):
    return "://" in item.get("label", "")


def _title(item, idx):
    """Short, Latin-script name of a step. Persian / Arabic / Hebrew text is never used."""
    if idx == 0:
        return "Home"
    candidates = [_clean(item.get("title"))]
    label = item.get("label", "")
    if _is_page(item):
        tail = [seg for seg in unquote(re.sub(r"[?#].*$", "", label.split("://", 1)[1])).split("/")[1:] if seg]
        if tail:
            candidates.append(_clean(re.sub(r"\.(html?|php|aspx?)$", "", tail[-1]).replace("-", " ").replace("_", " ")))
    else:
        candidates.append(_clean(label.rsplit(" > ", 1)[-1]))
    for text in candidates:
        if text and not RTL.search(text):
            return text if len(text) <= 40 else text[:39] + "…"
    return f"Page {idx + 1}" if _is_page(item) else f"Screen {idx + 1}"


def crumbs(flow):
    return [_title(it, i) for i, it in enumerate(flow)]


def describe_flows(flows):
    """Human-readable breadcrumbs, one per flow (for previews in the UI)."""
    return [SEP.join(crumbs(f)) for f in flows]


def _location(item, idx):
    label = item.get("label", "")
    if _is_page(item):
        text = label.split("://", 1)[1].rstrip("/")
        return text if not RTL.search(text) else re.sub(RTL, "", text)
    parts = label.replace(" (scroll", "").split(" > ")
    return "  ›  ".join(p if not RTL.search(p) else "…" for p in parts)


# ───────────────────────── building flows ─────────────────────────

def _kept_parent(label, lookup, kept):
    """Nearest ancestor (by discovery) of `label` that is part of the flows."""
    seen = set()
    parent = lookup[label].get("parent")
    while parent is not None and parent not in kept and parent not in seen:
        seen.add(parent)
        if parent in lookup:
            parent = lookup[parent].get("parent")
        elif " > " in parent:                      # app trail whose screen was a duplicate / not captured
            parent = parent.rsplit(" > ", 1)[0]
        else:
            parent = None
    return parent if parent in kept else None


def _path_of(label):
    return urlparse(label).path.rstrip("/") if "://" in label else None


def build_flows(items, all_items=None, max_flows=12, target_steps=5):
    """Return flows: lists of items, each starting at a root page / screen.

    1. Every page gets its most plausible *referrer* as parent: a link inside the content beats a menu
       link, a page above it in the URL hierarchy beats an unrelated one. Root -> leaf paths are the
       base flows (they follow the structure of the site / app).
    2. Flows shorter than `target_steps` are continued along real links to pages they do not contain
       yet (content links first, then menu links; pages used by few flows first), so flows are not all
       "start page + one page".

    items       the items to include (e.g. the ones the user selected); dicts with label, parent, title,
                path, kind and (websites) links
    all_items   every captured item, used to find ancestors when a page on the way was not selected
    """
    screens = [it for it in items if it.get("kind", "screen") == "screen"]
    kept = [it["label"] for it in screens]
    kept_set = set(kept)
    lookup = {it["label"]: it for it in (all_items or items) if it.get("kind", "screen") == "screen"}
    lookup.update({it["label"]: it for it in screens})
    order = {lb: i for i, lb in enumerate(kept)}

    # outgoing links between the pages that are part of the flows
    by_key = {page_key(lb): lb for lb in kept if _is_page(lookup[lb])}
    out_links = {lb: [] for lb in kept}                      # label -> [(target label, zone)]
    referrers = {lb: [] for lb in kept}
    for lb in kept:
        seen_targets = set()
        for target, _text, zone in (lookup[lb].get("links") or []):
            t = by_key.get(page_key(target))
            if t and t != lb and t not in seen_targets:
                seen_targets.add(t)
                out_links[lb].append((t, zone))
                referrers[t].append((lb, zone))

    # 1. parents -> base flows
    parent_of = {}
    for lb in kept:
        bfs_parent = _kept_parent(lb, lookup, kept_set)
        earlier = [(r, z) for r, z in referrers[lb] if order[r] < order[lb]]
        if not earlier:
            parent_of[lb] = bfs_parent
            continue
        lp = _path_of(lb)

        def score(rz, lb=lb, lp=lp, bfs_parent=bfs_parent):
            r, zone = rz
            rp = _path_of(r)
            s = 3 if zone == "content" else 0
            if rp is not None and lp is not None and lp.startswith(rp + "/"):
                s += 2                                       # the referrer is "above" the page in the URL
            if r == bfs_parent:
                s += 1
            return (s, -order[r])
        parent_of[lb] = max(earlier, key=score)[0]

    has_children = {p for p in parent_of.values() if p is not None}
    chains = []
    for leaf in kept:
        if leaf in has_children:
            continue
        chain, cur, guard = [], leaf, set()
        while cur is not None and cur not in guard:
            guard.add(cur)
            chain.append(cur)
            cur = parent_of[cur]
        chain.reverse()
        if len(chain) >= 2:
            chains.append(chain)

    # 2. continue short flows along real links
    usage = Counter(lb for ch in chains for lb in ch)
    for chain in chains:
        guard = set(chain)
        while len(chain) < target_steps:
            options = [(0 if zone == "content" else 1, usage[t], order[t], t)
                       for t, zone in out_links[chain[-1]] if t not in guard]
            if not options:
                break
            nxt = min(options)[3]
            chain.append(nxt)
            guard.add(nxt)
            usage[nxt] += 1

    # drop duplicates and flows that are only the beginning of another flow
    unique = []
    for ch in sorted(chains, key=lambda c: (-len(c), order[c[-1]])):
        if not any(ch == o[:len(ch)] for o in unique):
            unique.append(ch)
    return [[lookup[lb] for lb in ch] for ch in unique[:max_flows]]


# ───────────────────────── drawing ─────────────────────────

def _fit_crumbs(names, idx, f_bold, f_reg, max_width):
    """Shorten the breadcrumb until it fits. Returns (strings to draw, index of the current one)."""
    sep_w = f_reg.getlength(SEP)

    def total(items, cur):
        return sum((f_bold if i == cur else f_reg).getlength(t) for i, t in enumerate(items)) + sep_w * (len(items) - 1)

    def short(items, limit):
        return [t if len(t) <= limit else t[: limit - 1] + "…" for t in items]

    for limit in (40, 24, 16, 10):
        shown = short(names, limit)
        if total(shown, idx) <= max_width:
            return shown, idx
    for start in range(1, idx + 1):                # still too long: first step, "…", then the steps from `start`
        shown = [names[0], "…"] + short(names[start:], 10)
        cur = idx - start + 2
        if total(shown, cur) <= max_width or start == idx:
            return shown, cur
    return short(names, 10), idx


def page_view(shot_path):
    """The 'first screen' of a full-page screenshot."""
    img = Image.open(shot_path).convert("RGB")
    w, h = img.size
    crop_h = min(h, int(w / 1.6)) if w >= 1000 else min(h, int(w * 2.1))
    return img.crop((0, 0, w, max(crop_h, 1)))


def compose_frame(view, names, idx, location, k=1.0, watermark=True):
    """One GIF frame: the page picture, the app-icon watermark and the caption bar (scale k)."""
    Wk, Hk, CAPk = int(W * k), int(H * k), int(CAP * k)
    f_reg, f_bold, f_small = _fonts(k)
    scale = min(Wk / view.width, Hk / view.height)
    view = view.resize((max(1, int(view.width * scale)), max(1, int(view.height * scale))), Image.LANCZOS)

    canvas = Image.new("RGB", (Wk, Hk + CAPk), BG)
    canvas.paste(view, ((Wk - view.width) // 2, (Hk - view.height) // 2))
    if watermark:
        wm = _watermark(max(int(54 * k), 16))
        if wm:
            canvas.paste(wm[0], (Wk - wm[0].width - int(14 * k), Hk - wm[0].height - int(14 * k)), wm[1])   # bottom right
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, Hk, Wk, Hk + CAPk], fill=BAR)
    d.rectangle([0, Hk, Wk, Hk + max(2, int(2 * k))], fill=ORANGE)
    pad = int(24 * k)

    total = len(names)
    counter = f"{idx + 1} / {total}"
    d.text((Wk - pad - f_bold.getlength(counter), Hk + int(14 * k)), counter, font=f_bold, fill=FG)
    dot, gap = max(int(9 * k), 4), max(int(7 * k), 3)
    x0 = Wk - pad - (dot * total + gap * (total - 1))
    for i in range(total):
        box = [x0 + i * (dot + gap), Hk + int(48 * k), x0 + i * (dot + gap) + dot, Hk + int(48 * k) + dot]
        if i <= idx:
            d.ellipse(box, fill=ORANGE)
        else:
            d.ellipse(box, outline=FAINT, width=max(1, int(2 * k)))

    shown, cur = _fit_crumbs(names, idx, f_bold, f_reg, Wk - 2 * pad - int(130 * k))
    x, y = pad, Hk + int(14 * k)
    for i, t in enumerate(shown):
        font = f_bold if i == cur else f_reg
        color = ORANGE if i == cur else (FG if i < cur else FAINT)
        d.text((x, y), t, font=font, fill=color)
        x += font.getlength(t)
        if i < len(shown) - 1:
            d.text((x, y), SEP, font=f_reg, fill=MUTED)
            x += f_reg.getlength(SEP)

    maxw = Wk - 2 * pad - int(130 * k)
    loc = location
    while f_small.getlength(loc) > maxw and len(loc) > 12:
        loc = loc[: int(len(loc) * 0.9)]
    d.text((pad, Hk + int(50 * k)), loc if loc == location else loc + "…", font=f_small, fill=MUTED)
    return canvas


def save_frames_gif(frames, durations, out_path):
    """Write frames with ONE shared palette, so unchanged areas compress away between frames."""
    sample = Image.new("RGB", (frames[0].width, frames[0].height * 3))
    for i, f in enumerate((frames[0], frames[len(frames) // 2], frames[-1])):
        sample.paste(f, (0, i * frames[0].height))
    pal = sample.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pframes = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    pframes[0].save(out_path, save_all=True, append_images=pframes[1:], duration=durations, loop=0, disposal=1)


def flow_filename(number, names):
    return f"flow_{number:02d}_{slugify('-'.join(names), 60).lower()}.gif"


# ───────────────────────── slideshow GIFs ─────────────────────────

def render_flow_gif(flow, dest_dir: Path, number: int, seconds_per_step=1.6, watermark=True):
    """Slideshow: one frame per page. Returns the GIF path."""
    names = crumbs(flow)
    frames = [compose_frame(page_view(it["path"]), names, i, _location(it, i), 1.0, watermark)
              for i, it in enumerate(flow)]
    step = max(int(seconds_per_step * 1000), 200)
    durations = [step] * len(frames)
    durations[-1] = int(step * 1.6)                       # linger a little on the last page
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / flow_filename(number, names)
    pal = [f.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=durations, loop=0, disposal=2)
    return out


def render_flows(flows, dest_dir, seconds_per_step=1.6, watermark=True, progress=None):
    """Slideshow GIFs for ready-made flows (lists of items). `progress(n, total, breadcrumb)`."""
    made = []
    for n, flow in enumerate(flows, 1):
        if progress:
            progress(n, len(flows), SEP.join(crumbs(flow)))
        made.append(render_flow_gif(flow, Path(dest_dir), n, seconds_per_step, watermark))
    return made


def export_flows(items, dest_dir, all_items=None, seconds_per_step=1.6, max_flows=12, target_steps=5,
                 watermark=True, progress=None):
    """Build the flows from `items` and write one slideshow GIF per flow."""
    flows = build_flows(items, all_items, max_flows, target_steps)
    return render_flows(flows, dest_dir, seconds_per_step, watermark, progress)
