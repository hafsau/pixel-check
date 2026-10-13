"""Audits without designs (Oct 13, Hafsa's own apps — no design frames): a URL is captured as it looks and measured on
its own — width breaks (360–1600 px), warnings (platform badges over content, screenshot builds, exact-width media
queries) and text that vanishes on smaller screens. No match score: there is no design to compare with. Written
before the code (TDD)."""
import json
import os
import subprocess
import sys
from pathlib import Path

from orchestrator import check as C
from test_check import FakeSB

ROOT = Path(__file__).resolve().parents[1]


def dom(texts, inked=True):
    return [{"text": t, "inked": inked, "onscreen": True, "box": [0, 0, 10, 10]} for t in texts]


def test_the_sandbox_audit_reports_breaks_warnings_and_what_vanishes_on_phones(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    sizes = {"mobile": [390, 844], "tablet": [768, 1024], "desktop": [1280, 800]}
    checks = {"sizes": sizes, "breakpoints": {bp: {"width": w, "height": h, "overflow_px": 0, "text_overlaps": 0}
                                              for bp, (w, h) in sizes.items()},
              "between": {"1024": {"overflow_px": 0, "text_overlaps": 1}}, "runtime_errors": [],
              "warnings": ['mobile: the Replit badge covers "Generate Questions" (a platform badge, not your layout)']}
    (out / "checks.json").write_text(json.dumps(checks))
    (out / "mobile.dom.json").write_text(json.dumps(dom(["Interview Question Generator", "Generate Questions"])))
    common = ["Interview Question Generator", "Generate Questions", "Interview Sage", "Question Bank",
              "Include the job title and level"]
    (out / "tablet.dom.json").write_text(json.dumps(dom(common)))
    (out / "desktop.dom.json").write_text(json.dumps(dom(common + ["Dashboard"])))
    r = subprocess.run([sys.executable, "evaluate.py", "--audit"], cwd=ROOT / "sandbox", capture_output=True, text=True,
                       env={**os.environ, "PC_OUT": str(out)}, timeout=60)
    rep = json.loads(r.stdout)
    assert rep["mode"] == "audit" and "match" not in rep
    assert rep["fluidity"]["fails"] == [1024]
    # visible on a larger size, not on this one
    assert rep["vanished"]["mobile"] == ["Dashboard", "Include the job title and level", "Interview Sage", "Question Bank"]
    assert rep["vanished"]["tablet"] == ["Dashboard"]
    assert any("Replit badge" in w for w in rep["warnings"])


def test_audit_url_captures_then_audits_in_a_disposable_run_without_any_design():
    sb = FakeSB(score={"mode": "audit", "fluidity": {"pass": True}, "vanished": {"mobile": []}})
    out = C.audit_url("https://app.example/", sb=sb, verify=lambda m: None, emit=lambda *a, **k: None)
    (cap_cmd, cap), (aud_cmd, aud) = sb.runs
    assert "check_page.mjs" in cap_cmd and cap["networking"] is True and "--block-private" in cap_cmd
    assert "evaluate.py --audit" in aud_cmd and aud["disposable"] is True and not aud.get("networking")
    assert not any(k.startswith("/work/targets") for k in aud.get("files") or {})
    assert out["report"]["mode"] == "audit" and out["build"]["mobile"] == b"m"
