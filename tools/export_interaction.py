"""Export interaction runs (tools/interact_run.py) into a replay bundle: ui/public/runs/ix-<page>-<state>/.

    .venv/bin/python tools/export_interaction.py <page> <state> [--title "..."]
        [--variants perception-sandbox-template,perception-sandbox]   folders under out/interact/<page>/<state>/
        [--repeats out/interact/gateB]                                  <page>.<writer><n>.json summaries (no images)
        [--extra-repeats "Gate A re-run=out/interact/lambda/menu/runs/A2_*.json"]

Inputs (nothing is re-run, no model or sandbox calls):
- design: benchmarks-dev/<page>-lx/<bp>.png (base) and <bp>.<state>.png (state frame), meta-<state>.json (trigger box)
- each variant folder: result.json + attempt<N>/ (App.jsx, interact.json, sandbox.json, scenario PNGs
  <bp>.base / <bp>.<state> / .closed / .esc / .kbd) + static/ (the page without the interaction, reference run)
- repeats: per-run summaries of the same configuration (pass, attempts, costs) — images of those runs were not kept

interaction.json:
{
  "type": "interaction", "id", "title", "page", "state", "kind": overlay|drawer|inline, "created", "writer_model",
  "breakpoints": [{name, width, height}]                       (only breakpoints with a state frame)
  "design": {bp: {"base": path, "state": path}}, "trigger": {bp: [x, y, w, h]},
  "variants": [{
     "key", "writer": template|nemotron, "source": sandbox|local, "pass", "best_attempt", "model_usd", "sandbox_usd",
     "usd", "seconds", "base_expected": {bp}, "sandbox": {runs, vm_s, wall_s, usd},
     "static": {"renders": {bp: path}, "sandbox": {...}} | null,
     "attempts": [{"attempt", "pass", "infra", "failures": [str], "state_scores", "base_scores",
                   "checks": [{bp, check, score}], "sections": {HOOKS, TRIGGER_PROPS, ...}, "code": path | null,
                   "sandbox": {op_id, elapsed_s, wall_s, cost, status} | null,
                   "captures": {bp: {"base", "open", "closed", "esc", "kbd": path}}, "panels": {bp: {...}}}]}],
  "repeats": [{"label", "writer", "source", "runs": [{"name", "pass", "best_attempt", "attempts", "usd", "model_usd",
               "sandbox_usd", "seconds", "first_pass_attempt", "matches_variant": key | null,
               "attempt_scores": [{pass, state_scores, failures}]}]}]
}
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_common import BP_SIZE, ROOT, fresh_bundle, image, mtime, sandbox_summary, update_index  # noqa: E402

SCENARIOS = [("base", "{bp}.base"), ("open", "{bp}.{state}"), ("closed", "{bp}.{state}.closed"),
             ("esc", "{bp}.{state}.esc"), ("kbd", "{bp}.{state}.kbd")]


def _read(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def _attempt(a: dict, adir: Path, out: Path, key: str, state: str, bps: list[str]) -> dict:
    v = a.get("verdict") or {}
    n = a["attempt"]
    caps, panels = {}, {}
    ij = _read(adir / "interact.json") or {}
    sc = {s["name"]: s for s in ij.get("scenarios", [])}
    for bp in bps:
        caps[bp] = {}
        for slot, pat in SCENARIOS:
            name = pat.format(bp=bp, state=state)
            rel = image(adir / f"{name}.png", out, f"v/{key}/a{n}/{name}")
            if rel:
                caps[bp][slot] = rel
        op = sc.get(f"{bp}.{state}") or {}
        if op:
            panels[bp] = {k: op.get(k) for k in ("aria_expanded", "trigger_box", "panel", "error")}
    code = None
    if (adir / "App.jsx").exists():
        (out / "v" / key / f"a{n}").mkdir(parents=True, exist_ok=True)
        shutil.copy(adir / "App.jsx", out / "v" / key / f"a{n}" / "App.jsx")
        code = f"v/{key}/a{n}/App.jsx"
    sb = _read(adir / "sandbox.json")
    return {"attempt": n, "pass": bool(v.get("pass")), "infra": bool(v.get("infra")),
            "failures": v.get("failures") or [], "state_scores": v.get("state_scores") or {},
            "base_scores": v.get("base_scores") or {}, "checks": v.get("checks") or [],
            "sections": a.get("sections") or {}, "code": code,
            "sandbox": ({k: sb.get(k) for k in ("op_id", "status", "elapsed_s", "wall_s", "cost")} if sb else None),
            "captures": caps, "panels": panels}


def _variant(vdir: Path, out: Path, state: str, bps: list[str]) -> dict:
    res = json.loads((vdir / "result.json").read_text())
    key = vdir.name
    attempts = [_attempt(a, vdir / f"attempt{a['attempt']}", out, key, state, bps) for a in res.get("attempts", [])]
    static = None
    if (vdir / "static").exists():
        renders = {bp: image(vdir / "static" / f"{bp}.base.png", out, f"v/{key}/static/{bp}") for bp in bps}
        static = {"renders": {bp: r for bp, r in renders.items() if r},
                  "sandbox": sandbox_summary([s for s in [_read(vdir / "static" / "sandbox.json")] if s])}
    records = res.get("sandbox") or []
    return {"key": key, "writer": res.get("writer") or ("template" if key.endswith("template") else "nemotron"),
            "source": "sandbox" if records else "local", "oracle": bool(res.get("oracle")),
            "pass": bool(res.get("pass")), "best_attempt": res.get("best_attempt"),
            "model_usd": res.get("model_usd"), "sandbox_usd": res.get("sandbox_usd"), "usd": res.get("usd"),
            "seconds": res.get("seconds"), "kind": res.get("kind"), "base_expected": res.get("base_expected") or {},
            "sandbox": sandbox_summary(records), "first_op": (records[0].get("op_id") if records else None),
            "op_ids": [r.get("op_id") for r in records],
            "static": static, "attempts": attempts}


def _repeat_run(name: str, d: dict, variants: list[dict]) -> dict:
    atts = d.get("attempts") or []
    ops = {r.get("op_id") for r in d.get("sandbox") or []}
    match = next((v["key"] for v in variants if ops and set(v["op_ids"]) == ops), None)
    first = next((a["attempt"] for a in atts if (a.get("verdict") or {}).get("pass")), None)
    return {"name": name, "pass": bool(d.get("pass")), "best_attempt": d.get("best_attempt"), "attempts": len(atts),
            "first_pass_attempt": first, "usd": d.get("usd"), "model_usd": d.get("model_usd"),
            "sandbox_usd": d.get("sandbox_usd"), "seconds": d.get("seconds"), "matches_variant": match,
            "attempt_scores": [{"pass": bool((a.get("verdict") or {}).get("pass")),
                                "state_scores": (a.get("verdict") or {}).get("state_scores") or {},
                                "failures": (a.get("verdict") or {}).get("failures") or []} for a in atts]}


# config.MODEL_WRITER when these runs were made (result.json does not record the model id)
WRITER_MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"


def export(page: str, state: str, title: str | None = None, variants: list[str] | None = None,
           repeats_dir: Path | None = None, extra: list[tuple[str, str]] | None = None, index: bool = True,
           writer_model: str = WRITER_MODEL) -> Path:
    src = ROOT / "out" / "interact" / page / state
    design_dir = ROOT / "benchmarks-dev" / f"{page}-lx"
    meta = json.loads((design_dir / f"meta-{state}.json").read_text())
    bps = [bp for bp in ("mobile", "tablet", "desktop") if (design_dir / f"{bp}.{state}.png").exists()]
    bundle_id = f"ix-{page}-{state}"
    out = fresh_bundle(bundle_id)
    design = {bp: {"base": image(design_dir / f"{bp}.png", out, f"design/{bp}.base"),
                   "state": image(design_dir / f"{bp}.{state}.png", out, f"design/{bp}.{state}")} for bp in bps}
    vs = [_variant(src / v, out, state, bps) for v in (variants or ["perception-sandbox-template", "perception-sandbox"])
          if (src / v / "result.json").exists()]
    reps = []
    if repeats_dir and repeats_dir.exists():
        by_writer: dict[str, list] = {}
        for f in sorted(repeats_dir.glob(f"{page}.*.json")):
            m = re.match(rf"{re.escape(page)}\.([a-z]+?)(\d*)\.json$", f.name)
            if not m:
                continue
            d = json.loads(f.read_text())
            if d.get("state") not in (None, state):
                continue
            by_writer.setdefault(m.group(1), []).append(_repeat_run(f.stem, d, vs))
        for w, runs in by_writer.items():
            reps.append({"label": "Gate B ablation", "writer": w, "source": "sandbox", "runs": runs})
    for label, pattern in extra or []:
        runs = [_repeat_run(Path(f).stem, json.loads(Path(f).read_text()), vs) for f in sorted(glob.glob(str(ROOT / pattern)))]
        if runs:
            reps.append({"label": label, "writer": "nemotron", "source": "sandbox", "runs": runs})
    kind = next((v["kind"] for v in vs if v.get("kind")), None)
    created = max([mtime(src / v["key"] / "result.json") for v in vs] or [mtime(src)])
    bundle = {"type": "interaction", "id": bundle_id, "title": title or f"{page} · {state}", "page": page,
              "state": state, "kind": kind, "created": created, "writer_model": writer_model,
              "breakpoints": [{"name": bp, "width": BP_SIZE[bp][0], "height": BP_SIZE[bp][1]} for bp in bps],
              "design": design, "trigger": {bp: v.get("box") for bp, v in (meta.get("trigger") or {}).items() if bp in bps},
              "variants": vs, "repeats": reps}
    (out / "interaction.json").write_text(json.dumps(bundle, indent=1))
    if index:
        update_index({"id": bundle_id, "type": "interaction", "title": bundle["title"], "page": page, "state": state,
                      "kind": kind, "created": created, "bps": bps,
                      "variants": [{"writer": v["writer"], "pass": v["pass"], "attempts": len(v["attempts"]),
                                    "usd": v["usd"], "state_scores": (v["attempts"][v["best_attempt"] or 0]["state_scores"]
                                                                      if v["attempts"] else {})} for v in vs],
                      "thumb": design[bps[0]]["state"] if bps else None})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("state")
    ap.add_argument("--title")
    ap.add_argument("--variants", default="perception-sandbox-template,perception-sandbox")
    ap.add_argument("--repeats", type=Path, default=ROOT / "out" / "interact" / "gateB")
    ap.add_argument("--extra-repeats", action="append", default=[], help='"Label=glob relative to the repo root"')
    a = ap.parse_args()
    extra = [tuple(x.split("=", 1)) for x in a.extra_repeats]
    print(export(a.page, a.state, a.title, a.variants.split(","), a.repeats, extra))
