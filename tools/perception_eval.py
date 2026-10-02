"""Perception accuracy vs the DOM oracle, field by field, and which half of the spec costs the points.

    PYTHONPATH=.:sandbox .venv/bin/python tools/perception_eval.py <slug-lx> [...] [--hybrid]

Compares out/specs/<slug>.json (perception) with out/specs/<slug>.oracle.json per breakpoint:
  texts  — recall of oracle strings, top/left error of matched ink boxes, size_px error, weight accuracy, colour error
  blocks — recall/precision at IoU ≥ 0.6, fill error, border agreement
--hybrid also compiles (perception texts + oracle blocks) and (oracle texts + perception blocks) and scores them
locally against the -lx target, so the loss splits into a text part and a block part.
"""
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BPS = ("mobile", "tablet", "desktop")
norm = lambda s: re.sub(r"\s+", " ", s or "").strip().lower()


def _hex(c):
    c = c or "#000000"
    return [int(c[i:i + 2], 16) for i in (1, 3, 5)] if len(c) == 7 else [0, 0, 0]


def _iou(a, b):
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = a[2] * a[3] + b[2] * b[3] - i
    return i / u if u else 0.0


def compare(per: dict, ora: dict) -> dict:
    out = {}
    for bp in BPS:
        P, O = per["breakpoints"][bp], ora["breakpoints"][bp]
        pt = [t for t in P["texts"] if t.get("box") and not t.get("approx")]
        found, dy, dx, dfs, wok, dcol, missing = 0, [], [], [], 0, [], []
        used = set()
        for o in O["texts"]:
            best, sc = None, 0.0
            for k, p in enumerate(pt):
                if k in used:
                    continue
                s = SequenceMatcher(None, norm(o["text"]), norm(p["text"])).ratio()
                if s > sc:
                    best, sc = k, s
            if best is None or sc < 0.8:
                missing.append(o["text"][:30])
                continue
            used.add(best)
            p = pt[best]
            found += 1
            dy.append(p["box"][1] - o["box"][1])
            dx.append(p["box"][0] - o["box"][0])
            dfs.append((p.get("size_px") or 0) - o["size_px"])
            wok += int((p.get("weight") or 400) == o["weight"])
            dcol.append(sum(abs(a - b) for a, b in zip(_hex(p.get("color")), _hex(o["color"]))))
        med = lambda v: sorted(v)[len(v) // 2] if v else None
        mabs = lambda v: round(sum(abs(x) for x in v) / len(v), 1) if v else None
        pb, ob = P["blocks"], O["blocks"]
        hit = [max((_iou(o["box"], p["box"]) for p in pb), default=0) >= 0.6 for o in ob]
        prec = [max((_iou(p["box"], o["box"]) for o in ob), default=0) >= 0.6 for p in pb]
        out[bp] = {"text_recall": f"{found}/{len(O['texts'])}", "missing": missing[:6],
                   "abs_dy": mabs(dy), "abs_dx": mabs(dx), "med_dy": med(dy), "abs_dfs": mabs(dfs),
                   "weight_ok": f"{wok}/{found}", "col_err": mabs(dcol),
                   "block_recall": f"{sum(hit)}/{len(ob)}", "block_precision": f"{sum(prec)}/{len(pb)}",
                   "approx_texts": sum(1 for t in P["texts"] if t.get("approx"))}
    return out


def hybrid(slug: str, per: dict, ora: dict) -> dict:
    sys.path.insert(0, str(ROOT / "sandbox"))
    from orchestrator.fluid import compile_fluid
    from tools.intent_eval import evaluate
    res = {}
    for name, (tsrc, bsrc) in {"perception": (per, per), "texts=oracle": (ora, per), "blocks=oracle": (per, ora),
                               "oracle": (ora, ora)}.items():
        spec = {"breakpoints": {bp: dict(bsrc["breakpoints"][bp], texts=tsrc["breakpoints"][bp]["texts"])
                                for bp in BPS}}
        r = evaluate(slug, compile_fluid(spec), ROOT / "out" / "perception_eval" / slug / name)
        res[name] = (round(r["match"], 1), {k: round(v, 1) for k, v in r["per"].items()})
    return res


if __name__ == "__main__":
    for slug in [a for a in sys.argv[1:] if not a.startswith("--")]:
        per = json.loads((ROOT / "out" / "specs" / f"{slug}.json").read_text())
        ora = json.loads((ROOT / "out" / "specs" / f"{slug}.oracle.json").read_text())
        print(f"== {slug}")
        for bp, r in compare(per, ora).items():
            print(f"  {bp:8}", r)
        if "--hybrid" in sys.argv:
            for name, v in hybrid(slug, per, ora).items():
                print(f"  {name:14} {v}")
