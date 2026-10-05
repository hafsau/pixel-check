"""Stage 2 (docs/INTERACTIONS.md): the interaction trigger is resolved in the compiled base and marked
data-trigger="<state>" on a real <button>. Written before the implementation (TDD, Oct 2)."""
import json
import re
from pathlib import Path

import pytest

from orchestrator import fluid
from orchestrator.fluid import compile_fluid

ROOT = Path(__file__).resolve().parents[1]
SIZES = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}


def spec(frames):
    return {"breakpoints": {bp: {"size": list(SIZES[bp]), "background": "#ffffff", "texts": f.get("texts", []),
                                 "blocks": f.get("blocks", [])} for bp, f in frames.items()}}


def text(t, box, role="body", fs=16):
    return {"text": t, "box": list(box), "size_px": fs, "color": "#111111", "role": role, "weight": 400,
            "lines": 1, "measured": True}


def block(box, fill="#222222", contains=()):
    return {"box": list(box), "fill": fill, "contains_text": list(contains)}


def page_with_header(bp_list=("mobile", "tablet", "desktop")):
    frames = {}
    for bp in bp_list:
        w = SIZES[bp][0]
        frames[bp] = {"texts": [text("Brand", (20, 20, 80, 16), "heading"), text("Hello world", (20, 200, 200, 16))],
                      "blocks": [block((w - 56, 16, 40, 40), "#e50914")]}
    return spec(frames)


def element_with_marker(code, name):
    m = re.search(r'<(\w+)[^>]*data-trigger="%s"[^>]*>' % re.escape(name), code)
    return m.group(0) if m else None


def test_trigger_on_existing_block_becomes_button():
    s = page_with_header()
    code = compile_fluid(s, triggers={"menu": {"mobile": [334, 16, 40, 40]}})
    tag = element_with_marker(code, "menu")
    assert tag and tag.startswith("<button") and 'type="button"' in tag
    assert fluid.STATE["triggers"]["menu"] is not None
    assert code.count('data-trigger="menu"') == 1


def test_trigger_on_label_marks_its_control():
    s = spec({bp: {"texts": [text("Open menu", (40, 28, 90, 14), "button")],
                   "blocks": [block((24, 16, 140, 40), "#000000", ["Open menu"])]} for bp in SIZES})
    code = compile_fluid(s, triggers={"menu": {"mobile": [40, 28, 90, 14]}})
    tag = element_with_marker(code, "menu")
    assert tag and tag.startswith("<button")
    after = code[code.index(tag):]
    assert re.match(r'<button[^>]*>\s*<\w+[^>]*>Open menu<', after), "the label stays inside the marked control"


def test_trigger_without_block_wraps_the_icon_bars():
    frames = {}
    for bp in SIZES:
        w = SIZES[bp][0]
        bars = [block((w - 47, 41 + 8 * i, 24, 2), "#e7e6d9") for i in range(3)]
        for b in bars:
            b["rule"] = True
        frames[bp] = {"texts": [text("Brand", (20, 30, 80, 16), "heading")], "blocks": bars}
    s = spec(frames)
    code = compile_fluid(s, triggers={"menu": {"mobile": [335, 33, 40, 34], "tablet": [713, 33, 40, 34]}})
    tag = element_with_marker(code, "menu")
    assert tag and tag.startswith("<button")
    inner = code[code.index(tag):].split("</button>")[0]
    assert inner.count("h-[2px]") == 3, "the three bars are inside the trigger button"


def test_trigger_only_at_one_breakpoint_still_marked_once():
    s = page_with_header()
    code = compile_fluid(s, triggers={"menu": {"mobile": [334, 16, 40, 40]}})
    assert code.count('data-trigger="menu"') == 1


def test_unresolvable_trigger_reports_none_and_does_not_crash():
    s = page_with_header()
    code = compile_fluid(s, triggers={"menu": {"mobile": [5, 700, 10, 10]}})
    assert 'data-trigger="menu"' not in code
    assert fluid.STATE["triggers"]["menu"] is None


def test_duplicate_labels_highest_overlap_wins():
    s = spec({bp: {"texts": [text("More", (40, 28, 40, 14), "button"), text("More", (240, 28, 40, 14), "button")],
                   "blocks": [block((24, 16, 80, 40), "#000000", ["More"]), block((224, 16, 80, 40), "#333333", ["More"])]}
              for bp in SIZES})
    code = compile_fluid(s, triggers={"more": {"mobile": [226, 18, 76, 36]}})
    tag = element_with_marker(code, "more")
    assert tag and "bg-[#333333]" in tag


def test_no_triggers_leaves_output_unchanged():
    s = page_with_header()
    assert compile_fluid(s) == compile_fluid(s, triggers={})


def test_auto_menu_can_be_disabled():
    """Writer mode: the compiler's own deterministic menu toggle is off, Nemotron writes the behaviour."""
    frames = {}
    for bp in SIZES:
        w = SIZES[bp][0]
        links = [text(n, (300 + 80 * i, 26, 60, 14), "nav") for i, n in enumerate(["Products", "Pricing"])] if bp != "mobile" else []
        icon = [block((w - 44, 20, 24, 24), "#888888")] if bp == "mobile" else []
        frames[bp] = {"texts": [text("Brand", (20, 26, 80, 16), "heading")] + links, "blocks": icon}
    s = spec(frames)
    assert "useState" in compile_fluid(s)
    assert "useState" not in compile_fluid(s, auto_menu=False)


DEV = ROOT / "out" / "specs" / "lambda-lx.oracle.json"
META = ROOT / "benchmarks-dev" / "lambda-lx" / "meta-menu.json"


@pytest.mark.skipif(not (DEV.exists() and META.exists()), reason="dev captures not present")
@pytest.mark.parametrize("which", ["oracle", "perception"])
def test_real_lambda_hamburger(which):
    s = json.loads((ROOT / "out" / "specs" / f"lambda-lx{'.oracle' if which == 'oracle' else ''}.json").read_text())
    trig = {bp: v["box"] for bp, v in json.loads(META.read_text())["trigger"].items() if v.get("box")}
    code = compile_fluid(s, triggers={"menu": trig}, auto_menu=False)
    tag = element_with_marker(code, "menu")
    assert tag and tag.startswith("<button"), which
    assert fluid.STATE["triggers"]["menu"] is not None


STATE_PAGES = [(p.parent.name[:-3], p.stem[len("meta-"):]) for p in sorted((ROOT / "benchmarks-dev").glob("*-lx/meta-*.json"))]


@pytest.mark.skipif(not STATE_PAGES, reason="dev captures not present")
@pytest.mark.parametrize("page,state", STATE_PAGES)
@pytest.mark.parametrize("which", ["oracle", "perception"])
def test_marking_the_trigger_leaves_the_static_render_unchanged(page, state, which, tmp_path):
    """Gate A/B: 'static score unchanged' — the closed page with the trigger marked (writer mode, compiler toggle off)
    renders like the plain static compile at all three breakpoints: not one pixel changes outside the trigger's box
    (inside it the icon is redrawn as a button — council, Oct 2: ~288 px on lambda, score ±0.05). Every dev page with
    a captured state (vercel: a 44 px holder around a 24 px icon regrouped the header rows, page shifted ~25 px)."""
    import subprocess
    import numpy as np
    from PIL import Image
    sp = ROOT / "out" / "specs" / f"{page}-lx{'.oracle' if which == 'oracle' else ''}.json"
    if not sp.exists():
        pytest.skip(f"no {which} spec for {page}")
    s = json.loads(sp.read_text())
    meta = json.loads((ROOT / "benchmarks-dev" / f"{page}-lx" / f"meta-{state}.json").read_text())
    trig = {bp: v["box"] for bp, v in meta["trigger"].items() if v.get("box")}
    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps([{"name": f"{bp}.base", "bp": bp, "steps": []} for bp in SIZES]))
    outs = {}
    for k, code in {"static": compile_fluid(s, auto_menu=False),
                    "marked": compile_fluid(s, triggers={state: trig}, auto_menu=False)}.items():
        d = tmp_path / k
        d.mkdir()
        (d / "App.jsx").write_text(code)
        subprocess.run(["node", "render.mjs", "--interact", str(sc), "--in", str(d / "App.jsx"), "--out", str(d)],
                       cwd=ROOT / "sandbox", capture_output=True, timeout=180)
        outs[k] = d
    for bp in SIZES:
        a, b = (np.asarray(Image.open(outs[k] / f"{bp}.base.png").convert("RGB")).astype(int) for k in ("static", "marked"))
        assert a.shape == b.shape, bp
        changed = np.abs(a - b).sum(axis=2) > 30
        if bp in trig:
            x, y, w, h = trig[bp]
            changed[max(0, y - 2):y + h + 2, max(0, x - 2):x + w + 2] = False
        assert int(changed.sum()) == 0, (page, which, bp, int(changed.sum()))


def test_single_icon_inside_a_larger_trigger_box_is_marked_itself():
    """vercel: the capture's trigger is the 44 px button, perception sees only its 24 px icon — a synthetic 44 px holder
    regrouped the header rows (page shifted ~25 px). One block inside, no text → mark that block; layout unchanged."""
    frames = {}
    for bp in SIZES:
        w = SIZES[bp][0]
        frames[bp] = {"texts": [text("Hello world", (24, 200, 200, 16))],
                      "blocks": [block((24, 23, 21, 18), "#d4d4d8"), block((w - 48, 20, 24, 24), "#d4d4d8")]}
    s = spec(frames)
    trig = {"mobile": [332, 10, 44, 44], "tablet": [710, 10, 44, 44]}
    code = compile_fluid(s, triggers={"menu": trig}, auto_menu=False)
    tag = element_with_marker(code, "menu")
    assert tag and tag.startswith("<button") and "w-[24px]" in tag and "h-[24px]" in tag
    assert fluid.STATE["triggers"]["menu"] != "trigger:menu"
    plain = compile_fluid(s, auto_menu=False)
    strip = lambda c: re.sub(r'<button type="button" data-trigger="menu"', "<div", c).replace("</button>", "</div>")
    assert strip(code).count("\n") == plain.count("\n")                  # same structure, only the tag changed


def test_single_icon_trigger_keeps_its_look_in_a_child():
    """The open look replaces the trigger's children; when the trigger IS the icon block, its grey placeholder stayed
    under the open look (vercel). The visual (bg / border / radius / shadow) moves to a child span; the button keeps
    the layout classes (same size, same place)."""
    frames = {}
    for bp in SIZES:
        w = SIZES[bp][0]
        frames[bp] = {"texts": [text("Hello world", (24, 200, 200, 16))],
                      "blocks": [block((24, 23, 21, 18), "#d4d4d8"), block((w - 48, 20, 24, 24), "#d4d4d8")]}
    code = compile_fluid(spec(frames), triggers={"menu": {"mobile": [332, 10, 44, 44], "tablet": [710, 10, 44, 44]}},
                         auto_menu=False)
    tag = element_with_marker(code, "menu")
    assert tag and not tag.rstrip().endswith("/>") and "bg-[" not in tag and "w-[24px]" in tag and "relative" in tag
    assert "aria-hidden" not in tag                                      # a button must not hide from assistive tech
    inner = code[code.index(tag) + len(tag):].split("</button>")[0]
    assert "absolute inset-0" in inner and "bg-[#d4d4d8]" in inner


def test_single_text_trigger_is_marked_in_place():
    """A tab label / accordion question is its own trigger: one text inside the trigger box → that text element becomes
    the button (a synthetic holder around it moved the layout on shadcn / notion)."""
    frames = {bp: {"texts": [text("Overview", (40, 380, 60, 14), "nav"), text("Analytics", (128, 380, 60, 14), "nav"),
                             text("Hello world", (24, 500, 200, 16))], "blocks": []} for bp in SIZES}
    code = compile_fluid(spec(frames), triggers={"tabs1": {"mobile": [124, 376, 77, 25], "tablet": [124, 376, 77, 25]}},
                         auto_menu=False)
    tag = element_with_marker(code, "tabs1")
    assert tag and tag.startswith("<button")
    assert code[code.index(tag) + len(tag):].startswith("Analytics</button>")
    assert fluid.STATE["triggers"]["tabs1"] != "trigger:tabs1"


def test_a_block_holding_other_labels_is_not_the_triggers_holder():
    """shadcn tabs / notion toggle: the tab list (or segmented control) block contains the clicked label AND its
    siblings — marking it made the whole control one button. A holder holds only what lies in the trigger box."""
    frames = {bp: {"texts": [text("Overview", (60, 382, 60, 14), "nav"), text("Analytics", (138, 382, 60, 14), "nav"),
                             text("Reports", (212, 382, 50, 14), "nav"), text("Hello world", (24, 500, 200, 16))],
                   "blocks": [block((47, 373, 297, 32), "#f5f5f5", ["Overview", "Analytics", "Reports"])]} for bp in SIZES}
    code = compile_fluid(spec(frames), triggers={"tabs1": {"mobile": [128, 376, 77, 25]}}, auto_menu=False)
    tag = element_with_marker(code, "tabs1")
    assert tag and code[code.index(tag) + len(tag):].startswith("Analytics</button>"), tag


def test_label_with_an_icon_marks_the_label():
    """shadcn accordion: the trigger row holds the question and a chevron; a synthetic wrapper around both moved the
    desktop layout. One label inside (plus icons) → the label is the button; layout unchanged."""
    frames = {bp: {"texts": [text("What is your return policy?", (65, 453, 200, 16)), text("Hello world", (24, 600, 200, 16))],
                   "blocks": [block((305, 453, 16, 16), "#d4d4d8")]} for bp in SIZES}
    code = compile_fluid(spec(frames), triggers={"q2": {"mobile": [65, 441, 260, 42]}}, auto_menu=False)
    tag = element_with_marker(code, "q2")
    assert tag and code[code.index(tag) + len(tag):].startswith("What is your return policy?</button>"), tag
