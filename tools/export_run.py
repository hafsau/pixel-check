"""Export a loop run (out/runs/<id>/) into a static replay bundle for the UI: ui/public/runs/<id>/.

    .venv/bin/python tools/export_run.py <run_dir> --design benchmarks-dev/<page> [--title "..."]

Bundle: run.json (schema below) + PNGs (design per breakpoint, every candidate's renders). Also updates
ui/public/runs/index.json. Replay needs no models and no API key — it keeps the demo alive through Dec 15.

run.json:
{
  "id", "title", "created", "models": {coder, critic, vision, editor},
  "breakpoints": [{"name": "mobile", "width": 390, "height": 844}, ...],
  "design": {"mobile": "design/mobile.png", ...},
  "result": {"stop_reason", "match", "per_bp", "best", "wall_s", "history", "spend_model_usd", "spend_sandbox_usd"},
  (a candidate's "code" is set whenever renders exist — also for disqualified ones)
  "rounds": [{"round", "best", "match", "spend_usd"}],
  "candidates": [{"id", "parent", "round", "t", "status": scored|disqualified|skipped|error, "strategy" (no "#n"),
                  "match", "mean", "per_bp", "worst", "disqualified", "reason",
                  "checkpoint", "sandbox_cost", "renders": {bp: "c/<id>/<bp>.png"}, "code": "c/<id>/App.jsx"}],
  "critiques": [{"round", "parent", "diagnosis", "strategies": [{"title", "instructions"}],
                 "feedback": "<the measured flow/visual diff text the critic and editors saw (trace field element_diff)>"}],
  "edits": [{"round", "kind": "auto"|"class"|"tools", "applied", "edits": [{id, bp, add, ...} | tool call], "skipped"}],
  "calls": [{"t", "round", "step", "model", "thinking", "in", "out", "usd", "latency_s"}]
}
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BPS = [("mobile", 390, 844), ("tablet", 768, 1024), ("desktop", 1280, 800)]


def _round_at(events, t) -> int:
    """Round a model call belongs to: the first round whose end comes after it (calls carry timestamps)."""
    for e in events:
        if e["kind"] == "round_end" and t is not None and e.get("t", 0) >= t:
            return e["round"]
    return max([e["round"] for e in events if e["kind"] == "round_end"] or [0])


def export(run_dir: Path, design_dir: Path, title: str | None = None) -> Path:
    events = [json.loads(l) for l in (run_dir / "trace.jsonl").read_text().splitlines() if l.strip()]
    result = json.loads((run_dir / "result.json").read_text())
    start = next((e for e in events if e["kind"] == "run_start"), {})
    out = ROOT / "ui" / "public" / "runs" / run_dir.name
    if out.exists():
        shutil.rmtree(out)
    (out / "design").mkdir(parents=True)
    for bp, _, _ in BPS:
        shutil.copy(design_dir / f"{bp}.png", out / "design" / f"{bp}.png")
    cands = []
    for e in events:
        if e["kind"] != "candidate":
            continue
        cdir = run_dir / "candidates" / e["id"]
        renders = {}
        if cdir.exists():
            (out / "c" / e["id"]).mkdir(parents=True, exist_ok=True)
            for bp, _, _ in BPS:
                if (cdir / f"{bp}.png").exists():
                    shutil.copy(cdir / f"{bp}.png", out / "c" / e["id"] / f"{bp}.png")
                    renders[bp] = f"c/{e['id']}/{bp}.png"
            if (cdir / "App.jsx").exists():
                shutil.copy(cdir / "App.jsx", out / "c" / e["id"] / "App.jsx")
        report = json.loads((cdir / "report.json").read_text()) if (cdir / "report.json").exists() else {}
        reason = e.get("error") or report.get("reason") or "; ".join(report.get("integrity_failures") or []) or \
            "; ".join(v.get("detail", "") for v in (report.get("lint") or {}).get("violations", []))
        status = ("disqualified" if e.get("disqualified") else "scored" if renders and e.get("per_bp")
                  else "error" if (e.get("error") or "").split(":")[0].endswith(("Error", "Expired")) else "skipped")
        cands.append({"id": e["id"], "parent": e.get("parent"), "round": e["round"], "t": e.get("t"),
                      "status": status, "strategy": (e.get("strategy") or "").split("#")[0],
                      "match": e.get("match", 0), "mean": e.get("mean", 0), "per_bp": e.get("per_bp") or {},
                      "worst": e.get("worst"), "disqualified": bool(e.get("disqualified")), "reason": reason or None,
                      "checkpoint": e.get("checkpoint"), "sandbox_cost": e.get("sandbox_cost", 0),
                      "renders": renders, "code": f"c/{e['id']}/App.jsx" if renders else None})
    run = {
        "id": run_dir.name, "title": title or run_dir.name, "created": start.get("t", time.time()),
        "models": {**start.get("models", {}), "editor": start.get("models", {}).get("editor", "nvidia/nemotron-3-super-120b-a12b")},
        "breakpoints": [{"name": n, "width": w, "height": h} for n, w, h in BPS],
        "design": {bp: f"design/{bp}.png" for bp, _, _ in BPS},
        "result": {**{k: result.get(k) for k in ("stop_reason", "match", "per_bp", "best", "wall_s", "history")},
                   "spend_usd": result.get("spend_usd"), "spend_model_usd": result.get("spend_usd"),
                   "spend_sandbox_usd": round(sum(c["sandbox_cost"] or 0 for c in cands), 4)},
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
    idx_path = ROOT / "ui" / "public" / "runs" / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    idx = [r for r in idx if r["id"] != run["id"]] + [{"id": run["id"], "title": run["title"], "match": run["result"]["match"],
                                                       "per_bp": run["result"]["per_bp"], "created": run["created"]}]
    idx_path.write_text(json.dumps(idx, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--design", type=Path, required=True)
    ap.add_argument("--title")
    a = ap.parse_args()
    print(export(a.run_dir, a.design, a.title))
