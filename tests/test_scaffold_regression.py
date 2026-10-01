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
from orchestrator.scaffold import compile_scaffold  # noqa: E402

FLOORS = {"netflix-signin": 78.0, "calcom-signup": 48.0, "vercel-pricing": 50.0}


@pytest.mark.parametrize("page", sorted(FLOORS))
def test_scaffold_page(page, tmp_path):
    spec_p, dev = ROOT / "out" / "specs" / f"{page}.json", ROOT / "benchmarks-dev" / page
    if not spec_p.exists() or not dev.exists():
        pytest.skip("spec/capture not present")
    (tmp_path / "App.jsx").write_text(compile_scaffold(json.loads(spec_p.read_text())))
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
    assert res["match"] >= FLOORS[page], {bp: v["score"] for bp, v in res["breakpoints"].items()}
    c = checks.get("controls", {})
    assert c.get("inputs_typeable", 0) == c.get("inputs", 0) and c.get("buttons_focusable", 0) == c.get("buttons", 0)
