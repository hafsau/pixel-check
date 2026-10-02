"""Ablation of the responsive-intent planner on dev pages (local render; no sandbox spend, ~$0.01 of Nemotron).

    PYTHONPATH=.:sandbox .venv/bin/python tools/intent_eval.py <page> [<page> ...] [--plan-cache]

Per page: compile v2 with no plan / cards only / bands only / both; render; score at the design widths; fluidity at
360-1600. A decision is ADOPTED only if it scores no worse (match ≥ base − 0.5) and fails no more fluidity widths.
Writes out/intent/<page>/{plan.json, <variant>/...} and prints one line per variant.
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, "sandbox")
import fluidity  # noqa: E402
import integrity  # noqa: E402
import score  # noqa: E402

from orchestrator import fluid, intent  # noqa: E402
from orchestrator.tf_client import TFClient  # noqa: E402


def evaluate(page: str, code: str, out: pathlib.Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "App.jsx").write_text(code)
    lint = json.loads(subprocess.run(["node", "lint.mjs", str((out / "App.jsx").resolve())], cwd="sandbox",
                                     capture_output=True, text=True).stdout)
    subprocess.run(["node", "render.mjs", "--in", str((out / "App.jsx").resolve()), "--out", str(out.resolve())],
                   cwd="sandbox", capture_output=True)
    if not (out / "checks.json").exists():
        return {"match": 0, "per": {}, "fluid_fails": 99, "ok": False, "why": "build failed"}
    dev, t = pathlib.Path(f"benchmarks-dev/{page}"), out / "_t"
    t.mkdir(exist_ok=True)
    for bp in score.BREAKPOINTS:
        (t / f"{bp}.text.json").write_text((dev / f"{bp}.text.json").read_text())
    checks = json.loads((out / "checks.json").read_text())
    res = score.score_run(dev, out, t)
    fails = integrity.failures(checks, out, [x["text"] for bp in score.BREAKPOINTS for x in json.loads((t / f"{bp}.text.json").read_text())])
    fl = fluidity.report(checks)
    return {"match": res["match"], "per": {bp: v["score"] for bp, v in res["breakpoints"].items()},
            "fluid_fails": len(fl["fails"]), "fluid": fl["fails"], "ok": lint["ok"] and not fails, "integrity": fails}


def main(pages, cached):
    client = TFClient(run_id="intent-eval", run_budget_usd=0.25)
    summary = {}
    for page in pages:
        spec = json.loads(pathlib.Path(f"out/specs/{page}.json").read_text())
        root = pathlib.Path(f"out/intent/{page}")
        root.mkdir(parents=True, exist_ok=True)
        pf = root / "plan.json"
        if cached and pf.exists():
            rec = json.loads(pf.read_text())
            rec["intents"] = intent.revalidate(spec, rec["raw"])
        else:
            intents, raw = intent.plan_intents(client, spec)
            rec = {"intents": intents, **raw}
            pf.write_text(json.dumps(rec, indent=1))
        it = rec["intents"]
        variants = {"base": {}, "cards": {"cards": it["cards"]}, "bands": {"bands": it["bands"]}, "both": it}
        fluid.STATE["plan_fixes"] = []
        codes = {name: fluid.compile_fluid(spec, v) for name, v in variants.items()}
        res = {name: evaluate(page, code, root / name) for name, code in codes.items()}
        base = res["base"]
        for name, r in res.items():
            r["changed"] = codes[name] != codes["base"]
            adopt = (name != "base" and r["changed"] and r["ok"] and r["match"] >= base["match"] - 0.5 and r["fluid_fails"] <= base["fluid_fails"])
            r["adopt"] = adopt
            print(f"{page:15} {name:6} match {r['match']:5.1f} per {r['per']} fluid_fails {r['fluid_fails']} {r.get('fluid', '')} "
                  f"ok {r['ok']} {'ADOPT' if adopt else '' if r['changed'] or name == 'base' else 'no-op'}")
        mean = lambda r: sum(r["per"].values()) / max(len(r["per"]), 1)
        pick = max([n for n, r in res.items() if r.get("adopt")] or ["base"], key=lambda n: (round(res[n]["match"], 1), mean(res[n])))
        print(f"{'':15} plan: {len(it['cards'])} card groups {[len(g) for g in it['cards']]}, {len(it['bands'])} band intents, "
              f"dropped {it.get('dropped', [])}, fixes {fluid.STATE.get('plan_fixes', [])}, ${rec.get('usd', 0):.4f}")
        print(f"{'':15} SELECTED {pick}: match {res['base']['match']:.1f} -> {res[pick]['match']:.1f}, "
              f"mean {mean(res['base']):.1f} -> {mean(res[pick]):.1f}")
        summary[page] = {"plan": it, "results": res, "usd": rec.get("usd"), "selected": pick}
    pathlib.Path("out/intent/summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("--")], "--plan-cache" in sys.argv)
