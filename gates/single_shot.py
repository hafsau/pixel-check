"""Single-shot baseline: perceive once (cached spec), N independent code samples, evaluate each.

Usage: .venv/bin/python -m gates.single_shot <page> [n]
"""
import json, pathlib, sys, time
from concurrent.futures import ThreadPoolExecutor
from orchestrator import config
from orchestrator.code import write_initial
from orchestrator.evaluate import evaluate
from orchestrator.perceive import perceive
from orchestrator.sandbox import Sandbox
from orchestrator.tf_client import TFClient

page, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3
c, sb = TFClient(run_id=f"single-{page}", run_budget_usd=0.5), Sandbox()
tg = {bp: pathlib.Path(f"benchmarks-dev/{page}/{bp}.png").read_bytes() for bp in config.BREAKPOINTS}
tt = {bp: json.loads(pathlib.Path(f"benchmarks-dev/{page}/{bp}.text.json").read_text()) for bp in config.BREAKPOINTS}
sp = pathlib.Path(f"out/specs/{page}.json")
spec = json.loads(sp.read_text()) if sp.exists() else perceive(c, tg)
sp.write_text(json.dumps(spec, indent=1))
out = pathlib.Path(f"out/single/{page}"); out.mkdir(parents=True, exist_ok=True)

def one(i):
    t0 = time.time()
    code, raw = write_initial(c, spec)
    if not code:
        return i, None, f"no code block ({len(raw)} chars)"
    (out / f"App{i}.jsx").write_text(code)
    e = evaluate(sb, code, tg, tt)
    for k, v in e.renders.items():
        if k.endswith(".png"):
            (out / f"{i}-{k}").write_bytes(v)
    r = e.report
    per = {bp: v["score"] for bp, v in (r.get("breakpoints") or {}).items()}
    return i, e.match, f"per={per} disq={r.get('disqualified')} lint={[v['detail'] for v in r.get('lint', {}).get('violations', [])]} integ={r.get('integrity_failures')} {time.time()-t0:.0f}s"

with ThreadPoolExecutor(n) as ex:
    for i, m, info in ex.map(one, range(n)):
        print(f"sample {i}: match={m} {info}")
print(f"spend ${c.run_spend:.4f}")
