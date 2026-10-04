"""Unit tests for GIF flows (no browser needed)."""
from PIL import Image

import snapshot_gif as sg


def item(label, parent=None, title="", kind="screen", path=None):
    return {"label": label, "parent": parent, "title": title, "kind": kind, "path": path}


SITE = [
    item("https://x.com/", None),
    item("https://x.com/about", "https://x.com/", "About"),
    item("https://x.com/services/", "https://x.com/", "Services"),
    item("https://x.com/services/design", "https://x.com/services/", "Design →"),
    item("https://x.com/services/dev", "https://x.com/services/", "Development"),
    item("https://x.com/contact", "https://x.com/", "Contact"),
]


def names(flows):
    return [sg.crumbs(f) for f in flows]


def test_flows_are_root_to_leaf_paths_deepest_first():
    flows = sg.build_flows(SITE)
    assert names(flows) == [
        ["Home", "Services", "Design"],
        ["Home", "Services", "Development"],
        ["Home", "About"],
        ["Home", "Contact"],
    ]


def test_arrows_around_link_text_are_removed():
    assert sg.crumbs(sg.build_flows(SITE)[0])[-1] == "Design"


def test_missing_title_falls_back_to_the_url_path():
    flows = sg.build_flows([item("https://x.com/", None), item("https://x.com/our-team", "https://x.com/", "")])
    assert sg.crumbs(flows[0]) == ["Home", "our team"]


def test_deselected_middle_page_is_skipped_but_its_children_stay():
    selected = [it for it in SITE if it["label"] != "https://x.com/services/"]
    flows = sg.build_flows(selected, all_items=SITE)
    assert ["Home", "Design"] in names(flows)
    assert ["Home", "Development"] in names(flows)


def test_page_that_loses_its_children_becomes_a_leaf():
    selected = [it for it in SITE if "services/" not in it["label"] or it["label"].endswith("services/")]
    flows = sg.build_flows(selected, all_items=SITE)
    assert ["Home", "Services"] in names(flows)


def test_single_page_has_no_flow():
    assert sg.build_flows([item("https://x.com/", None)]) == []


def test_scroll_captures_are_not_part_of_flows():
    items = [item("home", None), item("home > Settings", "home", "Settings"),
             item("home > Settings (scroll 1)", "home > Settings", "", kind="scroll")]
    assert names(sg.build_flows(items)) == [["Home", "Settings"]]


def test_app_trails_find_their_parent_even_when_a_screen_was_not_captured():
    items = [item("home", None), item("home > A > B", "home > A", "B")]    # "home > A" is missing
    assert names(sg.build_flows(items)) == [["Home", "B"]]


def test_max_flows_limits_the_result():
    assert len(sg.build_flows(SITE, max_flows=2)) == 2


def make_shot(tmp_path, name, color, size=(1440, 3000)):
    p = tmp_path / name
    Image.new("RGB", size, color).save(p)
    return p


def test_gif_has_one_frame_per_step_and_a_caption_bar(tmp_path):
    items = [
        item("https://x.com/", None, path=make_shot(tmp_path, "a.png", (249, 115, 22))),
        item("https://x.com/p", "https://x.com/", "Projects", path=make_shot(tmp_path, "b.png", (59, 130, 246))),
        item("https://x.com/p/1", "https://x.com/p", "Project A", path=make_shot(tmp_path, "c.png", (34, 197, 94))),
    ]
    made = sg.export_flows(items, tmp_path / "flows", seconds_per_step=1.0)
    assert [m.name for m in made] == ["flow_01_home_projects_project_a.gif"]
    gif = Image.open(made[0])
    assert gif.n_frames == 3
    assert gif.size == (sg.W, sg.H + sg.CAP)
    durations = []
    for i in range(gif.n_frames):
        gif.seek(i)
        durations.append(gif.info["duration"])
    assert durations[0] == 1000 and durations[-1] > durations[0]       # the last page lingers
    gif.seek(0)
    caption = gif.convert("RGB").getpixel((5, sg.H + 40))
    assert caption == sg.BAR or sum(abs(a - b) for a, b in zip(caption, sg.BAR)) < 12


def test_very_long_flows_and_titles_still_render(tmp_path):
    shot = make_shot(tmp_path, "s.png", (200, 200, 200), size=(390, 800))      # phone-sized screenshot
    items, parent = [], None
    for i in range(9):
        label = f"https://x.com/{i}"
        items.append(item(label, parent, "A rather long page title number %d for testing" % i, path=shot))
        parent = label
    made = sg.export_flows(items, tmp_path / "flows")
    assert len(made) == 1 and Image.open(made[0]).n_frames == 9


# ───────────────────────── longer flows from the link graph ─────────────────────────

def link(target, text="", zone="content"):
    return (target, text, zone)


HOME, ABOUT, SERV, DESIGN, CONTACT = ("https://x.com/", "https://x.com/about", "https://x.com/services/",
                                      "https://x.com/services/design", "https://x.com/contact")
MENU = [link(HOME, "Home", "nav"), link(ABOUT, "About", "nav"), link(SERV, "Services", "nav"),
        link(CONTACT, "Contact", "nav")]


def graph_site():
    """A flat site: every page has the same menu; /services links to its child page in the content."""
    return [
        item(HOME, None) | {"links": MENU},
        item(ABOUT, HOME, "About") | {"links": MENU},
        item(SERV, HOME, "Services") | {"links": MENU + [link(DESIGN, "Design", "content")]},
        item(DESIGN, SERV, "Design") | {"links": MENU},
        item(CONTACT, HOME, "Contact") | {"links": MENU},
    ]


def test_flows_are_not_limited_to_two_steps():
    flows = sg.build_flows(graph_site(), target_steps=4)
    assert flows and all(len(f) >= 3 for f in flows)
    assert max(len(f) for f in flows) >= 4


def test_target_steps_of_two_keeps_flows_short():
    assert {len(f) for f in sg.build_flows(graph_site(), target_steps=2)} == {2, 3}


def test_no_page_repeats_inside_a_flow_and_no_flow_repeats():
    flows = sg.build_flows(graph_site(), target_steps=6)
    labels = [tuple(it["label"] for it in f) for f in flows]
    assert len(set(labels)) == len(labels)
    assert all(len(set(lb)) == len(lb) for lb in labels)


def test_content_link_and_url_hierarchy_decide_the_parent():
    flows = sg.build_flows(graph_site(), target_steps=2)
    assert ["Home", "Services", "Design"] in names(flows)         # not Home -> Design


def test_every_flow_starts_at_the_start_page():
    assert all(f[0]["label"] == HOME for f in sg.build_flows(graph_site(), target_steps=5))


# ───────────────────────── captions never contain Persian / Arabic text ─────────────────────────

def test_persian_titles_are_replaced_in_the_caption():
    items = [item("https://x.com/", None),
             item("https://x.com/%D8%AF%D8%B1%D8%A8%D8%A7%D8%B1%D9%87", "https://x.com/", "درباره ما")]
    flow = sg.build_flows(items)[0]
    assert sg.crumbs(flow) == ["Home", "Page 2"]
    assert not any(sg.RTL.search(n) for n in sg.crumbs(flow))


def test_persian_title_falls_back_to_a_latin_address_segment():
    items = [item("https://x.com/", None), item("https://x.com/contact-us", "https://x.com/", "تماس با ما")]
    assert sg.crumbs(sg.build_flows(items)[0]) == ["Home", "contact us"]


def test_persian_app_screens_and_locations_are_replaced():
    items = [item("home", None), item("home > تنظیمات", "home", "تنظیمات")]
    flow = sg.build_flows(items)[0]
    assert sg.crumbs(flow) == ["Home", "Screen 2"]
    assert not sg.RTL.search(sg._location(flow[1], 1))
    assert not sg.RTL.search(sg._location(item("https://x.com/درباره", None), 1))


# ───────────────────────── watermark and writer ─────────────────────────

def test_watermark_is_drawn_bottom_right_and_can_be_turned_off():
    view = Image.new("RGB", (1440, 900), (255, 255, 255))
    on = sg.compose_frame(view, ["Home", "A"], 0, "x.com", 1.0, watermark=True)
    off = sg.compose_frame(view, ["Home", "A"], 0, "x.com", 1.0, watermark=False)
    box = (sg.W - 54 - 14, sg.H - 54 - 14, sg.W - 14, sg.H - 14)
    assert on.crop(box).tobytes() != off.crop(box).tobytes()
    assert on.crop((0, 0, 200, 200)).tobytes() == off.crop((0, 0, 200, 200)).tobytes()   # nothing elsewhere


def test_frames_are_scaled_for_smaller_live_gifs():
    view = Image.new("RGB", (1280, 800), (240, 240, 240))
    frame = sg.compose_frame(view, ["Home", "A", "B"], 1, "x.com/a", k=640 / sg.W)
    assert frame.size == (640, int(sg.H * 640 / sg.W) + int(sg.CAP * 640 / sg.W))


def test_shared_palette_writer_keeps_frames_and_durations(tmp_path):
    frames = [Image.new("RGB", (200, 120), c) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
    out = tmp_path / "x.gif"
    sg.save_frames_gif(frames, [100, 200, 300], out)
    gif = Image.open(out)
    assert gif.n_frames == 3
    gif.seek(2)
    assert gif.info["duration"] == 300
