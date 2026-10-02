"""Cross-frame matching accuracy against DOM ground truth (oracle specs carry each element's DOM path).

    PYTHONPATH=. .venv/bin/python tools/match_eval.py <slug-lx> [...]

Pairs = (element at bp1, element at bp2) joined into one compiler item. precision = joined pairs that are the same
DOM element; recall = same-DOM pairs (both visible) that were joined. Texts and blocks separately.
"""
import itertools
import json
import sys
from pathlib import Path

from orchestrator import fluid

ROOT = Path(__file__).resolve().parents[1]
BPS = ("mobile", "tablet", "desktop")


def paths_of(spec):
    """{bp: {("t"|"b", box tuple): path}}"""
    out = {}
    for bp, f in spec["breakpoints"].items():
        out[bp] = {("t", tuple(t["box"])): t.get("path") for t in f["texts"]}
        out[bp].update({("b", tuple(b["box"])): b.get("path") for b in f["blocks"]})
    return out


def evaluate(spec, items):
    P = paths_of(spec)
    res = {}
    for kind in ("t", "b"):
        joined, correct, gt = 0, 0, set()
        for bp1, bp2 in itertools.combinations(BPS, 2):
            a = {p for (k, _), p in P[bp1].items() if k == kind and p}
            b = {p for (k, _), p in P[bp2].items() if k == kind and p}
            gt |= {(bp1, bp2, p) for p in a & b}
        found = set()
        for it in items:
            if (it.kind == "text") != (kind == "t"):
                continue
            pth = {}
            for bp, at in it.at.items():
                box = tuple(at["ink"] if it.kind == "text" else at["box"])
                pth[bp] = P[bp].get((kind, box))
            for bp1, bp2 in itertools.combinations([b for b in BPS if b in pth], 2):
                joined += 1
                if pth[bp1] and pth[bp1] == pth[bp2]:
                    correct += 1
                    found.add((bp1, bp2, pth[bp1]))
        res[kind] = {"precision": round(correct / joined, 3) if joined else None,
                     "recall": round(len(found & gt) / len(gt), 3) if gt else None, "pairs": joined, "gt": len(gt)}
    return res


if __name__ == "__main__":
    for slug in sys.argv[1:]:
        spec = json.loads((ROOT / "out" / "specs" / f"{slug}.oracle.json").read_text())
        print(f"{slug:20}", evaluate(spec, fluid.prepare(spec)))
