"""Scoring-run entry point (disposable VM forked from the render checkpoint).

    python3 evaluate.py  ->  JSON on stdout: {match, mean, worst, breakpoints, lint, integrity_failures, disqualified}

Reads /work/out (render outputs + lint.json) and /work/targets ({bp}.png, optional {bp}.text.json).
Any lint violation or integrity failure sets match = 0: a cheat never outranks an honest attempt.

    python3 evaluate.py --check  ->  check mode (Phase 3): any page's capture scored against design frames, with the
                                      width sweep; no lint / integrity verdict — someone else's code is measured, not graded
"""
import json
import os
import sys
from pathlib import Path

import fluidity
import integrity
import score

OUT, TARGETS = Path(os.environ.get("PC_OUT", "/work/out")), Path(os.environ.get("PC_TARGETS", "/work/targets"))


def check():
    checks_path = OUT / "checks.json"
    if not checks_path.exists():
        json.dump({"mode": "check", "match": 0.0, "mean": 0.0, "disqualified": False, "reason": "the page could not be captured"},
                  sys.stdout)
        return
    checks = json.loads(checks_path.read_text())
    res = score.score_run(TARGETS, OUT, TARGETS if any(TARGETS.glob("*.text.json")) else None)
    res.update(mode="check", disqualified=False, between=checks.get("between", {}), fluidity=fluidity.report(checks),
               runtime_errors=checks.get("runtime_errors", [])[:10])
    json.dump(res, sys.stdout)


def main():
    lint = json.loads((OUT / "lint.json").read_text()) if (OUT / "lint.json").exists() else {"ok": False, "violations": [{"rule": "missing-lint"}]}
    checks_path = OUT / "checks.json"
    if not checks_path.exists():
        build_log = (OUT / "build.log").read_text()[:2000] if (OUT / "build.log").exists() else "no render output"
        json.dump({"match": 0.0, "mean": 0.0, "disqualified": True, "reason": "build failed", "build_log": build_log, "lint": lint}, sys.stdout)
        return
    checks = json.loads(checks_path.read_text())
    target_strings = []
    for f in TARGETS.glob("*.text.json"):
        target_strings += [x["text"] if isinstance(x, dict) else x for x in json.loads(f.read_text())]
    fails = integrity.failures(checks, OUT, target_strings)
    res = score.score_run(TARGETS, OUT, TARGETS if any(TARGETS.glob("*.text.json")) else None)
    res["raw_match"] = res["match"]
    res["lint"] = lint
    res["integrity_failures"] = fails
    res["between"] = checks.get("between", {})
    res["fluidity"] = fluidity.report(checks)   # in-between widths; not part of match, used by loop selection
    res["disqualified"] = (not lint["ok"]) or bool(fails)
    if res["disqualified"]:
        res["match"] = 0.0
        res["mean"] = 0.0
    json.dump(res, sys.stdout)


if __name__ == "__main__":
    check() if "--check" in sys.argv else main()
