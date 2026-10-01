"""Symmetric measurement: measure the design AND the render with the same tools, compare the numbers.

Covers what text positions can't: filled blocks (buttons, inputs, panels, image placeholders), borders,
horizontal rules, and font weight (glyph stroke thickness). Output is text findings for the critic/editor
plus deterministic edits where the responsible element is identifiable from the render's node boxes.
Runs in the orchestrator; the coder only ever sees the resulting text.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.color import rgb2lab

from .measure import _hex, _iou, background, outlined_boxes, solid_blocks


def _img(png: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float32)


from .measure import rules as _rules   # continuous, text-free dividers only (one implementation)


def rules(img: np.ndarray, text_boxes: list | None = None) -> list[dict]:
    return _rules(img, text_boxes=text_boxes)


def _inside_text(box, text_boxes, frac=0.6) -> bool:
    x, y, w, h = box
    for t in text_boxes:
        tx, ty, tw, th = t
        iw = max(0, min(x + w, tx + tw) - max(x, tx))
        ih = max(0, min(y + h, ty + th) - max(y, ty))
        if w * h and iw * ih / (w * h) >= frac:
            return True
    return False


def blocks(img: np.ndarray, text_boxes: list | None = None) -> list[dict]:
    """Filled/bordered boxes, minus glyph fragments (solid parts of large letters inside text boxes)."""
    # glyph fragments are small; a button/input IS its own text element's box, so only small blocks are filtered
    b = [x for x in solid_blocks(img, [], min_area=100)
         if max(x["box"][2], x["box"][3]) > 48 or not _inside_text(x["box"], text_boxes or [])]
    for o in outlined_boxes(img):
        if all(_iou(o["box"], x["box"]) < 0.7 for x in b):
            b.append(o)
        else:   # a filled block that also has a border
            for x in b:
                if _iou(o["box"], x["box"]) >= 0.7:
                    x["border"] = o["border"]
    return b


def _de(a: str, b: str) -> float:
    ca = np.array([int(a[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
    cb = np.array([int(b[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
    return float(np.linalg.norm(rgb2lab(ca[None, None])[0, 0] - rgb2lab(cb[None, None])[0, 0]))


def _match(db, rbs):
    best, score = None, 0.0
    for rb in rbs:
        s = _iou(db["box"], rb["box"])
        if s > score:
            best, score = rb, s
    return best if score >= 0.4 else None


def _node_for(box, nodes, min_iou=0.75):
    """The unique rendered element (with a data-pc id) whose box matches `box`."""
    best, score = None, 0.0
    for n in nodes:
        if n.get("pc") is None or not n.get("v"):
            continue
        s = _iou(box, n.get("b") or [0, 0, 0, 0])
        if s > score:
            best, score = n, s
    if best is None or score < min_iou or sum(1 for m in nodes if m.get("pc") == best["pc"]) != 1:
        return None
    return best


def block_diff(bp: str, design_png: bytes, render_png: bytes, nodes: list[dict], design_text_boxes: list,
               render_text_boxes: list) -> tuple[list[str], list[dict]]:
    d_img, r_img = _img(design_png), _img(render_png)
    dbs, rbs = blocks(d_img, design_text_boxes), blocks(r_img, render_text_boxes)
    findings, edits = [], []
    for db in dbs:
        rb = _match(db, rbs)
        box = ",".join(map(str, db["box"]))
        if rb is None:
            findings.append(f"MISSING block [{box}] fill {db['fill']}" + (f" border {db['border']}" if db.get("border") else ""))
            continue
        node = _node_for(rb["box"], nodes)
        if _de(db["fill"], rb["fill"]) > 8:
            findings.append(f"block [{box}] fill {rb['fill']}→{db['fill']}")
            if node is not None:
                edits.append({"id": int(node["pc"]), "bp": bp, "add": f"bg-[{db['fill']}]", "why": "block fill"})
        if db.get("border") and not rb.get("border"):
            findings.append(f"block [{box}] needs border {db['border']}")
            if node is not None:
                edits.append({"id": int(node["pc"]), "bp": bp, "add": f"border border-[{db['border']}]", "why": "block border"})
        dw, dh, rw, rh = db["box"][2], db["box"][3], rb["box"][2], rb["box"][3]
        if abs(dw - rw) > 8 or abs(dh - rh) > 6:
            findings.append(f"block [{box}] size {rw}x{rh}→{dw}x{dh}")
            if node is not None and abs(dh - rh) > 6:
                edits.append({"id": int(node["pc"]), "bp": bp, "add": f"!h-[{dh}px]", "why": "block height"})
            if node is not None and abs(dw - rw) > 8:
                edits.append({"id": int(node["pc"]), "bp": bp, "add": f"!w-[{dw}px]", "why": "block width"})
    for rb in rbs:
        if _match(rb, dbs) is None and rb["box"][2] * rb["box"][3] > 400:
            findings.append(f"EXTRA block [{','.join(map(str, rb['box']))}] fill {rb['fill']} (not in design)")
    for ln in rules(d_img, design_text_boxes):
        if not any(abs(ln["box"][1] - r["box"][1]) <= 4 for r in rules(r_img, render_text_boxes)):
            findings.append(f"MISSING horizontal rule at y={ln['box'][1]} x={ln['box'][0]}..{ln['box'][0] + ln['box'][2]} "
                            f"colour {ln['fill']} (e.g. a border-b on the header)")
    return findings, edits


def _stroke(img: np.ndarray, box) -> float | None:
    """Mean glyph stroke thickness in px: ink pixels / (edge pixels / 2) inside a text box."""
    x, y, w, h = [int(v) for v in box[:4]]
    patch = img[max(0, y):y + h, max(0, x):x + w]
    if patch.size == 0:
        return None
    ring = np.concatenate([patch[0], patch[-1], patch[:, 0], patch[:, -1]])
    back = np.median(ring, axis=0)
    ink = np.linalg.norm(patch - back, axis=-1) > 60
    if ink.sum() < 20:
        return None
    edge = ink & ~ndimage.binary_erosion(ink)
    return float(ink.sum() / max(edge.sum() / 2.0, 1))


WEIGHTS = [400, 500, 600, 700]
WEIGHT_CLASS = {400: "font-normal", 500: "font-medium", 600: "font-semibold", 700: "font-bold"}


def weight_diff(bp: str, design_png: bytes, render_png: bytes, pairs: list[dict], dom: list[dict]) -> tuple[list[str], list[dict]]:
    """Compare glyph stroke thickness of the same text in design and render → heavier/lighter weight."""
    d_img, r_img = _img(design_png), _img(render_png)
    findings, edits = [], []
    by_pc = {str(e.get("pc")): e for e in dom}
    for p in pairs:
        if p.get("r") is None or p.get("id") is None or not p.get("size") or p["size"] < 14:
            continue
        sd, sr = _stroke(d_img, p["d"]), _stroke(r_img, p["r"])
        if not sd or not sr:
            continue
        ratio = sd / sr
        cur = int(float(by_pc.get(str(p["id"]), {}).get("font_weight", 400) or 400))
        cur = min(WEIGHTS, key=lambda w: abs(w - cur))
        if ratio > 1.18 and cur < 700:
            new = WEIGHTS[min(len(WEIGHTS) - 1, WEIGHTS.index(cur) + (2 if ratio > 1.4 else 1))]
        elif ratio < 0.85 and cur > 400:
            new = WEIGHTS[max(0, WEIGHTS.index(cur) - (2 if ratio < 0.7 else 1))]
        else:
            continue
        findings.append(f"#{p['id']} '{p['label'][:24]}' strokes {'heavier' if new > cur else 'lighter'} in design "
                        f"(×{ratio:.2f}) → font-weight {cur}→{new}")
        edits.append({"id": int(p["id"]), "bp": bp, "add": WEIGHT_CLASS[new], "why": "font weight"})
    return findings, edits
