"""Oracle spec: the frame spec perception SHOULD produce, read from the live DOM of a captured page.

    PYTHONPATH=. .venv/bin/python tools/oracle_spec.py <slug> [<slug> ...]     # e.g. vercel-pricing-lx

Input: benchmarks-dev/<slug>/<bp>.{png,notext.png,oracle.json} (tools/capture_linux.py). Output:
out/specs/<slug>.oracle.json in the same format as orchestrator/perceive.perceive(), so the same compiler runs on it.
Texts: exact strings and computed size / weight / colour / letter-spacing; ink boxes measured from the screenshot
(normal minus text-transparent), the same kind of box OCR gives. Blocks: painted boxes from computed styles.
Used for error attribution only (compiler ceiling vs perception loss) — dev pages, never reported as results.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from orchestrator.typography import metrics

ROOT = Path(__file__).resolve().parents[1]
BPS = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}


def _snap_weight(w) -> int:
    return min((400, 500, 600, 700), key=lambda x: abs(x - int(w)))


def _ink(mask: np.ndarray, r) -> list | None:
    x, y, w, h = r
    H, W = mask.shape
    x0, y0, x1, y1 = max(0, x - 2), max(0, y - 2), min(W, x + w + 2), min(H, y + h + 2)
    sub = mask[y0:y1, x0:x1]
    if not sub.any():
        return None
    ys, xs = np.nonzero(sub)
    return [int(x0 + xs.min()), int(y0 + ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]


def _background(img: np.ndarray) -> str:
    q = (img[::4, ::4] // 4 * 4).reshape(-1, 3)
    vals, counts = np.unique(q, axis=0, return_counts=True)
    c = vals[counts.argmax()]
    return "#" + "".join(f"{int(v):02x}" for v in c)


def frame(slug: str, bp: str) -> dict:
    d = ROOT / "benchmarks-dev" / slug
    img = np.asarray(Image.open(d / f"{bp}.png").convert("RGB")).astype(int)
    nt = np.asarray(Image.open(d / f"{bp}.notext.png").convert("RGB")).astype(int)
    mask = np.abs(img - nt).sum(axis=2) > 40
    dom = json.loads((d / f"{bp}.oracle.json").read_text())
    texts = []
    for t in dom["texts"]:
        lines = [b for b in (_ink(mask, r) for r in t["lines"]) if b]
        if not lines:
            continue
        x0, y0 = min(b[0] for b in lines), min(b[1] for b in lines)
        x1, y1 = max(b[0] + b[2] for b in lines), max(b[1] + b[3] for b in lines)
        fs = max(8, int(round(t["size_px"])))
        w = _snap_weight(t["weight"])
        top = metrics(t["text"], w)[2]
        texts.append({"text": t["text"], "role": t["role"], "size_px": fs, "weight": w,
                      "box": [x0, y0, x1 - x0, y1 - y0], "color": t["color"], "measured": True, "lines": len(lines),
                      "line_boxes": lines, "tracking_em": round(t.get("letter_spacing_px", 0) / fs, 3),
                      "top_em": round(top, 3), "underline": bool(t.get("underline")), "oracle": True})
    blocks, seen = [], set()
    for b in dom["blocks"]:
        key = (tuple(b["box"]), b.get("rule", False))
        if key in seen:
            continue
        seen.add(key)
        bx = b["box"]
        if bx[2] * bx[3] >= 0.9 * BPS[bp][0] * BPS[bp][1]:
            continue   # a page-size wrapper is the background (perception never reports it as a block)
        inside = [t["text"] for t in texts if bx[0] <= t["box"][0] + t["box"][2] / 2 <= bx[0] + bx[2]
                  and bx[1] <= t["box"][1] + t["box"][3] / 2 <= bx[1] + bx[3]]
        blk = {"box": bx, "fill": b.get("fill"), "contains_text": inside}
        if b.get("rule"):
            blk["rule"] = True
        else:
            blk.update(border=b.get("border"), radius=b.get("radius") or None, shadow=bool(b.get("shadow")))
        blocks.append(blk)
    return {"size": list(BPS[bp]), "background": _background(img), "texts": texts, "blocks": blocks,
            "layout": "", "vlm_blocks": []}


def build(slug: str) -> Path:
    spec = {"breakpoints": {bp: frame(slug, bp) for bp in BPS}, "oracle": True}
    out = ROOT / "out" / "specs" / f"{slug}.oracle.json"
    out.write_text(json.dumps(spec, indent=1))
    return out


if __name__ == "__main__":
    for s in sys.argv[1:]:
        p = build(s)
        sp = json.loads(p.read_text())
        print(p, {bp: (len(f["texts"]), len(f["blocks"])) for bp, f in sp["breakpoints"].items()})
