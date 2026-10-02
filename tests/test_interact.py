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
    assert by["mobile.menu.closed"]["steps"] == [{"click": '[data-trigger="menu"]'}, {"click": '[data-trigger="menu"]'}]
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
