"""Step D ablation: what each part of the pipeline adds, measured in the real sandbox loop.

    PYTHONPATH=.:sandbox .venv/bin/python tools/ablation.py [--configs a,b] [--pages p1,p2]

Pages: Linux re-captures (benchmarks-dev/<page>-lx) with their perception specs (out/specs/<page>-lx.json).
Configs:
  compiler    fluid compiler only (+ Nemotron semantic tags, which never change the score)
  plan        + Nemotron responsive-intent plan seeds (verified adoption in round 0)
  loop        + 2 loop rounds (auto / edit-all / nemotron-tools branches)
  drafts      Ultra-written initial drafts only, no compiler (the pre-compiler approach, for reference)
Per run: worst-breakpoint match, per-bp scores, fluidity fails, which candidate won, $ (models + sandbox), seconds.
Writes out/ablation/summary.json.
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from orchestrator import config
from orchestrator.loop import LoopConfig, run_loop

ROOT = Path(__file__).resolve().parents[1]
BPS = list(config.BREAKPOINTS)
CONFIGS = {
    "compiler": dict(scaffold=True, fluid=True, intents=False, initial_samples=0, max_rounds=0),
    "plan": dict(scaffold=True, fluid=True, intents=True, initial_samples=0, max_rounds=0),
    "loop": dict(scaffold=True, fluid=True, intents=True, initial_samples=0, max_rounds=2),
    "drafts": dict(scaffold=False, fluid=True, intents=False, initial_samples=2, max_rounds=0),
}


def one(page: str, name: str) -> dict:
    d = ROOT / "benchmarks-dev" / f"{page}-lx"
    targets = {bp: (d / f"{bp}.png").read_bytes() for bp in BPS}
    texts = {bp: json.loads((d / f"{bp}.text.json").read_text()) for bp in BPS}
    spec = json.loads((ROOT / "out" / "specs" / f"{page}-lx.json").read_text())
    run_id = f"abl-{name}-{page}-" + time.strftime("%H%M%S")
    res = run_loop(targets, spec, texts, run_id=run_id, cfg=LoopConfig(**CONFIGS[name], run_budget_usd=0.6),
                   out_root=ROOT / "out" / "ablation" / "runs")
    trace = [json.loads(l) for l in (ROOT / "out" / "ablation" / "runs" / run_id / "trace.jsonl").read_text().splitlines()]
    cands = [e for e in trace if e["kind"] == "candidate"]
    best = next((e for e in cands if e["id"] == res["best"]), {})
    sandbox_usd = sum(e.get("sandbox_cost") or 0 for e in cands)
    report = json.loads((ROOT / "out" / "ablation" / "runs" / run_id / "candidates" / res["best"] / "report.json").read_text()) if res["best"] else {}
    return {"page": page, "config": name, "match": res["match"], "per_bp": res["per_bp"], "winner": best.get("strategy"),
            "fluid_fails": len((report.get("fluidity") or {}).get("fails") or []),
            "candidates": len(cands), "adopted_model_change": bool(best.get("strategy") and best["strategy"] not in ("scaffold", "auto")),
            "usd_models": res["spend_usd"], "usd_sandbox": round(sandbox_usd, 4),
            "usd_total": round(res["spend_usd"] + sandbox_usd, 4), "wall_s": res["wall_s"], "run": run_id}


if __name__ == "__main__":
    arg = lambda k, d: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(k + "=")), d)
    configs = arg("--configs", "compiler,plan,loop").split(",")
    pages = arg("--pages", "netflix-signin,calcom-signup,vercel-pricing,lambda").split(",")
    jobs = [(p, c) for c in configs for p in pages]
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(lambda j: one(*j), jobs))
    for r in rows:
        print(f"{r['page']:15} {r['config']:9} match {r['match']:5.1f} {r['per_bp']}  winner {r['winner']}  "
              f"fluid_fails {r['fluid_fails']}  cands {r['candidates']}  ${r['usd_total']:.3f} {r['wall_s']}s", flush=True)
    out = ROOT / "out" / "ablation"
    out.mkdir(parents=True, exist_ok=True)
    prev = json.loads((out / "summary.json").read_text()) if (out / "summary.json").exists() else []
    (out / "summary.json").write_text(json.dumps(prev + rows, indent=1))
