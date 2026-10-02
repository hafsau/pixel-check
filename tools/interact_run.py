"""Run the interaction pipeline on a dev page with a captured state (docs/INTERACTIONS.md).

    PYTHONPATH=.:sandbox .venv/bin/python tools/interact_run.py <page> --state=menu [--oracle] [--sandbox] [--attempts=3]

Base spec: perception (out/specs/<page>-lx.json) or --oracle; state frames: perceived from <bp>.<state>.png the same
way (cached as out/specs/<page>-lx.<state>.json) or --oracle. Trigger boxes from meta-<state>.json. Runner: local
node harness, or --sandbox (Token Factory sandbox, runtime image with render.mjs --interact).
Writes out/interact/<page>/<state>/ (attempts, App.jsx per attempt, result.json).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from orchestrator.interact_loop import local_runner, run_interaction  # noqa: E402
from orchestrator.perceive import perceive  # noqa: E402
from orchestrator.tf_client import TFClient  # noqa: E402


def main(page: str, state: str, oracle: bool, sandbox: bool, attempts: int):
    d = ROOT / "benchmarks-dev" / f"{page}-lx"
    meta = json.loads((d / f"meta-{state}.json").read_text())
    trig = {bp: v["box"] for bp, v in meta["trigger"].items() if v.get("box")}
    client = TFClient(run_id=f"interact-{page}-{state}", run_budget_usd=0.5)
    if oracle:
        from oracle_spec import frame as oracle_frame
        base = json.loads((ROOT / "out" / "specs" / f"{page}-lx.oracle.json").read_text())
        states = {bp: oracle_frame(f"{page}-lx", bp, state=state) for bp in trig}
    else:
        base = json.loads((ROOT / "out" / "specs" / f"{page}-lx.json").read_text())
        sp = ROOT / "out" / "specs" / f"{page}-lx.{state}.json"
        if not sp.exists():
            sp.write_text(json.dumps(perceive(client, {bp: (d / f"{bp}.{state}.png").read_bytes() for bp in trig}), indent=1))
        states = json.loads(sp.read_text())["breakpoints"]
    targets = {"base": {bp: d / f"{bp}.png" for bp in trig}, "states": {bp: d / f"{bp}.{state}.png" for bp in trig},
               "base_texts": {bp: d / f"{bp}.text.json" for bp in trig},
               "state_texts": {bp: d / f"{bp}.{state}.text.json" for bp in trig}}
    runner = local_runner
    if sandbox:
        from orchestrator.interact_loop import sandbox_runner
        runner = sandbox_runner
    out = ROOT / "out" / "interact" / page / state / (("oracle" if oracle else "perception") + ("-sandbox" if sandbox else ""))
    if out.exists():                 # stale attempts from an earlier run must not leak into this one's record
        import shutil
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    res = run_interaction(base, states, trig, targets, state, client, runner, out=out, max_attempts=attempts)
    for a in res["attempts"]:
        v = a["verdict"]
        print(f"attempt {a['attempt']}: pass {v['pass']}  state scores {v.get('state_scores')}  failures {v['failures'][:4]}")
    summary = {"page": page, "state": state, "oracle": oracle, "pass": res["pass"], "best_attempt": res["best_attempt"],
               "kind": res["kind"], "attempts": [{"attempt": a["attempt"], "verdict": a["verdict"], "sections": a["sections"]}
                                                 for a in res["attempts"]],
               "usd": round(client.run_spend, 4), "seconds": round(time.time() - t0, 1),
               "sandbox": [json.loads(p.read_text()) for p in sorted(out.glob("attempt*/sandbox.json"))]}
    (out / "result.json").write_text(json.dumps(summary, indent=1))
    if res["code"]:
        (out / "App.jsx").write_text(res["code"])
    print(f"pass {res['pass']}  best attempt {res['best_attempt']}  ${summary['usd']}  {summary['seconds']}s  → {out}")


if __name__ == "__main__":
    opt = lambda k, d=None: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(k + "=")), d)
    main(sys.argv[1], opt("--state", "menu"), "--oracle" in sys.argv, "--sandbox" in sys.argv, int(opt("--attempts", 3)))
