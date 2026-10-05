"""Export sibling-group runs (tools/group_run.py) into a replay bundle: ui/public/runs/grp-<page>/.

    .venv/bin/python tools/export_group.py <page> [--title "..."] [--variants a,b,...] [--review "..."]

Inputs (nothing is re-run): out/group/<page>/<variant>/result.json + plan.json + run/ (scenario PNGs
<bp>.base.png and <bp>.<member>.png, App.jsx, sandbox.json); design frames benchmarks-dev/<page>-lx/<bp>.png and
<bp>.<member>.png. Only sandbox variants are exported by default (folder names ending in "-sandbox").

group.json:
{
  "type": "group", "id", "title", "page", "created", "review": str | null (verdict of the latest review, verbatim),
  "breakpoints": [...], "members": [names in plan order], "given": name, "held": [names],
  "design": {bp: {"base": path, <member>: path}},
  "variants": [{"key", "planner": nemotron|repeat|template, "notes": notes|notes_prose, "oracle": bool,
                "kind", "held_out_pass", "held_out_total", "held_out_mean", "held_out_delta",
                "base_scores": {bp}, "members": {name: {scores, delta, pass, held_out, planned}},
                "failures": [str], "model_usd", "sandbox_usd", "seconds", "sandbox": {runs, vm_s, wall_s, usd},
                "renders": {bp: {"base": path, <member>: path}}, "code": path | null,
                "plan": [{"trigger", "content": [str]}]}]
}
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_common import BP_SIZE, ROOT, fresh_bundle, image, mtime, sandbox_summary, update_index  # noqa: E402

BPS = ("mobile", "tablet", "desktop")


def _read(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def export(page: str, title: str | None = None, variants: list[str] | None = None, review: str | None = None,
           index: bool = True) -> Path:
    src = ROOT / "out" / "group" / page
    design_dir = ROOT / "benchmarks-dev" / f"{page}-lx"
    keys = variants or sorted(p.name for p in src.iterdir() if p.is_dir() and p.name.endswith("-sandbox"))
    bundle_id = f"grp-{page}"
    out = fresh_bundle(bundle_id)
    vs, members, given, held = [], [], None, []
    for key in keys:
        res = _read(src / key / "result.json")
        if not res:
            continue
        v = res.get("verdict") or {}
        given, held = res.get("given"), res.get("held") or []
        names = list((v.get("members") or {}).keys())
        members = members or names
        run = src / key / "run"
        renders = {}
        for bp in BPS:
            row = {"base": image(run / f"{bp}.base.png", out, f"v/{key}/{bp}.base")}
            for m in names:
                row[m] = image(run / f"{bp}.{m}.png", out, f"v/{key}/{bp}.{m}")
            if any(row.values()):
                renders[bp] = {k: r for k, r in row.items() if r}
        code = None
        if (run / "App.jsx").exists():
            shutil.copy(run / "App.jsx", out / "v" / key / "App.jsx")
            code = f"v/{key}/App.jsx"
        sb = [s for s in [_read(run / "sandbox.json"), _read(src / key / "static" / "sandbox.json")] if s]
        plan = (res.get("plan") or {})
        vs.append({"key": key, "planner": res.get("planner"), "notes": res.get("notes"), "oracle": bool(res.get("oracle")),
                   "kind": plan.get("kind"), "held_out_pass": v.get("held_out_pass"), "held_out_total": len(held),
                   "held_out_mean": v.get("held_out_mean"), "held_out_delta": v.get("held_out_delta"),
                   "base_scores": v.get("base_scores") or {}, "members": v.get("members") or {},
                   "failures": (v.get("base_failures") or []) + (v.get("failures") or []),
                   "model_usd": res.get("model_usd"), "sandbox_usd": res.get("sandbox_usd"), "seconds": res.get("seconds"),
                   "sandbox": sandbox_summary(sb), "renders": renders, "code": code,
                   "plan": [{"trigger": m.get("trigger"), "content": m.get("content") or []} for m in plan.get("members") or []]})
    bps = [bp for bp in BPS if (design_dir / f"{bp}.png").exists()]
    design = {}
    for bp in bps:
        row = {"base": image(design_dir / f"{bp}.png", out, f"design/{bp}.base")}
        for m in members:
            row[m] = image(design_dir / f"{bp}.{m}.png", out, f"design/{bp}.{m}")
        design[bp] = {k: r for k, r in row.items() if r}
    created = max([mtime(src / v["key"] / "result.json") for v in vs] or [mtime(src)])
    bundle = {"type": "group", "id": bundle_id, "title": title or f"{page} · sibling states", "page": page,
              "created": created, "review": review,
              "breakpoints": [{"name": bp, "width": BP_SIZE[bp][0], "height": BP_SIZE[bp][1]} for bp in bps],
              "members": members, "given": given, "held": held, "design": design, "variants": vs}
    (out / "group.json").write_text(json.dumps(bundle, indent=1))
    if index:
        update_index({"id": bundle_id, "type": "group", "title": bundle["title"], "page": page, "created": created,
                      "given": given, "held": held, "review": review,
                      "variants": [{"planner": v["planner"], "notes": v["notes"], "oracle": v["oracle"],
                                    "held_out_pass": v["held_out_pass"], "held_out_total": v["held_out_total"],
                                    "held_out_delta": v["held_out_delta"]} for v in vs],
                      "thumb": design.get("mobile", {}).get(given) if given else None})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("--title")
    ap.add_argument("--variants")
    ap.add_argument("--review")
    a = ap.parse_args()
    print(export(a.page, a.title, a.variants.split(",") if a.variants else None, a.review))
