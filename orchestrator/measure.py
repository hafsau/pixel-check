"""Deterministic measurement of a design frame: text line boxes (OCR), ink colours, solid blocks.

Why: the vision model reads text reliably (95.8 %) but its boxes are ~100 px off (median;
no coordinate transform fixes it — see docs/PLATFORM.md G3b). Tesseract finds fewer strings
(76.5 %) but places them within ~4.5 px. perceive.py merges the two.
"""
from __future__ import annotations

import csv
import io
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage

OCR_SCALE = 2
OCR_MIN_CONF = 30
BG_THRESHOLD = 24.0


def _hex(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[int(round(c)) for c in rgb])


def background(img: np.ndarray) -> np.ndarray:
    q = (img // 32).astype(np.int32)
    keys = q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]
    mode = np.bincount(keys.ravel()).argmax()
    return np.clip(img[keys == mode].mean(axis=0, dtype=np.float64), 0, 255)


def ocr_lines(img: np.ndarray) -> list[dict]:
    """Tesseract line boxes in image pixels. Runs twice (normal + inverted) so light-on-dark
    text is found too; overlapping duplicates are merged keeping the higher confidence."""
    if not shutil.which("tesseract"):
        raise RuntimeError("tesseract not installed (brew install tesseract / apt install tesseract-ocr)")
    grey = Image.fromarray(img.astype(np.uint8)).convert("L")
    found = []
    for variant in (grey, ImageOps.invert(grey)):
        im = variant.resize((grey.width * OCR_SCALE, grey.height * OCR_SCALE), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "PNG")
        out = subprocess.run(["tesseract", "stdin", "stdout", "--psm", "11", "tsv"], input=buf.getvalue(),
                             capture_output=True, check=True).stdout.decode()
        lines: dict[tuple, list] = {}
        for r in csv.DictReader(io.StringIO(out), delimiter="\t"):
            if not (r.get("text") or "").strip() or float(r["conf"]) < OCR_MIN_CONF:
                continue
            k = (r["block_num"], r["par_num"], r["line_num"])
            x, y, w, h = (int(r[c]) / OCR_SCALE for c in ("left", "top", "width", "height"))
            lines.setdefault(k, []).append((x, y, w, h, r["text"], float(r["conf"])))
        for ws in lines.values():
            x0, y0 = min(w[0] for w in ws), min(w[1] for w in ws)
            x1, y1 = max(w[0] + w[2] for w in ws), max(w[1] + w[3] for w in ws)
            found.append({"text": " ".join(w[4] for w in ws), "box": [round(x0), round(y0), round(x1 - x0), round(y1 - y0)],
                          "conf": float(np.mean([w[5] for w in ws]))})
    found.sort(key=lambda l: -l["conf"])
    kept = []
    for l in found:
        if all(_iou(l["box"], k["box"]) < 0.3 for k in kept):
            kept.append(l)
    kept.sort(key=lambda l: (l["box"][1], l["box"][0]))
    return kept


def _iou(a, b) -> float:
    ax1, ay1, bx1, by1 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw, ih = max(0, min(ax1, bx1) - max(a[0], b[0])), max(0, min(ay1, by1) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union else 0.0


def ink_and_backdrop(img: np.ndarray, box) -> tuple[str, str]:
    """Text colour and the colour directly behind it, for one text box."""
    x, y, w, h = [int(v) for v in box]
    H, W, _ = img.shape
    pad = 3
    x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
    patch = img[y0:y1, x0:x1].reshape(-1, 3)
    ring = np.concatenate([img[y0:y1, x0].reshape(-1, 3), img[y0:y1, x1 - 1].reshape(-1, 3),
                           img[y0, x0:x1].reshape(-1, 3), img[y1 - 1, x0:x1].reshape(-1, 3)])
    back = np.median(ring, axis=0)
    d = np.linalg.norm(patch - back, axis=1)
    ink = patch[d >= np.percentile(d, 90)] if d.max() > BG_THRESHOLD else patch
    return _hex(np.median(ink, axis=0)), _hex(back)


def solid_blocks(img: np.ndarray, text_boxes: list, min_area: int = 600) -> list[dict]:
    """Filled rectangles (buttons, cards, inputs, placeholders) as boxes + fill colour.

    A block = connected region of near-uniform colour that differs from the page background,
    found per quantised colour so a button inside a card is its own block.
    """
    H, W, _ = img.shape
    bg = background(img)
    q = (img // 12).astype(np.int32)
    keys = q[..., 0] * 10000 + q[..., 1] * 100 + q[..., 2]
    vals, counts = np.unique(keys, return_counts=True)
    blocks = []
    for v in vals[counts >= min_area]:
        m = keys == v
        colour = img[m].mean(axis=0)
        if np.linalg.norm(colour - bg) <= BG_THRESHOLD:
            continue
        lab, n = ndimage.label(ndimage.binary_closing(m, np.ones((5, 5), bool)))
        for i, sl in enumerate(ndimage.find_objects(lab), 1):
            ys, xs = sl
            bw, bh = xs.stop - xs.start, ys.stop - ys.start
            fill_ratio = (lab[sl] == i).mean()
            if bw * bh < min_area or fill_ratio < 0.6 or min(bw, bh) < 6:
                continue
            blocks.append({"box": [xs.start, ys.start, bw, bh], "fill": _hex(colour), "area": bw * bh})
    blocks.sort(key=lambda b: -b["area"])
    kept = []
    for b in blocks:  # drop near-duplicates of larger blocks
        if all(_iou(b["box"], k["box"]) < 0.8 for k in kept):
            kept.append(b)
    for b in kept:
        b["contains_text"] = [t["text"] for t in text_boxes if _inside(t["box"], b["box"])][:4]
        del b["area"]
    kept.sort(key=lambda b: (b["box"][1], b["box"][0]))
    return kept[:60]


def outlined_boxes(img: np.ndarray, min_w: int = 40, min_h: int = 24) -> list[dict]:
    """Rectangles drawn by thin borders (cards/inputs whose fill equals the page background)."""
    bg = background(img)
    d = np.linalg.norm(img - bg, axis=-1)
    faint = (d > 6) & (d < 120)
    # long straight runs only: horizontal and vertical line pixels
    h_lines = ndimage.binary_opening(faint, np.ones((1, 25), bool))
    v_lines = ndimage.binary_opening(faint, np.ones((15, 1), bool))
    frame = h_lines | v_lines
    lab, n = ndimage.label(ndimage.binary_dilation(frame, np.ones((3, 3), bool)))
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        ys, xs = sl
        bw, bh = xs.stop - xs.start, ys.stop - ys.start
        if bw < min_w or bh < min_h:
            continue
        comp = lab[sl] == i
        # a frame touches all four sides of its bounding box and is mostly hollow
        sides = comp[:3].any() and comp[-3:].any() and comp[:, :3].any() and comp[:, -3:].any()
        if not sides or comp.mean() > 0.35:
            continue
        # needs both a top/bottom edge and a left/right edge (not just one long divider)
        if comp[:3].mean() < 0.5 and comp[-3:].mean() < 0.5:
            continue
        border = img[ys, xs][comp & frame[sl]].mean(axis=0) if (comp & frame[sl]).any() else bg
        out.append({"box": [xs.start, ys.start, bw, bh], "fill": _hex(bg), "border": _hex(border)})
    return out


def _inside(inner, outer, slack=2) -> bool:
    return (inner[0] >= outer[0] - slack and inner[1] >= outer[1] - slack and
            inner[0] + inner[2] <= outer[0] + outer[2] + slack and inner[1] + inner[3] <= outer[1] + outer[3] + slack)


def measure(png: bytes) -> dict:
    img = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float32)
    lines = ocr_lines(img)
    for l in lines:
        l["color"], l["backdrop"] = ink_and_backdrop(img, l["box"])
    blocks = solid_blocks(img, lines)
    for o in outlined_boxes(img):
        if all(_iou(o["box"], b["box"]) < 0.7 for b in blocks):
            o["contains_text"] = [t["text"] for t in lines if _inside(t["box"], o["box"])][:4]
            blocks.append(o)
    blocks.sort(key=lambda b: (b["box"][1], b["box"][0]))
    return {"size": [img.shape[1], img.shape[0]], "background": _hex(background(img)),
            "text_lines": lines, "blocks": blocks}
