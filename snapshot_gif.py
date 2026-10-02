"""
GIF flows - one animated GIF per navigation path ("flow") through the captured pages / screens.

A flow is a path in the discovery tree: it starts at the start page (or app home screen) and ends at a
page that no other captured page was reached from. Every frame shows the page and, underneath, a caption
with the whole path, the current step highlighted, so you always see where you are:

    Home  ›  Projects  ›  Project A           2 / 3
"""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from snapshot_common import slugify

W, H, CAP = 960, 600, 84          # picture area and caption bar (pixels)
BG = (15, 12, 10)
BAR = (23, 18, 14)
FG = (245, 238, 232)
MUTED = (140, 126, 113)
FAINT = (122, 109, 97)
ORANGE = (249, 115, 22)

SANS = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Helvetica.ttc"]
SANS_BOLD = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]


def _font(candidates, size):
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


# ───────────────────────── building flows ─────────────────────────

def _title(item, is_root):
    if is_root:
        return "Home"
    text = re.sub(r"\s+", " ", (item.get("title") or "")).strip()
    text = re.sub(r"^[\s→←↗↘➜➔»«›‹>|•·:]+|[\s→←↗↘➜➔»«›‹>|•·:]+$", "", text)   # arrows / separators around link text
    if not text:
        label = item.get("label", "")
        if "://" in label:
            tail = [seg for seg in re.sub(r"[?#].*$", "", label.split("://", 1)[1]).split("/")[1:] if seg]
            text = tail[-1].replace("-", " ").replace("_", " ") if tail else "Page"
        else:
            text = label.rsplit(" > ", 1)[-1]
    return text if len(text) <= 40 else text[:39] + "…"


def _kept_parent(label, lookup, kept):
    """Nearest ancestor of `label` that is part of the flows (skips de-selected / missing pages)."""
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


def build_flows(items, all_items=None, max_flows=12):
    """Return flows: lists of items from a root page/screen down to a leaf.

    items      the items to include (e.g. the ones the user selected); dicts with
               label, parent, title, path, kind
    all_items  every captured item, used to find ancestors when a page on the way was not selected
    """
    screens = [it for it in items if it.get("kind", "screen") == "screen"]
    kept = {it["label"] for it in screens}
    lookup = {it["label"]: it for it in (all_items or items) if it.get("kind", "screen") == "screen"}
    lookup.update({it["label"]: it for it in screens})
    order = {it["label"]: i for i, it in enumerate(screens)}

    parent_of = {lb: _kept_parent(lb, lookup, kept) for lb in kept}
    has_children = {p for p in parent_of.values() if p is not None}

    flows = []
    for leaf in (it["label"] for it in screens):
        if leaf in has_children:
            continue
        chain, cur, guard = [], leaf, set()
        while cur is not None and cur not in guard:
            guard.add(cur)
            chain.append(cur)
            cur = parent_of[cur]
        chain.reverse()
        if len(chain) >= 2:
            flows.append([lookup[lb] for lb in chain])

    flows.sort(key=lambda f: (-len(f), order[f[-1]["label"]]))   # deepest paths first
    return flows[:max_flows]


def crumbs(flow):
    return [_title(it, i == 0) for i, it in enumerate(flow)]


def describe_flows(flows):
    """Human-readable breadcrumbs, one per flow (for previews in the UI)."""
    return ["  ›  ".join(crumbs(f)) for f in flows]


# ───────────────────────── rendering ─────────────────────────

def _location(item):
    label = item.get("label", "")
    if "://" in label:
        return label.split("://", 1)[1].rstrip("/")
    return label.replace(" > ", "  ›  ")


def _fit_crumbs(names, idx, f_bold, f_reg, max_width):
    """Shorten the breadcrumb until it fits. Returns (strings to draw, index of the current one)."""
    sep_w = f_reg.getlength("  ›  ")

    def total(items, cur):
        return sum((f_bold if i == cur else f_reg).getlength(t) for i, t in enumerate(items)) + sep_w * (len(items) - 1)

    def short(items, limit):
        return [t if len(t) <= limit else t[: limit - 1] + "…" for t in items]

    for limit in (40, 24, 16, 10):
        shown = short(names, limit)
        if total(shown, idx) <= max_width:
            return shown, idx
    # still too long: keep the first step, an ellipsis and the steps from `start` on
    for start in range(1, idx + 1):
        shown = [names[0], "…"] + short(names[start:], 10)
        cur = idx - start + 2
        if total(shown, cur) <= max_width or start == idx:
            return shown, cur
    return short(names, 10), idx


def _frame(shot_path, names, idx, location, fonts):
    f_reg, f_bold, f_small = fonts
    img = Image.open(shot_path).convert("RGB")
    w, h = img.size
    crop_h = min(h, int(w / 1.6)) if w >= 1000 else min(h, int(w * 2.1))   # the "first screen" of the page
    view = img.crop((0, 0, w, max(crop_h, 1)))
    scale = min(W / view.width, H / view.height)
    view = view.resize((max(1, int(view.width * scale)), max(1, int(view.height * scale))), Image.LANCZOS)

    canvas = Image.new("RGB", (W, H + CAP), BG)
    canvas.paste(view, ((W - view.width) // 2, (H - view.height) // 2))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, H, W, H + CAP], fill=BAR)
    d.rectangle([0, H, W, H + 2], fill=ORANGE)

    # step counter + dots (right)
    total = len(names)
    counter = f"{idx + 1} / {total}"
    d.text((W - 24 - f_bold.getlength(counter), H + 14), counter, font=f_bold, fill=FG)
    dot, gap = 9, 7
    x = W - 24 - (dot * total + gap * (total - 1))
    for i in range(total):
        box = [x + i * (dot + gap), H + 48, x + i * (dot + gap) + dot, H + 48 + dot]
        if i <= idx:
            d.ellipse(box, fill=ORANGE)
        else:
            d.ellipse(box, outline=FAINT, width=2)

    # breadcrumb (left): visited = light, current = orange + bold, upcoming = faint
    shown, cur = _fit_crumbs(names, idx, f_bold, f_reg, W - 48 - 130)
    x, y = 24, H + 14
    for i, t in enumerate(shown):
        font = f_bold if i == cur else f_reg
        color = ORANGE if i == cur else (FG if i < cur else FAINT)
        d.text((x, y), t, font=font, fill=color)
        x += font.getlength(t)
        if i < len(shown) - 1:
            d.text((x, y), "  ›  ", font=f_reg, fill=MUTED)
            x += f_reg.getlength("  ›  ")

    loc = location if f_small.getlength(location) <= W - 48 - 130 else location[:90] + "…"
    d.text((24, H + 50), loc, font=f_small, fill=MUTED)
    return canvas


def render_flow_gif(flow, dest_dir: Path, number: int, seconds_per_step: float = 1.6):
    """Write one GIF for the flow and return its path."""
    names = crumbs(flow)
    fonts = (_font(SANS, 22), _font(SANS_BOLD, 22), _font(SANS, 15))
    frames = [_frame(it["path"], names, i, _location(it), fonts) for i, it in enumerate(flow)]
    pal = [f.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]

    step = max(int(seconds_per_step * 1000), 200)
    durations = [step] * len(pal)
    durations[-1] = int(step * 1.6)                       # linger a little on the last page
    name = f"flow_{number:02d}_{slugify('-'.join(names), 60).lower()}.gif"
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / name
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=durations, loop=0, disposal=2)
    return out


def export_flows(items, dest_dir: Path, all_items=None, seconds_per_step=1.6, max_flows=12, progress=None):
    """Create one GIF per flow. `progress(done, total, breadcrumb)` is called before each GIF."""
    flows = build_flows(items, all_items, max_flows)
    created = []
    for n, flow in enumerate(flows, 1):
        if progress:
            progress(n, len(flows), "  ›  ".join(crumbs(flow)))
        created.append(render_flow_gif(flow, Path(dest_dir), n, seconds_per_step))
    return created
