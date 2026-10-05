"""Scaffold regression guard on the dev pages (local captures + cached specs; skips if absent).

Compile → lint → render → integrity → score. Floors sit a few points under the Oct 1 results so a change that
breaks one page (this happened several times while tuning) fails loudly instead of silently.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sandbox"))
sys.path.insert(0, str(ROOT))
import integrity  # noqa: E402
import score  # noqa: E402
import fluidity  # noqa: E402
from orchestrator.fluid import compile_fluid  # noqa: E402
from orchestrator.scaffold import compile_scaffold  # noqa: E402

# v1 (pinned scaffold) is legacy — kept for the v1-vs-v2 ablation, not used by the loop. Oct 2: measurement now
# reports vertical column dividers, which v1's banding can't place (lambda 43 → 16); v2 handles them.
FLOORS = {"netflix-signin": 81.0, "calcom-signup": 58.0, "vercel-pricing": 60.0, "lambda": 14.0}
# scaffold v2 (fluid compiler), Oct 1: (match floor, must pass the in-between-widths fluidity checks)
FLUID_FLOORS = {"netflix-signin": (88.0, True), "calcom-signup": (80.0, True), "vercel-pricing": (67.0, True),
                "lambda": (67.0, True), "netflix-signin-lx": (89.0, True), "calcom-signup-lx": (84.0, True),
                "vercel-pricing-lx": (68.0, True), "lambda-lx": (67.0, True)}
# compiler ceiling: fluid compiler on DOM oracle specs of the Linux re-captures (tools/oracle_spec.py), Oct 1 evening
ORACLE_FLOORS = {"calcom-signup-lx": 86.0, "vercel-pricing-lx": 85.0, "lambda-lx": 80.0, "netflix-signin-lx": 80.0,
                 # Oct 5 (council): the pages the desktop-sidebar fix was tuned on + lennysjobs get floors too;
                 # (floor, fluidity must pass) — lennysjobs (textured background, known limitation) and shadcn accordion
                 # (mobile layout still weak, 24) overflow at 360–500 px: recorded as known failures, not hidden
                 "shadcn-tabs-lx": 54.0, "shadcn-accordion-lx": (22.0, False), "notion-pricing-lx": 41.0,
                 "lennysjobs-lx": (23.0, False)}


@pytest.mark.parametrize("page", sorted(FLOORS))
def test_scaffold_page(page, tmp_path):
    _check(page, tmp_path, compile_scaffold, FLOORS[page], False)


@pytest.mark.parametrize("page", sorted(FLUID_FLOORS))
def test_fluid_page(page, tmp_path):
    _check(page, tmp_path, compile_fluid, *FLUID_FLOORS[page])


@pytest.mark.parametrize("page", sorted(ORACLE_FLOORS))
def test_fluid_oracle_page(page, tmp_path):
    f = ORACLE_FLOORS[page]
    floor, fluid_pass = f if isinstance(f, tuple) else (f, True)
    _check(page, tmp_path, compile_fluid, floor, fluid_pass, oracle=True)


def _check(page, tmp_path, compiler, floor, fluid_pass, oracle=False):
    spec_p = ROOT / "out" / "specs" / f"{page}{'.oracle' if oracle else ''}.json"
    dev = ROOT / "benchmarks-dev" / page
    if not spec_p.exists() or not dev.exists():
        pytest.skip("spec/capture not present")
    (tmp_path / "App.jsx").write_text(compiler(json.loads(spec_p.read_text())))
    lint = json.loads(subprocess.run(["node", "lint.mjs", str(tmp_path / "App.jsx")], cwd=ROOT / "sandbox",
                                     capture_output=True, text=True).stdout)
    assert lint["ok"], lint
    subprocess.run(["node", "render.mjs", "--in", str(tmp_path / "App.jsx"), "--out", str(tmp_path)],
                   cwd=ROOT / "sandbox", capture_output=True, check=False)
    checks = json.loads((tmp_path / "checks.json").read_text())
    texts = {bp: json.loads((dev / f"{bp}.text.json").read_text()) for bp in score.BREAKPOINTS}
    tdir = tmp_path / "_t"; tdir.mkdir()
    for bp, t in texts.items():
        (tdir / f"{bp}.text.json").write_text(json.dumps(t))
    assert integrity.failures(checks, tmp_path, [x["text"] for v in texts.values() for x in v]) == []
    res = score.score_run(dev, tmp_path, tdir)
    assert res["match"] >= floor, {bp: v["score"] for bp, v in res["breakpoints"].items()}
    c = checks.get("controls", {})
    assert c.get("inputs_typeable", 0) == c.get("inputs", 0) and c.get("buttons_focusable", 0) == c.get("buttons", 0)
    if fluid_pass:
        assert fluidity.report(checks)["pass"], fluidity.report(checks)["fails"]


def test_duplicate_labels_match_across_breakpoints_by_style_not_order():
    """shadcn docs: desktop shows "Tabs" twice — a 14 px sidebar link (first in the list) and the 30 px page heading;
    mobile has only the heading. Matching by order tied the mobile heading to the sidebar link (the page compiled
    nearly blank, 5 / 100)."""
    from orchestrator import fluid

    def t(text, box, size, role):
        return {"text": text, "box": list(box), "size_px": size, "role": role, "color": "#000000", "weight": 600}
    spec = {"breakpoints": {
        "mobile": {"size": [390, 844], "background": "#ffffff", "blocks": [],
                   "texts": [t("Tabs", (24, 80, 70, 30), 30, "heading"), t("Installation", (24, 838, 130, 24), 24, "heading")]},
        "desktop": {"size": [1280, 800], "background": "#ffffff", "blocks": [],
                    "texts": [t("Tabs", (40, 300, 40, 14), 14, "nav"), t("Installation", (1100, 120, 80, 13), 13, "nav"),
                              t("Tabs", (420, 90, 70, 30), 30, "heading"), t("Installation", (420, 700, 130, 24), 24, "heading")]}}}
    items = fluid.prepare(spec)
    head = next(c for c in items if c.kind == "text" and c.text == "Tabs" and "mobile" in c.at)
    assert head.at["desktop"]["fs"] == 30 and fluid._box(head, "desktop")[1] < 120
    inst = next(c for c in items if c.kind == "text" and c.text == "Installation" and "mobile" in c.at)
    assert inst.at["desktop"]["fs"] == 24 and fluid._box(inst, "desktop")[1] > 600


def test_label_only_in_a_different_role_and_size_is_not_matched():
    """shadcn docs: the 24 px "Installation" heading is below desktop's fold; desktop only shows a 13 px sidebar link
    with that label — not the same element (it pulled the mobile heading into the desktop sidebar)."""
    from orchestrator import fluid

    def t(text, box, size, role):
        return {"text": text, "box": list(box), "size_px": size, "role": role, "color": "#000000", "weight": 600}
    spec = {"breakpoints": {
        "mobile": {"size": [390, 844], "background": "#ffffff", "blocks": [],
                   "texts": [t("Tabs", (24, 80, 70, 30), 30, "heading"), t("Installation", (24, 820, 130, 24), 24, "heading")]},
        "desktop": {"size": [1280, 800], "background": "#ffffff", "blocks": [],
                    "texts": [t("Installation", (35, 664, 65, 13), 13, "nav"), t("Tabs", (420, 90, 90, 48), 48, "heading")]}}}
    items = fluid.prepare(spec)
    inst = [c for c in items if c.kind == "text" and c.text == "Installation"]
    assert len(inst) == 2 and all(len(c.at) == 1 for c in inst)
    tabs = [c for c in items if c.kind == "text" and c.text == "Tabs"]
    assert len(tabs) == 1 and set(tabs[0].at) == {"mobile", "desktop"}            # 30 → 48 px heading still matches


def test_heading_not_matched_to_a_smaller_link_with_another_role():
    """shadcn accordion: tablet's 19 px "Usage" heading was tied to desktop's 13 px "on this page" link (ratio 1.46,
    heading vs link) — the column then could not be set apart and the tablet compiled to 14."""
    from orchestrator import fluid

    def t(text, box, size, role):
        return {"text": text, "box": list(box), "size_px": size, "role": role, "color": "#000000", "weight": 600}
    spec = {"breakpoints": {
        "tablet": {"size": [768, 1024], "background": "#ffffff", "blocks": [], "texts": [t("Usage", (65, 946, 57, 18), 19, "heading")]},
        "desktop": {"size": [1280, 800], "background": "#ffffff", "blocks": [], "texts": [t("Usage", (1033, 158, 38, 13), 13, "link")]}}}
    us = [c for c in fluid.prepare(spec) if c.kind == "text" and c.text == "Usage"]
    assert len(us) == 2 and all(len(c.at) == 1 for c in us)
