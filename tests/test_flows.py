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
