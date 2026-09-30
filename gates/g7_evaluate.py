"""G7 (new): end-to-end candidate evaluation in the sandbox.

Cases: selftest App vs its own renders (expect ~100), vs a dev capture (expect low),
a static cheat (expect 0, disqualified), a runtime cheat (expect 0), broken JSX (expect 0, build failed).
"""
import json, pathlib, time
from orchestrator import config
from orchestrator.evaluate import evaluate
from orchestrator.sandbox import Sandbox

sb = Sandbox()
selftest = pathlib.Path("sandbox/selftest/App.jsx").read_text()
own = {bp: pathlib.Path(f"out/g5/{bp}.png").read_bytes() for bp in config.BREAKPOINTS}
dev = {bp: pathlib.Path(f"benchmarks-dev/vercel-pricing/{bp}.png").read_bytes() for bp in config.BREAKPOINTS}
dev_txt = {bp: json.loads(pathlib.Path(f"benchmarks-dev/vercel-pricing/{bp}.text.json").read_text()) for bp in config.BREAKPOINTS}
cases = [
    ("selftest vs own render", selftest, own, None, lambda e: e.match >= 99.9),
    ("selftest vs vercel-pricing", selftest, dev, dev_txt, lambda e: 0 < e.match < 60),
    ("static cheat <img>", pathlib.Path("tests/fixtures/cheat/img_tag.jsx").read_text(), own, None, lambda e: e.match == 0 and e.report["disqualified"]),
    ("runtime cheat duplicate layouts", pathlib.Path("tests/fixtures/cheat/runtime_duplicate_layouts.jsx").read_text(), own, None, lambda e: e.match == 0 and e.report["integrity_failures"]),
    ("broken JSX", "export default function App(){ return <div>", own, None, lambda e: e.match == 0 and e.report.get("reason") == "build failed"),
]
ok_all = True
for name, app, tg, tt, check in cases:
    t0 = time.time()
    e = evaluate(sb, app, tg, tt)
    ok = bool(check(e)); ok_all &= ok
    r = e.report
    print(f"{'PASS' if ok else 'FAIL'}  {name:34} match={e.match:6.2f} raw={r.get('raw_match')} worst={r.get('worst')} "
          f"lint_ok={r.get('lint', {}).get('ok')} integ={r.get('integrity_failures')} reason={r.get('reason')} "
          f"{time.time()-t0:.1f}s cost={e.render_run.cost:.4f}+{(e.score_run.cost if e.score_run else 0):.4f}")
print("G7", "PASS" if ok_all else "FAIL")
