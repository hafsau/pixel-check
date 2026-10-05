"""Export a loop run (out/runs/<id>/ or out/ablation/runs/<id>/) into a static replay bundle: ui/public/runs/<id>/.

    .venv/bin/python tools/export_run.py <run_dir> --design benchmarks-dev/<page>-lx [--title "..."] [--label "..."]

Bundle: run.json (schema below) + screenshots as lossless WebP (design per breakpoint, every candidate's renders) +
App.jsx per rendered candidate. Also updates ui/public/runs/index.json ("type": "static"). Replay needs no models and
no API key — it keeps the demo alive through Dec 15.

run.json:
{
  "type": "static", "id", "title", "label" (short config name, e.g. "compiler + plan"), "page", "created",
  "models": {coder, critic, vision, editor}, "cfg": {...loop config...},
  "breakpoints": [{"name": "mobile", "width": 390, "height": 844}, ...],
  "design": {"mobile": "design/mobile.webp", ...},
  "result": {"stop_reason", "match", "per_bp", "best", "wall_s", "history", "spend_usd", "spend_model_usd",
             "spend_sandbox_usd"},
  "pipeline": {"compiler": "fluid"|"scaffold"|null, "intent_plan": {cards, bands, dropped, usd} | null,
               "structure_plans": [{tags, applied, segments}], "intent_adoption": {winner, adopted, match, fluid_fails}},
  "rounds": [{"round", "best", "match", "spend_usd"}],
  "candidates": [{"id", "parent", "round", "t", "status": scored|disqualified|skipped|error, "strategy" (no "#n"),
                  "match", "mean", "per_bp", "worst", "disqualified", "reason", "checkpoint", "sandbox_cost",
                  "renders": {bp: "c/<id>/<bp>.webp"}, "code": "c/<id>/App.jsx" | null,
                  "components": {bp: {structure, layout, text, color, ...}},
                  "fluidity": {"pass", "fails": [str], "widths": {"360": {overflow, overlaps, centre_drift, max_gap,
                               bg_covers, ok}}} | null,
                  "controls": {inputs, inputs_typeable, buttons, buttons_focusable, links, links_with_href, ...} | null}],
  "critiques": [{"round", "parent", "diagnosis", "strategies": [{"title", "instructions"}], "feedback"}],
  "edits": [{"round", "kind": "auto"|"class"|"tools", "applied", "edits": [...], "skipped"}],
  "calls": [{"t", "round", "step", "model", "thinking", "in", "out", "usd", "latency_s"}]
}
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_common import BPS, ROOT, fresh_bundle, image, update_index  # noqa: E402,F401


def _round_at(events, t) -> int:
    """Round a model call belongs to: the first round whose end comes after it (calls carry timestamps)."""
    for e in events:
        if e["kind"] == "round_end" and t is not None and e.get("t", 0) >= t:
            return e["round"]
    return max([e["round"] for e in events if e["kind"] == "round_end"] or [0])


def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


def _page_of(design_dir: Path) -> str:
    return design_dir.name.removesuffix("-lx")


def export(run_dir: Path, design_dir: Path, title: str | None = None, label: str | None = None,
           index: bool = True, out_root: Path | None = None) -> Path:
    events = [json.loads(l) for l in (run_dir / "trace.jsonl").read_text().splitlines() if l.strip()]
    result = json.loads((run_dir / "result.json").read_text())
    start = next((e for e in events if e["kind"] == "run_start"), {})
    cfg = start.get("cfg") or {}
    out = fresh_bundle(run_dir.name, out_root)
    design = {bp: image(design_dir / f"{bp}.png", out, f"design/{bp}") for bp, _, _ in BPS}
    cands = []
    for e in events:
        if e["kind"] != "candidate":
            continue
        cdir = run_dir / "candidates" / e["id"]
        renders = {}
        if cdir.exists():
            for bp, _, _ in BPS:
                rel = image(cdir / f"{bp}.png", out, f"c/{e['id']}/{bp}")
                if rel:
                    renders[bp] = rel
            if renders and (cdir / "App.jsx").exists():
                shutil.copy(cdir / "App.jsx", out / "c" / e["id"] / "App.jsx")
        report = _read(cdir / "report.json")
        checks = _read(cdir / "checks.json")
        reason = e.get("error") or report.get("reason") or "; ".join(report.get("integrity_failures") or []) or \
            "; ".join(v.get("detail", "") for v in (report.get("lint") or {}).get("violations", []))
        status = ("disqualified" if e.get("disqualified") else "scored" if renders and e.get("per_bp")
                  else "error" if (e.get("error") or "").split(":")[0].endswith(("Error", "Expired")) else "skipped")
        comps = {bp: (v or {}).get("components") for bp, v in (report.get("breakpoints") or {}).items()
                 if isinstance(v, dict) and v.get("components")}
        cands.append({"id": e["id"], "parent": e.get("parent"), "round": e["round"], "t": e.get("t"),
                      "status": status, "strategy": (e.get("strategy") or "").split("#")[0],
                      "match": e.get("match", 0), "mean": e.get("mean", 0), "per_bp": e.get("per_bp") or {},
                      "worst": e.get("worst"), "disqualified": bool(e.get("disqualified")), "reason": reason or None,
                      "checkpoint": e.get("checkpoint"), "sandbox_cost": e.get("sandbox_cost", 0),
                      "renders": renders, "code": f"c/{e['id']}/App.jsx" if renders and (cdir / "App.jsx").exists() else None,
                      "components": comps or None, "fluidity": report.get("fluidity") or None,
                      "controls": checks.get("controls") or None})
    ip = next((e for e in events if e["kind"] == "intent_plan"), None)
    ad = next((e for e in events if e["kind"] == "intent_adoption"), None)
    run = {
        "type": "static", "id": run_dir.name, "title": title or run_dir.name, "label": label,
        "page": _page_of(design_dir), "created": start.get("t", time.time()),
        "models": {**start.get("models", {}), "editor": start.get("models", {}).get("editor", "nvidia/nemotron-3-super-120b-a12b")},
        "cfg": cfg,
        "breakpoints": [{"name": n, "width": w, "height": h} for n, w, h in BPS],
        "design": {bp: rel for bp, rel in design.items() if rel},
        "result": {**{k: result.get(k) for k in ("stop_reason", "match", "per_bp", "best", "wall_s", "history")},
                   "spend_usd": result.get("spend_usd"), "spend_model_usd": result.get("spend_usd"),
                   "spend_sandbox_usd": round(sum(c["sandbox_cost"] or 0 for c in cands), 4)},
        "pipeline": {
            "compiler": "fluid" if cfg.get("fluid") else "scaffold" if cfg.get("scaffold") else None,
            "intent_plan": ({"cards": [{"name": c.get("name"), "count": len(c.get("cards") or [])}
                                       for c in ((ip.get("raw") or {}).get("cards") or [])],
                             "bands": (ip.get("raw") or {}).get("bands") or {}, "dropped": ip.get("dropped") or [],
                             "usd": ip.get("usd")} if ip else None),
            "structure_plans": [{"tags": e.get("tags") or {}, "applied": e.get("applied"), "segments": e.get("segments")}
                                for e in events if e["kind"] == "structure_plan"],
            "intent_adoption": ({k: ad.get(k) for k in ("winner", "adopted", "match", "fluid_fails")} if ad else None),
        },
        "rounds": [{"round": e["round"], "best": e.get("best"), "match": e.get("match"), "spend_usd": e.get("spend")}
                   for e in events if e["kind"] == "round_end"],
        "candidates": cands,
        "critiques": [{"round": e["round"], "parent": e.get("parent"), "diagnosis": e.get("diagnosis"),
                       "strategies": [{"title": s.get("title"), "instructions": s.get("instructions")} for s in e.get("strategies", [])],
                       "feedback": e.get("element_diff")} for e in events if e["kind"] == "critique"],
        "edits": [{"round": e["round"], "kind": {"auto_edits": "auto", "edits": "class", "tool_calls": "tools"}[e["kind"]],
                   "applied": e.get("applied"),
                   "edits": [({"id": x[0], "bp": x[1], "add": x[2]} if isinstance(x, list) else x)
                             for x in (e.get("edits") or e.get("calls") or [])][:40],
                   "skipped": e.get("skipped", [])[:10]}
                  for e in events if e["kind"] in ("auto_edits", "edits", "tool_calls")],
        "calls": [{**{k: e.get(k) for k in ("t", "step", "model", "thinking", "in", "out", "usd", "latency_s")},
                   "round": _round_at(events, e.get("t"))}
                  for e in events if e["kind"] == "llm"],
    }
    (out / "run.json").write_text(json.dumps(run, indent=1))
    if index:
        best = next((c for c in cands if c["id"] == run["result"]["best"]), None)
        update_index({"id": run["id"], "type": "static", "title": run["title"], "label": label, "page": run["page"],
                      "match": run["result"]["match"], "per_bp": run["result"]["per_bp"], "created": run["created"],
                      "usd": round((result.get("spend_usd") or 0) + run["result"]["spend_sandbox_usd"], 4),
                      "fluid_pass": (best or {}).get("fluidity", {}).get("pass") if best and best.get("fluidity") else None,
                      "thumb": (best or {}).get("renders", {}).get("mobile")})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--design", type=Path, required=True)
    ap.add_argument("--title")
    ap.add_argument("--label")
    a = ap.parse_args()
    print(export(a.run_dir, a.design, a.title, a.label))
