"""Pick the coder's sampling settings by measurement: settings × samples × pages, single-shot.

Usage: .venv/bin/python -m gates.coder_settings [samples]
"""
import json, pathlib, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
from orchestrator import config
from orchestrator.code import repair, write_initial
from orchestrator.evaluate import evaluate
from orchestrator.sandbox import Sandbox
from orchestrator.tf_client import TFClient

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
PAGES = ["netflix-signin", "calcom-signup"]
SETTINGS = {"off_t1.0": ("off", 1.0), "off_t0.6": ("off", 0.6), "low_t1.0": ("low", 1.0)}
c, sb = TFClient(run_id="coder-settings", run_budget_usd=0.6), Sandbox()
data = {}
for p in PAGES:
    data[p] = dict(tg={bp: pathlib.Path(f"benchmarks-dev/{p}/{bp}.png").read_bytes() for bp in config.BREAKPOINTS},
                   tt={bp: json.loads(pathlib.Path(f"benchmarks-dev/{p}/{bp}.text.json").read_text()) for bp in config.BREAKPOINTS},
                   spec=json.loads(pathlib.Path(f"out/specs/{p}.json").read_text()))
out = pathlib.Path("out/coder_settings"); out.mkdir(parents=True, exist_ok=True)


def job(args):
    name, page, i = args
    thinking, temp = SETTINGS[name]
    d = data[page]
    t0 = time.time(); spend0 = c.run_spend
    code, raw = write_initial(c, d["spec"], thinking=thinking, temperature=temp)
    repaired = False
    e = evaluate(sb, code, d["tg"], d["tt"]) if code else None
    if e is not None and e.report.get("reason") == "build failed":
        fixed, _ = repair(c, code, e.report.get("build_log", ""))
        if fixed:
            code, repaired = fixed, True
            e = evaluate(sb, code, d["tg"], d["tt"])
    if code:
        (out / f"{page}-{name}-{i}.jsx").write_text(code)
    m = e.match if e else 0.0
    dq = (e.report.get("reason") or e.report.get("integrity_failures") or [v["detail"] for v in e.report.get("lint", {}).get("violations", [])]) if e else "no code"
    return name, page, i, m, repaired, dq, time.time() - t0


jobs = [(n, p, i) for n in SETTINGS for p in PAGES for i in range(N)]
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(job, jobs))
for n in SETTINGS:
    for p in PAGES:
        ms = [r[3] for r in res if r[0] == n and r[1] == p]
        notes = [f"{r[3]:.1f}{'(repaired)' if r[4] else ''}{'' if not r[5] else ' DQ:' + str(r[5])[:60]}" for r in res if r[0] == n and r[1] == p]
        print(f"{n:9} {p:15} median {statistics.median(ms):5.1f} max {max(ms):5.1f}  [{', '.join(notes)}]")
print(f"spend ${c.run_spend:.4f}")
json.dump(res, open(out / "results.json", "w"), default=str)
