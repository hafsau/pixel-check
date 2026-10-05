"""Stage 5 (docs/INTERACTIONS.md): interaction harness (render.mjs --interact) + generated acceptance checks
(orchestrator/acceptance.py). Written before the implementation (TDD, Oct 2). Fixtures: a correct toggle, one
without a click handler, one without Escape-to-close."""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from orchestrator.acceptance import build_scenarios, evaluate

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "interact"


def run(app: Path, scenarios: list, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    sc = out / "scenarios.json"
    sc.write_text(json.dumps(scenarios))
    subprocess.run(["node", "render.mjs", "--interact", str(sc), "--in", str(app), "--out", str(out)],
                   cwd=ROOT / "sandbox", capture_output=True, text=True, timeout=120)
    return json.loads((out / "interact.json").read_text())


def img(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(int)


def frac_diff(a, b):
    return float((np.abs(img(a) - img(b)).sum(axis=2) > 30).mean())


SCEN = build_scenarios(["mobile"], "menu")


def test_build_scenarios_names_and_steps():
    names = {s["name"] for s in SCEN}
    assert names == {"mobile.base", "mobile.menu", "mobile.menu.closed", "mobile.menu.esc", "mobile.menu.kbd"}
    by = {s["name"]: s for s in SCEN}
    assert by["mobile.menu"]["steps"] == [{"click": '[data-trigger="menu"]'}]
    assert by["mobile.menu.closed"]["steps"] == [{"click": '[data-trigger="menu"]'}, {"click_at": '[data-trigger="menu"]'}]
    assert by["mobile.menu.esc"]["steps"][-1] == {"key": "Escape"}
    assert by["mobile.menu.kbd"]["steps"] == [{"focus": '[data-trigger="menu"]'}, {"key": "Enter"}]


@pytest.fixture(scope="module")
def good(tmp_path_factory):
    out = tmp_path_factory.mktemp("good")
    return run(FIX / "good.jsx", SCEN, out), out


def test_harness_good_toggle(good):
    res, out = good
    r = {x["name"]: x for x in res["scenarios"]}
    assert all(x["ok"] for x in res["scenarios"]), res
    assert r["mobile.menu"]["aria_expanded"] == "true" and r["mobile.menu.closed"]["aria_expanded"] == "false"
    assert r["mobile.menu.esc"]["aria_expanded"] == "false" and r["mobile.menu.kbd"]["aria_expanded"] == "true"
    assert frac_diff(out / "mobile.base.png", out / "mobile.menu.png") > 0.003   # black panel over a black page
    assert frac_diff(out / "mobile.base.png", out / "mobile.menu.closed.png") < 0.001
    for f in ("mobile.menu.png", "mobile.menu.dom.json", "mobile.menu.notext.png", "mobile.menu.coded.png"):
        assert (out / f).exists(), f


def test_harness_no_handler(tmp_path):
    res = run(FIX / "nohandler.jsx", SCEN, tmp_path)
    r = {x["name"]: x for x in res["scenarios"]}
    assert r["mobile.menu"]["aria_expanded"] == "false"
    assert frac_diff(tmp_path / "mobile.base.png", tmp_path / "mobile.menu.png") < 0.001


def test_harness_missing_trigger_reports_error(tmp_path):
    res = run(FIX / "good.jsx", build_scenarios(["mobile"], "nope"), tmp_path)
    r = {x["name"]: x for x in res["scenarios"]}
    assert not r["mobile.nope"]["ok"] and "not found" in r["mobile.nope"]["error"]
    assert r["mobile.base"]["ok"]


def targets_from(out: Path, d: Path) -> dict:
    """Use the good fixture's own renders as the design: base frame + state frame."""
    d.mkdir(parents=True, exist_ok=True)
    (d / "mobile.png").write_bytes((out / "mobile.base.png").read_bytes())
    (d / "mobile.menu.png").write_bytes((out / "mobile.menu.png").read_bytes())
    return {"base": {"mobile": d / "mobile.png"}, "states": {"mobile": d / "mobile.menu.png"}}


def test_acceptance_passes_good(good, tmp_path):
    res, out = good
    v = evaluate(out, targets_from(out, tmp_path / "t"), "menu")
    assert v["pass"], v["failures"]
    assert v["state_scores"]["mobile"] >= 95


def test_acceptance_fails_no_handler_with_clear_message(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    out = tmp_path / "r"
    run(FIX / "nohandler.jsx", SCEN, out)
    v = evaluate(out, t, "menu")
    assert not v["pass"]
    joined = " ".join(v["failures"])
    assert "mobile" in joined and "does not match the state frame" in joined and "aria-expanded" in joined


def test_acceptance_fails_only_escape_for_noescape(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    out = tmp_path / "r"
    run(FIX / "noescape.jsx", SCEN, out)
    v = evaluate(out, t, "menu")
    assert not v["pass"]
    assert len(v["failures"]) == 1 and "Escape" in v["failures"][0]


def test_acceptance_reports_runtime_errors(tmp_path):
    bad = tmp_path / "crash.jsx"
    bad.write_text((FIX / "good.jsx").read_text().replace("onClick={() => setOpen((o) => !o)}",
                                                          "onClick={() => { throw new Error('boom'); }}"))
    out = tmp_path / "r"
    res = run(bad, SCEN, out)
    assert any("boom" in e for e in res["runtime_errors"])


def test_harness_reports_panel_visibility(good):
    res, _ = good
    r = {x["name"]: x for x in res["scenarios"]}
    p = r["mobile.menu"]["panel"]
    assert p["id"] == "menu-panel" and p["exists"] and p["on_top"]


def test_harness_reports_what_covers_the_panel(tmp_path):
    res = run(FIX / "covered.jsx", SCEN, tmp_path)
    p = {x["name"]: x for x in res["scenarios"]}["mobile.menu"]["panel"]
    assert p["exists"] and not p["on_top"] and "bg-[#000000]/[0.9]" in p["covered_by"]


def test_acceptance_names_the_covering_element(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    out = tmp_path / "r"
    run(FIX / "covered.jsx", SCEN, out)
    v = evaluate(out, t, "menu")
    assert any("covered by" in f and "menu-panel" in f for f in v["failures"]), v["failures"]


def test_acceptance_flags_missing_aria_controls(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    out = tmp_path / "r"
    run(FIX / "nocontrols.jsx", SCEN, out)
    v = evaluate(out, t, "menu")
    assert any("aria-controls" in f for f in v["failures"]), v["failures"]


def test_acceptance_checks_the_trigger_open_look(good, tmp_path):
    """When the design's open trigger (e.g. an X) differs from the render, say so precisely."""
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    im = np.asarray(Image.open(t["states"]["mobile"]).convert("RGB")).copy()
    for k in range(20):                       # the design shows a dark X on the light trigger (330..370, 23..57)
        im[30 + k, 340 + k:342 + k] = 17
        im[30 + k, 358 - k:360 - k] = 17
    Image.fromarray(im).save(t["states"]["mobile"])
    t["triggers"] = {"mobile": [330, 23, 40, 34]}
    v = evaluate(gout, t, "menu")
    assert any("trigger" in f and "open" in f for f in v["failures"]), v["failures"]


def test_acceptance_trigger_check_quiet_when_matching(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    t["triggers"] = {"mobile": [330, 23, 40, 34]}
    v = evaluate(gout, t, "menu")
    assert v["pass"], v["failures"]


def test_relative_paths_work_from_the_cli(tmp_path):
    """The image build runs `node render.mjs --interact selftest/scenarios.json --in selftest/App.jsx` from /opt/pc;
    a relative --in failed to resolve ("Could not resolve selftest/App.jsx")."""
    out = tmp_path / "o"
    r = subprocess.run(["node", "render.mjs", "--interact", "selftest/scenarios.json", "--in", "selftest/App.jsx",
                        "--out", str(out)], cwd=ROOT / "sandbox", capture_output=True, text=True, timeout=120)
    res = json.loads((out / "interact.json").read_text())
    assert r.returncode == 0 and not res.get("build_failed"), res.get("build_failed")
    assert [s["name"] for s in res["scenarios"]] == ["mobile.base", "desktop.base"] and all(s["ok"] for s in res["scenarios"])


def dead_class_fixture(tmp_path: Path) -> Path:
    """good.jsx + a backdrop written bg-[#000000/0.9] (invalid arbitrary value → Tailwind emits nothing; Nemotron
    repeated it 3 attempts in a row on lambda because the failure only said "extra regions"). Valid neighbours:
    an arbitrary colour with opacity, a breakpoint-only arbitrary class (its rule sits in a media query that is not
    active at mobile), and a non-utility marker class."""
    p = tmp_path / "dead.jsx"
    p.write_text((FIX / "good.jsx").read_text().replace(
        '''<a href="#" className="block mt-[30px] text-[16px] text-white">PRICING</a>''',
        '''<a href="#" className="block mt-[30px] text-[16px] text-white md:w-[400px] group">PRICING</a>
          <div aria-hidden="true" className="fixed inset-x-0 top-[200px] h-[10px] bg-[#000000/0.9]" />
          <div aria-hidden="true" className="fixed inset-x-0 top-[220px] h-[10px] bg-[#000000]/[0.9] xl:top-[300px]" />'''))
    return p


def test_harness_reports_classes_that_generate_no_css(tmp_path):
    res = run(dead_class_fixture(tmp_path), SCEN, tmp_path / "o")
    assert res["unknown_classes"] == ["bg-[#000000/0.9]"]           # found although it exists only while open


def test_harness_reports_no_unknown_classes_for_valid_code(good):
    res, _ = good
    assert res["unknown_classes"] == []


def test_acceptance_names_classes_that_do_nothing(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    out = tmp_path / "r"
    run(dead_class_fixture(tmp_path), SCEN, out)
    v = evaluate(out, t, "menu")
    assert not v["pass"]
    f = [x for x in v["failures"] if "bg-[#000000/0.9]" in x]
    assert f and "no CSS" in f[0]


def test_why_names_the_texts_rendered_in_extra_regions():
    """Lambda v9 run 1: the mobile panel showed at tablet; 'extra [8, 168, 352, 176]' alone gave the writer nothing —
    name what is rendered there (from the capture's DOM)."""
    from orchestrator.acceptance import _why
    res = {"missing_text": [], "regions": [{"kind": "extra", "box": [8, 168, 352, 176]},
                                           {"kind": "missing", "box": [368, 352, 8, 592]}]}
    dom = [{"text": "AI FACTORIES", "box": [20, 180, 120, 16], "inked": True},
           {"text": "PRICING", "box": [20, 220, 80, 16], "inked": True},
           {"text": "Hidden", "box": [20, 260, 80, 16], "inked": False},           # not painted: not named
           {"text": "Brand", "box": [500, 30, 80, 16], "inked": True}]            # outside the region
    w = _why(res, dom)
    assert "extra [8, 168, 352, 176] shows 'AI FACTORIES', 'PRICING'" in w
    assert "Hidden" not in w and "Brand" not in w and "missing [368, 352, 8, 592]" in w
    assert _why(res) == _why(res, None) and "shows" not in _why(res)         # no DOM → boxes only, as before


def test_acceptance_says_zero_size_panel_plainly(good, tmp_path):
    import shutil
    _, gout = good
    out = tmp_path / "r"
    shutil.copytree(gout, out)
    res = json.loads((out / "interact.json").read_text())
    for s in res["scenarios"]:
        if s.get("panel"):
            s["panel"] = {"id": "menu-panel", "exists": True, "on_top": False, "covered_by": "(zero size)"}
    (out / "interact.json").write_text(json.dumps(res))
    t = targets_from(gout, tmp_path / "t")
    Image.new("RGB", Image.open(t["states"]["mobile"]).size, "white").save(t["states"]["mobile"])
    v = evaluate(out, t, "menu")
    f = [x for x in v["failures"] if "menu-panel" in x]
    assert f and "zero width or height" in f[0] and "covered by" not in f[0]


def test_harness_and_acceptance_flag_duplicate_ids(good, tmp_path):
    _, gout = good
    p = tmp_path / "dup.jsx"
    p.write_text((FIX / "good.jsx").read_text().replace(
        '''      )}
    </div>''', '''      )}
      {open && <div id="menu-panel" className="hidden md:block">copy</div>}
    </div>'''))
    out = tmp_path / "r"
    res = run(p, SCEN, out)
    assert res["duplicate_ids"] == ["menu-panel"]
    v = evaluate(out, targets_from(gout, tmp_path / "t"), "menu")
    assert any("menu-panel" in f and "unique" in f for f in v["failures"]), v["failures"]
    assert good[0]["duplicate_ids"] == []


# council review of Gate A (Oct 2): an always-open panel and a menu the trigger cannot close both passed
def always_open_fixture(tmp_path: Path) -> Path:
    p = tmp_path / "always.jsx"
    p.write_text((FIX / "good.jsx").read_text().replace("{open && (", "{true && ("))
    return p


def blocker_fixture(tmp_path: Path) -> Path:
    """Opens, then an invisible full-screen layer swallows every click: the trigger can never close it."""
    p = tmp_path / "blocker.jsx"
    p.write_text((FIX / "good.jsx").read_text().replace(
        '''      )}
    </div>''', '''      )}
      {open && <div aria-hidden="true" className="fixed inset-0 z-[100]" />}
    </div>'''))
    return p


def test_acceptance_fails_a_panel_that_is_open_before_any_click(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    t["base_expected"] = {"mobile": 100.0}             # the page without the interaction scores this on the base frame
    out = tmp_path / "r"
    run(always_open_fixture(tmp_path), SCEN, out)
    v = evaluate(out, t, "menu")
    assert not v["pass"]
    assert any("before" in f and "click" in f for f in v["failures"]), v["failures"]


def test_acceptance_base_check_quiet_for_good_code(good, tmp_path):
    res, gout = good
    t = targets_from(gout, tmp_path / "t")
    t["base_expected"] = {"mobile": 100.0}
    assert evaluate(gout, t, "menu")["pass"]


def test_acceptance_fails_when_a_scenario_errors(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    out = tmp_path / "r"
    run(blocker_fixture(tmp_path), SCEN, out)
    v = evaluate(out, t, "menu")
    assert not v["pass"]
    assert any("clicking the trigger again" in f for f in v["failures"]), v["failures"]


def test_keyboard_failure_not_repeated_when_click_already_fails(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    out = tmp_path / "r"
    run(FIX / "nohandler.jsx", SCEN, out)
    v = evaluate(out, t, "menu")
    assert not any("keyboard" in f for f in v["failures"]), v["failures"]


def test_trigger_look_not_checked_when_the_design_trigger_does_not_change(good, tmp_path):
    """netflix 'Get help': the trigger looks the same open and closed in the design; the render's static trigger
    differs a little (spacing) — that is the static page's score, not a wrong open look (false failure, Oct 2)."""
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    for p in (t["base"]["mobile"], t["states"]["mobile"]):    # same mark in both design frames
        im = np.asarray(Image.open(p).convert("RGB")).copy()
        im[35:45, 335:365] = 17
        Image.fromarray(im).save(p)
    t["triggers"] = {"mobile": [330, 23, 40, 34]}
    v = evaluate(gout, t, "menu")
    assert not any("open look" in f for f in v["failures"]), v["failures"]


def covering_drawer_fixture(tmp_path: Path) -> Path:
    """The open panel covers the trigger and has its own close button on the same spot (lennysjobs' drawer)."""
    p = tmp_path / "covering.jsx"
    p.write_text((FIX / "good.jsx").read_text().replace(
        '''<div id="menu-panel" className="fixed inset-x-0 top-[80px] bottom-0 bg-[#0b0b0b] px-[20px] pt-[40px]">''',
        '''<div id="menu-panel" className="fixed inset-0 bg-[#0b0b0b] px-[20px] pt-[120px]">
          <button type="button" aria-label="Close menu" onClick={() => setOpen(false)}
                  className="absolute left-[330px] top-[23px] w-[40px] h-[34px] bg-[#333333]" />'''))
    return p


def test_close_scenario_clicks_the_triggers_spot(tmp_path):
    """Clicking the trigger element again timed out when the drawer covers it; a user clicks the same spot (where the
    drawer's close button is)."""
    by = {s["name"]: s for s in build_scenarios(["mobile"], "menu")}
    assert by["mobile.menu.closed"]["steps"] == [{"click": '[data-trigger="menu"]'}, {"click_at": '[data-trigger="menu"]'}]
    res = run(covering_drawer_fixture(tmp_path), SCEN, tmp_path / "o")
    r = {x["name"]: x for x in res["scenarios"]}
    assert r["mobile.menu.closed"]["ok"], r["mobile.menu.closed"]
    assert r["mobile.menu.closed"]["aria_expanded"] == "false"
    assert frac_diff(tmp_path / "o" / "mobile.base.png", tmp_path / "o" / "mobile.menu.closed.png") < 0.001


def _x_img(x0, y0, size=20, bg=240, ink=20, W=390, H=120):
    im = np.full((H, W, 3), bg, np.uint8)
    for k in range(size):
        im[y0 + k, x0 + k:x0 + k + 2] = ink
        im[y0 + k, x0 + size - k - 2:x0 + size - k] = ink
    return im


def test_trigger_look_compared_where_the_render_put_the_trigger():
    """lennysjobs: the static layout put the trigger at x 190 instead of 349 — the open look is judged inside the
    render's own trigger box (aligned by centre), the misplacement already costs the static score."""
    from orchestrator.acceptance import trigger_look_failure
    design_base = np.full((120, 390, 3), 240, np.uint8)
    design_state = _x_img(355, 18)                          # X inside the design's trigger box [349, 10, 36, 36]
    render_ok = _x_img(196, 18)                             # the same X inside the render's trigger at [190, 10, 36, 36]
    render_bad = np.full((120, 390, 3), 240, np.uint8)
    render_bad[20:36, 196:216] = 20                         # a solid square instead of the X
    box_d, box_r = [349, 10, 36, 36], [190, 10, 36, 36]
    assert trigger_look_failure(design_base, design_state, render_ok, box_d, box_r) is None
    assert "open look" in trigger_look_failure(design_base, design_state, render_bad, box_d, box_r)
    assert trigger_look_failure(design_base, design_state, render_ok, box_d, None) is not None   # no render box: as before
    assert trigger_look_failure(design_state, design_state, render_bad, box_d, box_r) is None    # design unchanged


def test_harness_reports_the_triggers_rendered_box(good):
    res, _ = good
    tb = {x["name"]: x for x in res["scenarios"]}["mobile.menu"]["trigger_box"]
    assert tb == [330, 23, 40, 34]


def test_base_mismatch_names_what_is_visible(good, tmp_path):
    _, gout = good
    t = targets_from(gout, tmp_path / "t")
    t["base_expected"] = {"mobile": 100.0}
    p = tmp_path / "stray.jsx"
    p.write_text((FIX / "good.jsx").read_text().replace("<p className=\"px-[20px] mt-[100px]",
                                                         "<p className=\"px-[20px] mt-[20px] text-[40px] text-white\">(empty)</p>\n      <p className=\"px-[20px] mt-[100px]"))
    out = tmp_path / "r"
    run(p, SCEN, out)
    v = evaluate(out, t, "menu")
    f = [x for x in v["failures"] if "before any click" in x]
    assert f and "(empty)" in f[0], v["failures"]


def test_harness_reports_selection_aria(tmp_path):
    """Swap groups (tabs / toggles) report selection via aria-selected / aria-pressed, not aria-expanded."""
    p = tmp_path / "tabs.jsx"
    p.write_text('''import { useState } from "react";

export default function App() {
  const [sel, setSel] = useState(0);
  return (
    <div className="min-h-screen bg-white p-[20px]">
      <button type="button" data-trigger="tabs0" role="tab" aria-selected={sel === 0} onClick={() => setSel(0)}>One</button>
      <button type="button" data-trigger="tabs1" role="tab" aria-selected={sel === 1} onClick={() => setSel(1)}>Two</button>
      <p>{["First", "Second"][sel]}</p>
    </div>
  );
}
''')
    res = run(p, [{"name": "mobile.tabs1", "bp": "mobile", "steps": [{"click": '[data-trigger="tabs1"]'}]}], tmp_path / "o")
    r = res["scenarios"][0]
    assert r["aria_selected"] == "true" and r["aria_pressed"] is None


def test_compiled_tabs_behave_in_the_browser(tmp_path):
    """Selected look and keyboard, rendered: clicking Analytics moves the white pill to it; from the focused first tab,
    ArrowRight selects the second (the `check` step reports that element's aria)."""
    from orchestrator.groups import compile_swap
    from test_groups import PILL_PAGE, PILL_PLAN
    p = tmp_path / "tabs.jsx"
    p.write_text(compile_swap(PILL_PAGE, PILL_PLAN, "tabs"))
    res = run(p, [{"name": "mobile.base", "bp": "mobile", "steps": []},
                  {"name": "mobile.tabs1", "bp": "mobile", "steps": [{"click": '[data-trigger="tabs1"]'}]},
                  {"name": "mobile.kbd", "bp": "mobile", "steps": [{"focus": '[data-trigger="tabs0"]'}, {"key": "ArrowRight"},
                                                                   {"check": '[data-trigger="tabs1"]'}]}], tmp_path / "o")
    r = {x["name"]: x for x in res["scenarios"]}
    assert r["mobile.tabs1"]["aria_selected"] == "true" and r["mobile.kbd"]["aria_selected"] == "true", r
    base, sel = img(tmp_path / "o" / "mobile.base.png"), img(tmp_path / "o" / "mobile.tabs1.png")
    white = lambda im: (im.sum(axis=2) > 740)
    assert white(base).sum() > 300 and white(sel).sum() > 100
    xs_base, xs_sel = np.nonzero(white(base))[1], np.nonzero(white(sel))[1]
    assert xs_sel.mean() > xs_base.mean() + 20                                # the pill moved right, to Analytics
