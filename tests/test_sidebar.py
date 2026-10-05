"""Desktop-only side columns (docs sidebars): items only the desktop frame has, in a tall strip beside the main
content, must not reshape the other breakpoints (shadcn docs compiled to 2–17 on mobile because the sidebar's 50
links drove the band structure). They compile as one desktop-only aside at its design position.
Written before the implementation (TDD, Oct 4)."""
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from orchestrator.fluid import compile_fluid

ROOT = Path(__file__).resolve().parents[1]
SIZES = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}


def t(text, box, size=16, role="body", weight=400):
    return {"text": text, "box": list(box), "size_px": size, "role": role, "color": "#111111", "weight": weight,
            "lines": 1, "measured": True}


def page(with_sidebar: bool):
    bps = {}
    for bp, (w, h) in SIZES.items():
        x = 320 if bp == "desktop" else 24
        cw = (w - x - 40) if bp != "desktop" else 640
        texts = [t("Tabs", (x, 90, 80, 30), 30, "heading", 700), t("A set of layered sections of content.", (x, 140, min(cw, 400), 20)),
                 t("Overview", (x + 30, 260, 70, 14), 14, "nav", 500), t("Analytics", (x + 120, 260, 70, 14), 14, "nav", 500),
                 t("View your key metrics.", (x + 30, 320, 240, 16), 14)]
        blocks = [{"box": [x, 230, cw, 160], "fill": "#ffffff", "border": {"color": "#e5e5e5", "sides": "trbl"},
                   "contains_text": ["Overview", "Analytics", "View your key metrics."]}]
        if bp != "desktop":      # below desktop's fold: only the smaller frames show the next heading
            texts += [t("Installation", (24, h - 60, 130, 24), 24, "heading", 600)]
        if with_sidebar and bp == "desktop":
            texts += [t(f"Component {i}", (35, 110 + 40 * i, 110, 14), 14, "nav") for i in range(16)]
            texts += [t(s_, (1100, 120 + 28 * i, 120, 13), 13, "nav") for i, s_ in   # an "On this page" column
                      enumerate(["On This Page", "Installation", "Usage", "Composition", "Disabled", "API Reference"])]
        bps[bp] = {"size": [w, h], "background": "#ffffff", "texts": texts, "blocks": blocks}
    return {"breakpoints": bps}


def render(code: str, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    (out / "App.jsx").write_text(code)
    sc = out / "sc.json"
    sc.write_text(json.dumps([{"name": f"{bp}.base", "bp": bp, "steps": []} for bp in SIZES]))
    subprocess.run(["node", "render.mjs", "--interact", str(sc), "--in", str(out / "App.jsx"), "--out", str(out)],
                   cwd=ROOT / "sandbox", capture_output=True, timeout=180)
    return out


def png(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def test_desktop_sidebar_does_not_change_mobile_or_tablet(tmp_path):
    a = render(compile_fluid(page(False), auto_menu=False), tmp_path / "plain")
    b = render(compile_fluid(page(True), auto_menu=False), tmp_path / "side")
    for bp in ("mobile", "tablet"):
        diff = (np.abs(png(a / f"{bp}.base.png") - png(b / f"{bp}.base.png")).sum(axis=2) > 30).sum()
        assert diff == 0, (bp, int(diff))


def test_desktop_sidebar_drawn_at_its_design_position(tmp_path):
    out = render(compile_fluid(page(True), auto_menu=False), tmp_path / "side")
    dom = {e["text"]: e["box"] for e in json.loads((out / "desktop.base.dom.json").read_text()) if e.get("text")}
    for i in (0, 7, 15):
        x, y = dom[f"Component {i}"][:2]
        assert abs(x - 35) <= 4 and abs(y - (110 + 40 * i)) <= 4, (i, dom[f"Component {i}"])
    x, y = dom["Tabs"][:2]
    assert abs(x - 320) <= 4 and abs(y - 90) <= 6, dom["Tabs"]
    assert abs(dom["API Reference"][0] - 1100) <= 4 and abs(dom["API Reference"][1] - 260) <= 4, dom["API Reference"]


REAL = [p for p in ("shadcn-tabs", "shadcn-accordion") if (ROOT / "out" / "specs" / f"{p}-lx.oracle.json").exists()]


import pytest  # noqa: E402


@pytest.mark.skipif(not REAL, reason="dev captures not present")
@pytest.mark.parametrize("pg", REAL)
def test_real_docs_page_desktop_frame_does_not_wreck_mobile_and_tablet(pg, tmp_path):
    """shadcn docs (oracle spec): mobile / tablet scored 17 / 26 with the desktop frame, 72 / 81 without it — the
    desktop sidebar and "on this page" columns drove the bands. The desktop frame may cost at most 5 points there."""
    import copy
    from orchestrator.acceptance import _score_full
    spec = json.loads((ROOT / "out" / "specs" / f"{pg}-lx.oracle.json").read_text())
    two = copy.deepcopy(spec)
    two["breakpoints"].pop("desktop")
    D = ROOT / "benchmarks-dev" / f"{pg}-lx"
    a = render(compile_fluid(two, auto_menu=False), tmp_path / "two")
    b = render(compile_fluid(spec, auto_menu=False), tmp_path / "three")
    for bp in ("mobile", "tablet"):
        sa = _score_full(D / f"{bp}.png", a, f"{bp}.base", D / f"{bp}.text.json")["score"]
        sb = _score_full(D / f"{bp}.png", b, f"{bp}.base", D / f"{bp}.text.json")["score"]
        assert sb >= sa - 5, (pg, bp, round(sa, 1), round(sb, 1))


def test_row_order_compares_positions_in_one_frame():
    """shadcn tabs: the row "Tabs [icon][icon]" (mobile) / "Tabs … Copy Page" (desktop) put the mobile-only icons
    (x 294 on a 390 frame) before the heading (x 320 on desktop): items were sorted by x in different frames. The
    heading rendered at x 259 on mobile instead of 24."""
    spec = {"breakpoints": {
        "mobile": {"size": [390, 844], "background": "#ffffff", "texts": [t("Tabs", (24, 87, 68, 23), 30, "heading", 700),
                                                                          t("Body", (24, 300, 200, 16))],
                   "blocks": [{"box": [294, 82, 32, 32], "fill": "#f5f5f5"}, {"box": [334, 82, 32, 32], "fill": "#f5f5f5"}]},
        "desktop": {"size": [1280, 800], "background": "#ffffff", "texts": [t("Tabs", (320, 119, 68, 23), 30, "heading", 700),
                                                                            t("Copy Page", (784, 120, 66, 13), 13),
                                                                            t("Body", (320, 300, 400, 16))], "blocks": []}}}
    code = compile_fluid(spec, auto_menu=False)
    assert code.index(">Tabs</") < code.index("w-[32px]"), "the heading comes first in its row"
