"""Error attribution: where each page loses its points (Oct 1 step back).

    PYTHONPATH=.:sandbox .venv/bin/python tools/attribution.py <slug> [<slug> ...]      # slugs without -lx

Targets: benchmarks-dev/<slug>-lx (captured in the scoring image's Linux Chromium, tools/capture_linux.py).
Specs:   oracle      = out/specs/<slug>-lx.oracle.json (exact DOM text/styles/boxes, tools/oracle_spec.py)
         perception  = out/specs/<slug>-lx.json (Tesseract + Gemma, orchestrator/perceive.py; created if missing)
Both compiled by the fluid compiler (no intent plan) and scored locally (macOS Chromium) and in the sandbox.
  compiler ceiling   = oracle score in the sandbox
  perception loss    = oracle − perception (sandbox)
  environment gap    = sandbox − local, same code
Writes out/attribution/<slug>/{oracle,perception}/{local,sandbox}/ and out/attribution/summary.json.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "sandbox")
from orchestrator import config  # noqa: E402
from orchestrator.evaluate import evaluate as sandbox_evaluate  # noqa: E402
from orchestrator.fluid import compile_fluid  # noqa: E402
from orchestrator.perceive import perceive  # noqa: E402
from orchestrator.sandbox import Sandbox  # noqa: E402
from orchestrator.tf_client import TFClient  # noqa: E402
from tools.intent_eval import evaluate as local_evaluate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BPS = list(config.BREAKPOINTS)


def specs_for(slug: str) -> dict:
    page = f"{slug}-lx"
    sp = ROOT / "out" / "specs"
    perc = sp / f"{page}.json"
    if not perc.exists():
        tg = {bp: (ROOT / "benchmarks-dev" / page / f"{bp}.png").read_bytes() for bp in BPS}
        perc.write_text(json.dumps(perceive(TFClient(run_id=f"perceive-{page}"), tg), indent=1))
    return {"oracle": json.loads((sp / f"{page}.oracle.json").read_text()), "perception": json.loads(perc.read_text())}


def run(slug: str, sb: Sandbox) -> dict:
    page = f"{slug}-lx"
    d = ROOT / "benchmarks-dev" / page
    targets = {bp: (d / f"{bp}.png").read_bytes() for bp in BPS}
    texts = {bp: json.loads((d / f"{bp}.text.json").read_text()) for bp in BPS}
    out = {}
    for name, spec in specs_for(slug).items():
        code = compile_fluid(spec)
        base = ROOT / "out" / "attribution" / slug / name
        loc = local_evaluate(page, code, base / "local")
        ev = sandbox_evaluate(sb, code, targets, texts)
        r = ev.report
        sbx = {"match": ev.match, "per": {bp: v["score"] for bp, v in (r.get("breakpoints") or {}).items()},
               "fluid_fails": len((r.get("fluidity") or {}).get("fails") or []), "disqualified": r.get("disqualified"),
               "missing_text": {bp: v.get("missing_text", [])[:8] for bp, v in (r.get("breakpoints") or {}).items()}}
        (base / "sandbox").mkdir(parents=True, exist_ok=True)
        for k, v in ev.renders.items():
            if k.endswith(".png"):
                (base / "sandbox" / k).write_bytes(v)
        out[name] = {"local": {k: loc[k] for k in ("match", "per", "fluid_fails", "ok")}, "sandbox": sbx}
    return out


def main(slugs):
    sb = Sandbox()
    with ThreadPoolExecutor(len(slugs)) as ex:
        res = dict(zip(slugs, ex.map(lambda s: run(s, sb), slugs)))
    print(f"{'page':15} {'spec':10} {'local':>6} {'sandbox':>8}   sandbox per bp            fluid")
    for s, r in res.items():
        for name in ("oracle", "perception"):
            v = r[name]
            print(f"{s:15} {name:10} {v['local']['match']:6.1f} {v['sandbox']['match']:8.1f}   "
                  f"{v['sandbox']['per']}  {v['sandbox']['fluid_fails']}")
        o, p = r["oracle"]["sandbox"], r["perception"]["sandbox"]
        print(f"{'':15} ceiling {o['match']:.1f} · perception loss {o['match'] - p['match']:+.1f} · "
              f"env gap (oracle) {o['match'] - r['oracle']['local']['match']:+.1f}")
    (ROOT / "out" / "attribution").mkdir(parents=True, exist_ok=True)
    (ROOT / "out" / "attribution" / "summary.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
