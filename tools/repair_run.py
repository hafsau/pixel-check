"""Run the repair benchmark arms on one build (docs/REPAIR.md): no repair · Nemotron one-shot · Nemotron repair loop.

    PYTHONPATH=. .venv/bin/python tools/repair_run.py --code build.jsx --frames DIR [--spec spec.json] \
        [--arms none,one_shot,repair] [--rounds 3] --out DIR

DIR holds {mobile,tablet,desktop}.png (the design frames). --spec reuses a stored design reading (else the frames
are read once with vision + OCR). Real sandboxes and Nemotron; writes <out>/result.json and <out>/<arm>.jsx.
Dev builds (from third-party captures) are for developing the agent only — never reported.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orchestrator import config  # noqa: E402
from orchestrator.check import check_code  # noqa: E402
from orchestrator.repair import _propose_default, lines_kept, one_shot, repair, summary  # noqa: E402
from orchestrator.sandbox import Sandbox  # noqa: E402
from orchestrator.tf_client import TFClient  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", type=Path, required=True)
    ap.add_argument("--frames", type=Path, required=True)
    ap.add_argument("--spec", type=Path)
    ap.add_argument("--arms", default="none,one_shot,repair")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    code = a.code.read_text()
    frames = {bp: (a.frames / f"{bp}.png").read_bytes() for bp in ("mobile", "tablet", "desktop")}
    client = TFClient(run_id=f"repair-{a.out.name}", run_budget_usd=config.RUN_BUDGET_USD)
    sb = Sandbox()
    if a.spec:
        spec = json.loads(a.spec.read_text())
    else:
        from orchestrator.perceive import perceive
        spec = perceive(client, frames)
    sandbox_usd = [0.0]

    def check(c):
        out = check_code(c, frames, sb=sb, read_design=None, emit=lambda *x, **k: None, spec=spec)
        return out
    propose = _propose_default(client)
    results = {}
    for arm in a.arms.split(","):
        t0, spend0 = time.time(), client.run_spend
        if arm == "none":
            s = summary(check(code)["report"])
            res = {"code": code, "start": s, "best": s, "history": [dict(s, round=0)], "lines_kept": 1.0}
        elif arm == "one_shot":
            res = one_shot(code, spec=spec, check=check, propose=propose)
        elif arm == "repair":
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(3) as ex:
                res = repair(code, spec=spec, check=check, propose=propose, rounds=a.rounds, pmap=ex.map)
        else:
            raise SystemExit(f"unknown arm {arm}")
        (a.out / f"{arm}.jsx").write_text(res["code"])
        res = {k: v for k, v in res.items() if k != "code"}
        res.update(wall_s=round(time.time() - t0, 1), model_usd=round(client.run_spend - spend0, 4),
                   lines_kept=lines_kept(code, (a.out / f"{arm}.jsx").read_text()))
        results[arm] = res
        b = res["best"]
        print(f"{arm:<9} worst {b['worst']}  per_bp {b['per_bp']}  width fails {b['fluid_fails']}  "
              f"lines kept {res['lines_kept']:.0%}  {res['wall_s']}s  ${res['model_usd']}", flush=True)
    (a.out / "result.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
