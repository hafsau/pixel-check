"""Gate B' run: sibling interactions from ONE example state (docs/INTERACTIONS.md).

    PYTHONPATH=.:sandbox .venv/bin/python tools/group_run.py <page> --given=<state> --held=<s1,s2> \
        [--planner=nemotron|repeat|template] [--notes=notes|notes_prose] [--oracle] [--sandbox] [--name=group]

Base spec: perception (out/specs/<page>-lx.json) or --oracle; the given state's frame is perceived the same way
(cached as out/specs/<page>-lx.<state>.json) or --oracle. Held-out states are only used for scoring.
Writes out/group/<page>/<planner>-<notes>[-oracle][-sandbox]/ (plan.json, run/, result.json).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from orchestrator.group_loop import load_targets, run_group  # noqa: E402
from orchestrator.interact_loop import local_runner, sandbox_cost  # noqa: E402
from orchestrator.perceive import perceive  # noqa: E402
from orchestrator.tf_client import TFClient  # noqa: E402


def main(page, given, held, planner, notes, oracle, sandbox, name):
    d = ROOT / "benchmarks-dev" / f"{page}-lx"
    meta = json.loads((d / f"meta-{given}.json").read_text())
    trig = {bp: v["box"] for bp, v in meta["trigger"].items() if v.get("box")}
    client = TFClient(run_id=f"group-{page}-{planner}", run_budget_usd=0.5)
    if oracle:
        from oracle_spec import frame as oracle_frame
        base = json.loads((ROOT / "out" / "specs" / f"{page}-lx.oracle.json").read_text())
        frames = {bp: oracle_frame(f"{page}-lx", bp, state=given) for bp in trig}
    else:
        base = json.loads((ROOT / "out" / "specs" / f"{page}-lx.json").read_text())
        sp = ROOT / "out" / "specs" / f"{page}-lx.{given}.json"
        if not sp.exists():
            sp.write_text(json.dumps(perceive(client, {bp: (d / f"{bp}.{given}.png").read_bytes() for bp in trig}), indent=1))
        frames = json.loads(sp.read_text())["breakpoints"]
    targets = load_targets(d, [given] + held)
    runner = local_runner
    if sandbox:
        from orchestrator.interact_loop import sandbox_runner
        runner = sandbox_runner
    tag = f"{planner}-{notes}" + ("-oracle" if oracle else "") + ("-sandbox" if sandbox else "")
    out = ROOT / "out" / "group" / page / tag
    if out.exists():
        import shutil
        shutil.rmtree(out)
    t0 = time.time()
    res = run_group(base, {"name": given, "trigger": trig, "frames": frames}, targets, (d / f"{notes}.md").read_text(),
                    planner, client, runner, out, name=name)
    v = res["verdict"]
    summary = {"page": page, "planner": planner, "notes": notes, "oracle": oracle, "given": given, "held": held,
               "verdict": v, "plan": res["plan"], "model_usd": round(client.run_spend, 4),
               "sandbox_usd": round(sandbox_cost(out), 4), "seconds": round(time.time() - t0, 1)}
    (out / "result.json").write_text(json.dumps(summary, indent=1))
    for s, m in v["members"].items():
        print(f"  {s:12} held_out={m['held_out']!s:5} pass={m['pass']!s:5} scores={m['scores']} delta={m['delta']}")
    print(f"{page} {tag}: held-out pass {v['held_out_pass']}/{len(held)}  delta {v['held_out_delta']}  "
          f"base_failures {v['base_failures']}  ${summary['model_usd']} + sandbox ${summary['sandbox_usd']}  {summary['seconds']}s")


if __name__ == "__main__":
    opt = lambda k, dflt=None: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(k + "=")), dflt)
    main(sys.argv[1], opt("--given"), [s for s in (opt("--held") or "").split(",") if s], opt("--planner", "nemotron"),
         opt("--notes", "notes"), "--oracle" in sys.argv, "--sandbox" in sys.argv, opt("--name", "group"))
