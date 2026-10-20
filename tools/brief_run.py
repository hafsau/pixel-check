"""Write the fix brief (orchestrator/brief.py) for a stored check bundle — no re-capture, no re-score.
Nemotron 3 Super via Token Factory; its cost is added to the bundle's usd and recorded in the spend ledger.

    PYTHONPATH=. .venv/bin/python tools/brief_run.py var/live/<id>/bundle [--template]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from orchestrator import brief as _brief


def rebrief(bundle_dir: Path, client) -> dict:
    p = Path(bundle_dir) / "check.json"
    chk = json.loads(p.read_text())
    before = getattr(client, "run_spend", 0.0) if client is not None else 0.0
    out = _brief.brief(chk, client=client)
    cost = (getattr(client, "run_spend", 0.0) - before) if client is not None else 0.0
    chk["brief"] = out
    if cost and chk.get("usd") is not None:
        chk["usd"] = round(chk["usd"] + cost, 4)
    p.write_text(json.dumps(chk))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--template", action="store_true", help="no model: the brief written from the facts")
    a = ap.parse_args()
    client = None
    if not a.template:
        from orchestrator import config
        from orchestrator.tf_client import TFClient
        client = TFClient(run_id=a.bundle.parent.name + "-brief", run_budget_usd=config.LIVE_RUN_BUDGET_USD)
    b = rebrief(a.bundle, client)
    print(json.dumps({"source": b["source"], "dropped": b["dropped"], "fix": [i["text"] for i in b["fix"]]}, indent=1))
