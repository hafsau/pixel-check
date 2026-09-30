"""Single-shot coder capability: model × thinking, N samples on one page (same spec, same scorer)."""
import json, pathlib, statistics, sys
from concurrent.futures import ThreadPoolExecutor
from orchestrator import config
from orchestrator.code import write_initial
from orchestrator.evaluate import evaluate
from orchestrator.sandbox import Sandbox
from orchestrator.tf_client import TFClient

page, N = (sys.argv[1] if len(sys.argv) > 1 else "netflix-signin"), 3
ARMS = [("nvidia/nemotron-3-super-120b-a12b", "on"), ("nvidia/Nemotron-3-Ultra-550b-a55b", "off"), ("nvidia/Nemotron-3-Ultra-550b-a55b", "low")]
c, sb = TFClient(run_id="model-compare", run_budget_usd=0.5), Sandbox()
tg = {bp: pathlib.Path(f"benchmarks-dev/{page}/{bp}.png").read_bytes() for bp in config.BREAKPOINTS}
tt = {bp: json.loads(pathlib.Path(f"benchmarks-dev/{page}/{bp}.text.json").read_text()) for bp in config.BREAKPOINTS}
spec = json.loads(pathlib.Path(f"out/specs/{page}.json").read_text())
out = pathlib.Path("out/model_compare"); out.mkdir(parents=True, exist_ok=True)

def job(a):
    (model, thinking), i = a
    config.MODEL_CODER_OVERRIDE = model
    s0 = c.run_spend
    import orchestrator.code as code_mod
    orig = config.MODEL_CODER
    code, raw = code_mod.write_initial.__wrapped__(c, spec, model=model, thinking=thinking) if hasattr(code_mod.write_initial, "__wrapped__") else code_mod.write_initial(c, spec, thinking=thinking, model=model)
    if not code:
        return model, thinking, i, 0.0, "no code"
    (out / f"{page}-{model.split('/')[1]}-{thinking}-{i}.jsx").write_text(code)
    e = evaluate(sb, code, tg, tt)
    r = e.report
    return model, thinking, i, e.match, str(r.get("integrity_failures") or [v["detail"] for v in r.get("lint", {}).get("violations", [])] or r.get("reason") or "")

with ThreadPoolExecutor(9) as ex:
    res = list(ex.map(job, [(a, i) for a in ARMS for i in range(N)]))
for a in ARMS:
    ms = [r[3] for r in res if (r[0], r[1]) == a]
    print(f"{a[0].split('/')[1]:32} thinking={a[1]:4} median {statistics.median(ms):5.1f} max {max(ms):5.1f} {[round(m,1) for m in ms]} {[r[4][:40] for r in res if (r[0], r[1]) == a and r[4]]}")
print(f"spend ${c.run_spend:.4f}")
