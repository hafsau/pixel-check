"""Rebuild the UI's replay set (ui/public/runs/) from the current pipeline outputs in out/. No model or sandbox calls.

    .venv/bin/python tools/export_demo.py

Static runs: step-D ablation runs (out/ablation/runs/, sandbox, perception path, -lx pages) — the default pipeline
"compiler + plan" for 4 pages, plus one run with 2 loop rounds. Interactions: the Gate B sandbox runs
(out/interact/<page>/<state>/perception-sandbox[-template]) with the ablation repeats. Sibling states: the Gate B'
sandbox runs (out/group/shadcn-tabs/*-sandbox).

All of these use third-party DEV captures (benchmarks-dev/): local replay only, never committed or deployed — the
production build strips ui/public/runs unless PC_INCLUDE_RUNS=1 (ui/vite.config.ts). index.json is rebuilt from
scratch, so bundles from older exports stay on disk but are no longer listed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_group  # noqa: E402
import export_interaction  # noqa: E402
import export_run  # noqa: E402
from export_common import ROOT, RUNS  # noqa: E402

ABL = ROOT / "out" / "ablation" / "runs"
BD = ROOT / "benchmarks-dev"

STATIC = [  # (run, page, title, label)
    ("abl-plan-netflix-signin-203135", "netflix-signin", "Sign-in page", "compiler + plan"),
    ("abl-plan-calcom-signup-203136", "calcom-signup", "Sign-up page", "compiler + plan"),
    ("abl-plan-vercel-pricing-203137", "vercel-pricing", "Pricing page", "compiler + plan"),
    ("abl-plan-lambda-203138", "lambda", "Cloud landing page", "compiler + plan"),
    ("abl-loop-calcom-signup-203151", "calcom-signup", "Sign-up page", "compiler + plan + 2 loop rounds"),
]
INTERACTIONS = [  # (page, state, title, extra repeats)
    ("lambda", "menu", "Cloud landing · menu", [("Gate A re-run (earlier prompt)", "out/interact/lambda/menu/runs/A2_*.json")]),
    ("vercel-pricing", "menu", "Pricing page · menu", []),
    ("lennysjobs", "menu", "Job board · menu drawer", []),
    ("netflix-signin", "help", "Sign-in page · “Get help” disclosure", []),
]
GROUP_REVIEW = ("Council review (Oct 5): FAIL — a ~30-line notes regex produces the same plan as Nemotron, the "
                "active-tab look never moves, and the score barely separates right from wrong content. Shown as a "
                "record of the experiment, not as a result.")


def main():
    idx = RUNS / "index.json"
    if idx.exists():
        idx.unlink()
    for run, page, title, label in STATIC:
        print(export_run.export(ABL / run, BD / f"{page}-lx", f"{title} (dev capture)", label))
    for page, state, title, extra in INTERACTIONS:
        print(export_interaction.export(page, state, f"{title} (dev capture)",
                                        ["perception-sandbox-template", "perception-sandbox"],
                                        ROOT / "out" / "interact" / "gateB", extra))
    print(export_group.export("shadcn-tabs", "Docs tabs · held-out sibling states (dev capture)", None, GROUP_REVIEW))


if __name__ == "__main__":
    main()
