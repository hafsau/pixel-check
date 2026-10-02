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


@pytest.mark.skipif(not (DEV.exists() and META.exists()), reason="dev captures not present")
@pytest.mark.parametrize("which", ["oracle", "perception"])
def test_marking_the_trigger_leaves_the_static_render_unchanged(which, tmp_path):
    """Gate A: 'static score unchanged' — the closed page with the trigger marked (writer mode, compiler toggle off)
    renders like the plain static compile at all three breakpoints."""
    import subprocess
    import numpy as np
    from PIL import Image
    s = json.loads((ROOT / "out" / "specs" / f"lambda-lx{'.oracle' if which == 'oracle' else ''}.json").read_text())
    trig = {bp: v["box"] for bp, v in json.loads(META.read_text())["trigger"].items() if v.get("box")}
    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps([{"name": f"{bp}.base", "bp": bp, "steps": []} for bp in SIZES]))
    outs = {}
    for k, code in {"static": compile_fluid(s), "marked": compile_fluid(s, triggers={"menu": trig}, auto_menu=False)}.items():
        d = tmp_path / k
        d.mkdir()
        (d / "App.jsx").write_text(code)
        subprocess.run(["node", "render.mjs", "--interact", str(sc), "--in", str(d / "App.jsx"), "--out", str(d)],
                       cwd=ROOT / "sandbox", capture_output=True, timeout=180)
        outs[k] = d
    for bp in SIZES:
        a, b = (np.asarray(Image.open(outs[k] / f"{bp}.base.png").convert("RGB")).astype(int) for k in ("static", "marked"))
        assert a.shape == b.shape, bp
        changed = float((np.abs(a - b).sum(axis=2) > 30).mean())
        assert changed < 0.002, (which, bp, changed)
