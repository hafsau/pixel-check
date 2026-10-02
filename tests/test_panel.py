"""Stage 3 (docs/INTERACTIONS.md): the content an interaction reveals is compiled deterministically into a JSX
panel component, laid out relative to the panel's top. Written before the implementation (TDD, Oct 2)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator.panel import compile_panel

ROOT = Path(__file__).resolve().parents[1]
SIZES = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}


def frame(bp, texts=(), blocks=()):
    return {"size": list(SIZES[bp]), "background": "#0b0b0b",
            "texts": [{"text": t, "box": list(b), "size_px": 16, "color": "#ffffff", "role": "nav", "weight": 500,
                       "lines": 1, "measured": True} for t, b in texts],
            "blocks": [{"box": list(b), "fill": f, "contains_text": []} for b, f in blocks]}


def base_spec():
    return {"breakpoints": {bp: frame(bp, [("Brand", (20, 30, 80, 16)), ("Hero title", (20, 300, 300, 40))])
                            for bp in SIZES}}


def menu_state(bp):
    links = [(n, (21, 140 + 46 * i, 120, 14)) for i, n in enumerate(["AI FACTORIES", "PRODUCTS", "PRICING", "COMPANY"])]
    rules = [((15, 168 + 46 * i, 360, 1), "#262625") for i in range(4)]
    return frame(bp, [("Brand", (20, 30, 80, 16))] + links, [((0, 100, SIZES[bp][0], SIZES[bp][1] - 100), "#0b0b0b")] + rules)


def lint(component: str) -> dict:
    app = component + "\nexport default function App() {\n  return (\n    <div>\n      <Panel />\n    </div>\n  );\n}\n"
    p = ROOT / "out" / "tmp_panel_test.jsx"
    p.parent.mkdir(exist_ok=True)
    p.write_text(app)
    out = subprocess.run(["node", "lint.mjs", str(p)], cwd=ROOT / "sandbox", capture_output=True, text=True).stdout
    return json.loads(out)


def test_panel_contains_every_appeared_text_and_nothing_persisted():
    res = compile_panel(base_spec(), {"mobile": menu_state("mobile")}, name="Panel")
    for t in ["AI FACTORIES", "PRODUCTS", "PRICING", "COMPANY"]:
        assert f">{t}<" in res["jsx"]
    assert ">Brand<" not in res["jsx"], "persisted header stays in the page, not in the panel"
    assert res["kind"] == "overlay"


def test_panel_is_a_component_that_lints():
    res = compile_panel(base_spec(), {"mobile": menu_state("mobile")}, name="Panel")
    assert res["jsx"].lstrip().startswith("function Panel(")
    r = lint(res["jsx"])
    assert r["ok"], r


def test_layout_is_relative_to_the_panel_top():
    res = compile_panel(base_spec(), {"mobile": menu_state("mobile")}, name="Panel")
    assert res["panel"]["mobile"][1] == 100
    tops = [int(v) for v in re.findall(r"(?<![\w-])mt-\[(\d+)px\]", res["jsx"])]
    assert tops and max(tops) < 100, "no page-coordinate offsets (the first link sits ~40 px below the panel top)"


def test_states_at_two_breakpoints():
    res = compile_panel(base_spec(), {"mobile": menu_state("mobile"), "tablet": menu_state("tablet")}, name="Panel")
    assert set(res["panel"]) == {"mobile", "tablet"}
    assert lint(res["jsx"])["ok"]


def test_no_change_gives_no_panel():
    b = base_spec()
    res = compile_panel(b, {"mobile": b["breakpoints"]["mobile"]}, name="Panel")
    assert res["jsx"] is None and res["kind"] == "none"


def test_drawer_kind():
    st = frame("mobile", [("Brand", (20, 30, 80, 16)), ("Hero title", (20, 300, 300, 40))] +
               [(f"Link {i}", (160, 40 + 32 * i, 120, 16)) for i in range(6)], [((140, 0, 250, 844), "#ffffff")])
    res = compile_panel(base_spec(), {"mobile": st}, name="Panel")
    assert res["kind"] == "drawer"
    assert ">Link 0<" in res["jsx"] and ">Hero title<" not in res["jsx"]


DEV = ROOT / "benchmarks-dev" / "lambda-lx"


@pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_real_lambda_menu_panel():
    sys.path.insert(0, str(ROOT / "tools"))
    from oracle_spec import frame as oracle_frame
    base = json.loads((ROOT / "out" / "specs" / "lambda-lx.oracle.json").read_text())
    states = {bp: oracle_frame("lambda-lx", bp, state="menu") for bp in ("mobile", "tablet")}
    res = compile_panel(base, states, name="MenuPanel")
    for t in ["AI FACTORIES", "PRODUCTS", "PRICING", "COMPANY", "LOG IN", "GET STARTED"]:
        assert f">{t}<" in res["jsx"], t
    assert res["kind"] == "overlay"
    r = lint(res["jsx"].replace("function MenuPanel(", "function Panel("))
    assert r["ok"], r


@pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_real_lambda_panel_starts_below_header_with_trigger():
    sys.path.insert(0, str(ROOT / "tools"))
    from oracle_spec import frame as oracle_frame
    base = json.loads((ROOT / "out" / "specs" / "lambda-lx.oracle.json").read_text())
    states = {bp: oracle_frame("lambda-lx", bp, state="menu") for bp in ("mobile", "tablet")}
    trig = {bp: v["box"] for bp, v in json.loads((DEV / "meta-menu.json").read_text())["trigger"].items()}
    res = compile_panel(base, states, name="MenuPanel", triggers=trig)
    assert res["panel"]["mobile"][1] >= 95, res["panel"]
    assert "trigger_changes" in res and res["trigger_changes"]["mobile"]["appeared"]["blocks"]


@pytest.mark.skipif(not (DEV / "tablet.menu.png").exists(), reason="dev state capture not present")
def test_panel_reports_backdrop_per_breakpoint():
    sys.path.insert(0, str(ROOT / "tools"))
    from oracle_spec import frame as oracle_frame
    base = json.loads((ROOT / "out" / "specs" / "lambda-lx.oracle.json").read_text())
    meta = json.loads((DEV / "meta-menu.json").read_text())
    trig = {bp: v["box"] for bp, v in meta["trigger"].items()}
    states = {bp: oracle_frame("lambda-lx", bp, state="menu") for bp in trig}
    images = {bp: (DEV / f"{bp}.png", DEV / f"{bp}.menu.png") for bp in trig}
    res = compile_panel(base, states, name="MenuPanel", triggers=trig, images=images)
    assert res["backdrop"]["mobile"] is None, "full-screen overlay: nothing to dim"
    b = res["backdrop"]["tablet"]
    assert b and abs(b["opacity"] - 0.9) < 0.05 and 95 <= b["box"][1] <= 110


def test_panel_without_images_has_no_backdrop_key_values():
    res = compile_panel(base_spec(), {"mobile": menu_state("mobile")}, name="Panel")
    assert res["backdrop"] == {"mobile": None}


def test_dimmed_base_content_is_not_panel_content(tmp_path):
    """Perception of a drawer state reads the dimmed page behind it as new, differently coloured items; they must not
    become panel content (lambda tablet: the panel box swallowed the whole page and the kind became overlay)."""
    import numpy as np
    from PIL import Image
    W, H = SIZES["tablet"]
    base_img = np.full((H, W, 3), 11, np.uint8)
    rng = np.random.default_rng(1)                         # a headline with varied ink (like real glyphs)
    base_img[200:260, 20:700] = rng.integers(120, 255, size=(60, 680, 3))
    state_img = (base_img * 0.1).astype(np.uint8)          # dimmed 90 %
    state_img[0:100] = base_img[0:100]                     # header not dimmed
    state_img[100:, 368:] = 11                             # the drawer
    d = tmp_path
    Image.fromarray(base_img).save(d / "b.png")
    Image.fromarray(state_img).save(d / "s.png")
    base = {"breakpoints": {"tablet": frame("tablet", [("Brand", (20, 30, 80, 16)), ("Headline text", (20, 210, 600, 40))])}}
    st = frame("tablet", [("Brand", (20, 30, 80, 16)), ("Headline tex", (21, 211, 590, 38))] +
               [(n, (389, 133 + 46 * i, 97, 17)) for i, n in enumerate(["AI FACTORIES", "PRODUCTS", "PRICING"])],
               [((390, 162 + 46 * i, 360, 1), "#262625") for i in range(3)])
    res = compile_panel(base, {"tablet": st}, name="Panel", images={"tablet": (d / "b.png", d / "s.png")})
    assert res["kind"] == "drawer", res["panel"]
    assert res["panel"]["tablet"][0] >= 368 and ">Headline tex<" not in res["jsx"]
    assert res["backdrop"]["tablet"] and abs(res["backdrop"]["tablet"]["opacity"] - 0.9) < 0.05


PSPEC = ROOT / "out" / "specs" / "lambda-lx.menu.json"


@pytest.mark.skipif(not PSPEC.exists(), reason="perceived state spec not present")
def test_real_lambda_perceived_tablet_is_a_drawer():
    base = json.loads((ROOT / "out" / "specs" / "lambda-lx.json").read_text())
    states = json.loads(PSPEC.read_text())["breakpoints"]
    trig = {bp: v["box"] for bp, v in json.loads((DEV / "meta-menu.json").read_text())["trigger"].items()}
    res = compile_panel(base, states, name="MenuPanel", triggers=trig,
                        images={bp: (DEV / f"{bp}.png", DEV / f"{bp}.menu.png") for bp in trig})
    assert res["diff"]["tablet"]["kind"] == "drawer" and res["panel"]["tablet"][0] >= 300, res["panel"]
    assert res["diff"]["mobile"]["kind"] == "overlay"


def test_same_kind_and_content_compiles_one_shared_panel():
    res = compile_panel(base_spec(), {"mobile": menu_state("mobile"), "tablet": menu_state("tablet")}, name="Panel")
    assert res["components"] == {"mobile": "Panel", "tablet": "Panel"}
    assert res["jsx"].count("function ") == 1


def test_different_kinds_compile_one_panel_per_breakpoint():
    st_t = frame("tablet", [("Brand", (20, 30, 80, 16)), ("Hero title", (20, 300, 300, 40))] +
                 [(n, (389, 133 + 46 * i, 97, 17)) for i, n in enumerate(["AI FACTORIES", "PRODUCTS", "PRICING", "COMPANY"])],
                 [((368, 100, 400, 924), "#111111")])
    res = compile_panel(base_spec(), {"mobile": menu_state("mobile"), "tablet": st_t}, name="MenuPanel")
    assert res["components"] == {"mobile": "MenuPanel", "tablet": "MenuPanel"}
    assert "function MenuPanelMobile(" in res["jsx"] and "function MenuPanelTablet(" in res["jsx"]
    # the wrapper shows each breakpoint's panel only at its breakpoint (the writer mounts one component)
    wrap = res["jsx"].split("function MenuPanel(")[1]
    assert '<div className="md:hidden"><MenuPanelMobile /></div>' in wrap
    assert '<div className="hidden md:block xl:hidden"><MenuPanelTablet /></div>' in wrap
    assert lint(res["jsx"].replace("MenuPanelMobile(", "Panel(").replace("<MenuPanelMobile", "<Panel"))["ok"]
    # each component only lays out its own breakpoint: no md:/xl: classes in the mobile one
    mob = res["jsx"].split("function MenuPanelTablet(")[0]
    assert "md:" not in mob


@pytest.mark.skipif(not PSPEC.exists(), reason="perceived state spec not present")
def test_real_lambda_panels_split_overlay_and_drawer():
    base = json.loads((ROOT / "out" / "specs" / "lambda-lx.json").read_text())
    states = json.loads(PSPEC.read_text())["breakpoints"]
    trig = {bp: v["box"] for bp, v in json.loads((DEV / "meta-menu.json").read_text())["trigger"].items()}
    res = compile_panel(base, states, name="MenuPanel", triggers=trig,
                        images={bp: (DEV / f"{bp}.png", DEV / f"{bp}.menu.png") for bp in trig})
    assert "function MenuPanelMobile(" in res["jsx"] and "function MenuPanelTablet(" in res["jsx"]


def test_overlay_panel_spans_the_viewport_width():
    """Perception gives an overlay's CONTENT extent (x 21..370); the overlay itself spans the viewport, and its
    content keeps its real gutters (laid out at 349 px wide it was squeezed: dividers short, '+' icons shifted)."""
    st = menu_state("mobile")
    st["blocks"] = [b for b in st["blocks"] if b["box"][2] < 390]       # no full-width background block measured
    res = compile_panel(base_spec(), {"mobile": st}, name="Panel")
    assert res["kind"] == "overlay"
    p = res["panel"]["mobile"]
    assert p[0] == 0 and p[2] == 390
    assert re.search(r"(?<![\w-])(pl|ml)-\[2[01]px\]", res["jsx"]), "content keeps its ~21 px gutter (ink box starts 1 px in)"


def test_per_breakpoint_panel_uses_the_closest_frame_width():
    st_t = frame("tablet", [("Brand", (20, 30, 80, 16)), ("Hero title", (20, 300, 300, 40))] +
                 [(n, (40, 140 + 46 * i, 120, 16)) for i, n in enumerate(["AI FACTORIES", "PRODUCTS", "PRICING", "COMPANY"])],
                 [((0, 100, 768, 924), "#111111")])
    st_m = frame("mobile", [("Brand", (20, 30, 80, 16)), ("Hero title", (20, 300, 300, 40))] +
                 [(f"Link {i}", (160, 40 + 32 * i, 120, 16)) for i in range(6)], [((140, 0, 250, 844), "#ffffff")])
    res = compile_panel(base_spec(), {"mobile": st_m, "tablet": st_t}, name="P")
    assert res["components"] == {"mobile": "P", "tablet": "P"} and "function PTablet(" in res["jsx"]
    assert res["panel"]["tablet"][2] == 768


def test_panel_components_accept_a_classname():
    """The writer mounted <MenuPanelMobile className="block md:hidden" /> — components that ignore props then rendered
    at every breakpoint. Components take className onto their root."""
    st_t = frame("tablet", [("Brand", (20, 30, 80, 16)), ("Hero title", (20, 300, 300, 40))] +
                 [(n, (389, 133 + 46 * i, 97, 17)) for i, n in enumerate(["AI FACTORIES", "PRODUCTS"])],
                 [((368, 100, 400, 924), "#111111")])
    res = compile_panel(base_spec(), {"mobile": menu_state("mobile"), "tablet": st_t}, name="MenuPanel")
    for n in ("MenuPanel", "MenuPanelMobile", "MenuPanelTablet"):
        assert f"function {n}({{ className = \"\" }})" in res["jsx"]
    assert 'className={`w-full ${className}`}' in res["jsx"]


def test_trigger_open_look_compiled_as_a_component():
    from orchestrator.panel import compile_trigger_look
    jsx = compile_trigger_look({"box": [11, 7, 18, 20], "fill": "#e7e6d9", "shape": "x"}, "MenuTriggerOpen")
    assert jsx.startswith("function MenuTriggerOpen()")
    assert jsx.count("absolute") >= 2 and "rotate-45" in jsx and "-rotate-45" in jsx and "bg-[#e7e6d9]" in jsx
    assert "left-[11px]" in jsx and "top-[7px]" in jsx and "w-[18px]" in jsx and "h-[20px]" in jsx
    r = lint(jsx.replace("MenuTriggerOpen(", "Panel("))
    assert r["ok"], r


def test_unknown_trigger_look_has_no_component():
    from orchestrator.panel import compile_trigger_look
    assert compile_trigger_look({"box": [1, 1, 5, 5], "fill": "#fff", "shape": "unknown"}, "X") is None
    assert compile_trigger_look(None, "X") is None
