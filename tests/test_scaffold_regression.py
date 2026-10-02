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
ORACLE_FLOORS = {"calcom-signup-lx": 86.0, "vercel-pricing-lx": 85.0, "lambda-lx": 80.0, "netflix-signin-lx": 80.0}


@pytest.mark.parametrize("page", sorted(FLOORS))
def test_scaffold_page(page, tmp_path):
    _check(page, tmp_path, compile_scaffold, FLOORS[page], False)


@pytest.mark.parametrize("page", sorted(FLUID_FLOORS))
def test_fluid_page(page, tmp_path):
    _check(page, tmp_path, compile_fluid, *FLUID_FLOORS[page])


@pytest.mark.parametrize("page", sorted(ORACLE_FLOORS))
def test_fluid_oracle_page(page, tmp_path):
    _check(page, tmp_path, compile_fluid, ORACLE_FLOORS[page], True, oracle=True)


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
