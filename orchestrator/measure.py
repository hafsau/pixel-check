"""Deterministic measurement of a design frame: text line boxes (OCR), ink colours, solid blocks.

Why: the vision model reads text reliably (95.8 %) but its boxes are ~100 px off (median;
no coordinate transform fixes it — see docs/PLATFORM.md G3b). Tesseract finds fewer strings
(76.5 %) but places them within ~4.5 px. perceive.py merges the two.
"""
from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage

OCR_SCALE = 2
OCR_MIN_CONF = 30
BG_THRESHOLD = 24.0


def _hex(rgb) -> str:
    # clamp: a mean of 255.000x rounded to 256 printed "#100100100" (invalid Tailwind colour)
    return "#{:02x}{:02x}{:02x}".format(*[min(255, max(0, int(round(float(c))))) for c in rgb])


def background(img: np.ndarray) -> np.ndarray:
    """Most frequent colour: mode over 64 levels/channel, refined to the mean of that bin. (8-level bins merged a
    black page with its dark-grey footer band into one bin; the drifted mean put the band right on the content
    threshold, so identical dark footers were 'content' in one image and background in the other.)"""
    q = (img // 4).astype(np.int64)
    keys = (q[..., 0] * 64 + q[..., 1]) * 64 + q[..., 2]
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
                          "conf": float(np.mean([w[5] for w in ws])),
                          "words": [{"text": w[4], "box": [round(w[0]), round(w[1]), round(w[2]), round(w[3])]} for w in ws]})
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
        if np.linalg.norm(colour - bg) <= 8:     # subtle fills count (white buttons/cards on light grey differ by ~14)
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
        # a real frame has ≥ 3 sides mostly covered by an edge line (≥ 60 %); dividers meeting in a T or an L (a nav
        # bar's vertical separators + its bottom border) only touch the sides (lambda header, Oct 1)
        cover = [comp[:3].any(axis=0).mean(), comp[-3:].any(axis=0).mean(),
                 comp[:, :3].any(axis=1).mean(), comp[:, -3:].any(axis=1).mean()]
        if sum(c >= 0.6 for c in cover) < 3:
            continue
        border = img[ys, xs][comp & frame[sl]].mean(axis=0) if (comp & frame[sl]).any() else bg
        out.append({"box": [xs.start, ys.start, bw, bh], "fill": _hex(bg), "border": _hex(border)})
    return out


def _frac_inside(box, outer) -> float:
    x, y, w, h = box
    iw = max(0, min(x + w, outer[0] + outer[2]) - max(x, outer[0]))
    ih = max(0, min(y + h, outer[1] + outer[3]) - max(y, outer[1]))
    return (iw * ih) / (w * h) if w * h else 0.0


def rules(img: np.ndarray, min_frac: float = 0.4, text_boxes: list | None = None) -> list[dict]:
    """Thin (≤ 3 px) horizontal lines spanning ≥ 40 % of the width, CONTINUOUS (≥ 95 % of their span) and not
    crossing any text box: dividers, header underlines. (Without the last two, a long line of small text on a
    390 px frame was detected as a divider.)"""
    bg = background(img)
    d = np.linalg.norm(img - bg, axis=-1) > 8
    out, H = [], d.shape[0]
    rows = d.mean(axis=1)
    y = 0
    while y < H:
        if rows[y] >= min_frac:
            y0 = y
            while y < H and rows[y] >= min_frac:
                y += 1
            if y - y0 <= 3:
                col = d[y0:y].any(axis=0)
                xs = np.where(col)[0]
                box = [int(xs.min()), y0, int(xs.max() - xs.min() + 1), y - y0]
                # columns covered by a text box crossing this row don't count (a divider interrupted by "or");
                # a line of text itself leaves almost nothing once its own box is masked out
                keep = np.ones(xs.max() - xs.min() + 1, bool)
                for tb in (text_boxes or []):
                    if tb[1] - 2 <= y0 <= tb[1] + tb[3] + 2:
                        a0, a1 = max(tb[0] - 4, xs.min()), min(tb[0] + tb[2] + 4, xs.max() + 1)
                        if a1 > a0:
                            keep[a0 - xs.min():a1 - xs.min()] = False
                seg = col[xs.min():xs.max() + 1][keep]
                if keep.mean() >= 0.6 and seg.size and seg.mean() >= 0.95:
                    fill = _hex(img[y0:y][d[y0:y]].mean(axis=0))
                    if keep.all():
                        out.append({"box": box, "fill": fill})
                    else:   # interrupted by text ("— or —"): one rule per visible segment, so layout can flow around it
                        run = np.flatnonzero(np.diff(np.concatenate([[0], (col[xs.min():xs.max() + 1] & keep).astype(int), [0]])))
                        for a0, a1 in zip(run[::2], run[1::2]):
                            if a1 - a0 >= 16:
                                out.append({"box": [int(xs.min() + a0), y0, int(a1 - a0), y - y0], "fill": fill})
        y += 1
    return out


def thin_lines(img: np.ndarray, text_boxes: list, min_h_len: int = 24, min_v_len: int = 40) -> list[dict]:
    """Thin (≤ 3 px) lines in BOTH orientations by local contrast: a pixel that differs from the pixels 3 px to either
    side (which agree with each other) is on a line. Catches what rules() missed (Oct 1, vs DOM oracle): vertical
    column dividers (lambda, vercel, calcom) and faint 1 px dividers inside cards (#ebebeb on #fafafa). Thick glyph
    strokes are not thin, so large headings don't produce lines; text boxes are masked out."""
    H, W, _ = img.shape
    out = []
    mask_text = np.zeros((H, W), bool)
    for tb in text_boxes:
        x, y, w, h = [int(v) for v in tb]
        mask_text[max(0, y - 2):y + h + 2, max(0, x - 2):x + w + 2] = True
    for axis in (0, 1):          # 0: horizontal lines (compare up/down), 1: vertical lines (compare left/right)
        a = np.roll(img, 3, axis=axis)
        b = np.roll(img, -3, axis=axis)
        da = np.linalg.norm(img - a, axis=-1)
        db = np.linalg.norm(img - b, axis=-1)
        same = np.linalg.norm(a - b, axis=-1) < 8
        line = (da > 6) & (db > 6) & same & ~mask_text
        if axis == 0:
            line[:3], line[-3:] = False, False
            runs = ndimage.binary_opening(line, np.ones((1, min_h_len), bool))
        else:
            line[:, :3], line[:, -3:] = False, False
            runs = ndimage.binary_opening(line, np.ones((min_v_len, 1), bool))
        lab, n = ndimage.label(runs)
        for i, sl in enumerate(ndimage.find_objects(lab), 1):
            ys, xs = sl
            bw, bh = xs.stop - xs.start, ys.stop - ys.start
            if (axis == 0 and bh > 3) or (axis == 1 and bw > 3):
                continue
            comp = lab[sl] == i
            out.append({"box": [int(xs.start), int(ys.start), int(bw), int(bh)], "fill": _hex(img[ys, xs][comp].mean(axis=0))})
    return out


def crosses(img: np.ndarray, text_boxes: list, min_len: int = 8, max_len: int = 24) -> list[dict]:
    """Small "+" icons → two thin rules crossing at their centres (fluid._glyphs turns the pair into one glyph).
    An ink component of plus size whose centre row AND centre column are mostly ink while the box is mostly empty
    (a T-junction, a letter or a filled square fails one of those). Components inside text boxes are skipped."""
    bg = background(img)
    ink = np.linalg.norm(img - bg, axis=-1) > 40
    for tb in text_boxes:
        x, y, w, h = [int(v) for v in tb]
        ink[max(0, y - 1):y + h + 1, max(0, x - 1):x + w + 1] = False
    lab, n = ndimage.label(ink, np.ones((3, 3), bool))
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        ys, xs = sl
        w, h = xs.stop - xs.start, ys.stop - ys.start
        if not (min_len <= w <= max_len and min_len <= h <= max_len) or abs(w - h) > 4:
            continue
        comp = lab[sl] == i
        if comp.mean() > 0.45:
            continue
        rows, cols = comp.mean(axis=1), comp.mean(axis=0)
        hr = np.nonzero(rows >= 0.8)[0]      # rows of the horizontal bar
        vc = np.nonzero(cols >= 0.8)[0]      # columns of the vertical bar
        if not len(hr) or not len(vc) or len(hr) > 3 or len(vc) > 3:
            continue
        cy, cx = (hr.min() + hr.max()) / 2, (vc.min() + vc.max()) / 2
        if abs(cy - (h - 1) / 2) > 1.5 or abs(cx - (w - 1) / 2) > 1.5:
            continue                          # bars must cross at the middle (a "T" crosses at an end)
        fill = _hex(img[ys, xs][comp].mean(axis=0))
        out.append({"box": [int(xs.start), int(ys.start + hr.min()), int(w), int(len(hr))], "fill": fill})
        out.append({"box": [int(xs.start + vc.min()), int(ys.start), int(len(vc)), int(h)], "fill": fill})
    return out


def block_labels(img: np.ndarray, blocks: list, lines: list) -> list[dict]:
    """OCR inside control-sized filled boxes that have no text yet, one line each, contrast-stretched and inverted
    when the text is lighter than the fill. The whole-page pass misses light-on-dark button labels ("LAUNCH GPU
    INSTANCE", "Continue", "Sign Up", "Continue with Google" — every dev page, Oct 1)."""
    if not shutil.which("tesseract"):
        return []
    found = []
    for b in blocks:
        x, y, w, h = [int(v) for v in b["box"]]
        if b.get("rule") or not (16 <= h <= 90 and w >= 30) or any(_inside(l["box"], b["box"]) for l in lines):
            continue
        crop = img[y + 2:y + h - 2, x + 2:x + w - 2]
        if crop.size == 0:
            continue
        grey = crop.mean(axis=2)
        lo, hi = np.percentile(grey, 2), np.percentile(grey, 98)
        if hi - lo < 30:
            continue
        g = np.clip((grey - lo) / (hi - lo) * 255, 0, 255)
        if np.median(g) < 128:      # dark fill → light text: make the text dark for tesseract
            g = 255 - g
        im = Image.fromarray(g.astype(np.uint8)).resize((g.shape[1] * 3, g.shape[0] * 3), Image.LANCZOS)
        im = ImageOps.expand(im, border=12, fill=255)
        buf = io.BytesIO(); im.save(buf, "PNG")
        out = subprocess.run(["tesseract", "stdin", "stdout", "--psm", "7", "tsv"], input=buf.getvalue(),
                             capture_output=True).stdout.decode()
        words = [r for r in csv.DictReader(io.StringIO(out), delimiter="\t")
                 if (r.get("text") or "").strip() and float(r["conf"]) >= 55]
        if not words:
            continue
        xs0 = min(int(r["left"]) for r in words); ys0 = min(int(r["top"]) for r in words)
        xs1 = max(int(r["left"]) + int(r["width"]) for r in words); ys1 = max(int(r["top"]) + int(r["height"]) for r in words)
        bx = [x + 2 + (xs0 - 12) / 3, y + 2 + (ys0 - 12) / 3, (xs1 - xs0) / 3, (ys1 - ys0) / 3]
        to_page = lambda r: [round(x + 2 + (int(r["left"]) - 12) / 3), round(y + 2 + (int(r["top"]) - 12) / 3),
                             round(int(r["width"]) / 3), round(int(r["height"]) / 3)]
        found.append({"text": " ".join(r["text"] for r in words), "box": [round(v) for v in bx],
                      "conf": float(np.mean([float(r["conf"]) for r in words])), "in_block": True,
                      "words": [{"text": r["text"], "box": to_page(r)} for r in words]})
    return found


def _border_and_radius(img: np.ndarray, b: dict, bg: np.ndarray) -> None:
    """1 px ring just outside the block: uniform and distinct from fill and page → border (box grows by 1).
    Corner radius: steps along the top-left diagonal until the fill colour starts, × 1/(1 − 1/√2)."""
    H, W, _ = img.shape
    x, y, w, h = b["box"]
    fill = np.array([int(b["fill"][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
    if x >= 3 and y >= 3 and x + w + 3 < W and y + h + 3 < H and not b.get("border") and min(w, h) >= 8:
        e = 10 if min(w, h) > 30 else 2   # skip rounded corners
        sides = [img[y - 1, x + e:x + w - e], img[y + h, x + e:x + w - e], img[y + e:y + h - e, x - 1], img[y + e:y + h - e, x + w]]
        beyond = [img[y - 3, x + e:x + w - e], img[y + h + 2, x + e:x + w - e], img[y + e:y + h - e, x - 3], img[y + e:y + h - e, x + w + 2]]
        good = []
        for sd, by in zip(sides, beyond):
            if len(sd) < 3:
                continue
            med = np.median(sd, axis=0)
            if (np.mean(np.linalg.norm(sd - med, axis=1) < 15) >= 0.8 and np.linalg.norm(med - fill) > 10
                    and np.linalg.norm(med - np.median(by, axis=0)) > 10):
                good.append(med)
        if len(good) >= 3 and max(np.linalg.norm(a - c) for a in good for c in good) < 40:
            b["border"] = _hex(np.median(np.array(good), axis=0))   # a drop shadow darkens the bottom side
            # shadow: the 2 rows below the bottom border fade back to the page colour
            below = [np.median(img[y + h + k, x + e:x + w - e], axis=0) for k in (1, 2)]
            if all(np.linalg.norm(v - bg) > 4 for v in below[:1]) and np.linalg.norm(below[-1] - bg) < np.linalg.norm(below[0] - bg):
                b["shadow"] = True
            b["box"] = [x - 1, y - 1, w + 2, h + 2]
            x, y, w, h = b["box"]
    k = 0
    while k < min(w, h) // 2 and np.linalg.norm(img[y + k, x + k] - fill) > 12:
        k += 1
    r = int(round(k / (1 - 2 ** -0.5))) if k else 0
    side = min(w, h)
    if r > side // 2:             # the walk ran past the corner: a pill if small, otherwise a measurement failure
        r = side // 2 if side <= 60 else 0
    if r > 32 and side > 120:     # large cards with radii > 32 px are implausible here; treat as failed
        r = 0
    if r >= 2:
        b["radius"] = r


def _inside(inner, outer, slack=2) -> bool:
    return (inner[0] >= outer[0] - slack and inner[1] >= outer[1] - slack and
            inner[0] + inner[2] <= outer[0] + outer[2] + slack and inner[1] + inner[3] <= outer[1] + outer[3] + slack)


def drop_caret(img: np.ndarray, line: dict) -> dict:
    """OCR reads an input's text cursor as a leading '|' and its box then spans the cursor's full height (52 px for
    16 px text). Drop the leftmost tall thin ink component and re-fit a tight box around the remaining glyphs."""
    if not line["text"].lstrip().startswith("|"):
        return line
    x, y, w, h = line["box"]
    patch = img[max(0, y):y + h, max(0, x):x + w]
    ring = np.concatenate([patch[0], patch[-1], patch[:, 0], patch[:, -1]])
    dist = np.linalg.norm(patch - np.median(ring, axis=0), axis=-1)
    ink = dist >= 0.5 * np.percentile(dist, 99)   # same 50 %-contrast rule as typography (halos made boxes 2 px tall)
    lab, n = ndimage.label(ink)
    comps = ndimage.find_objects(lab)
    if not comps:
        return line
    first = min(range(n), key=lambda k: comps[k][1].start)
    sl = comps[first]
    if (sl[1].stop - sl[1].start) <= 4 and (sl[0].stop - sl[0].start) >= 0.6 * h:
        ink[lab == first + 1] = False
    ys, xs = np.where(ink)
    if not len(xs):
        return line
    text = re.sub(r"^\s*\|\s*", "", line["text"])
    return dict(line, text=text, box=[x + int(xs.min()), y + int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)])


def measure(png: bytes) -> dict:
    img = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float32)
    lines = [drop_caret(img, l) for l in ocr_lines(img)]
    from .typography import infer
    for l in lines:
        l["color"], l["backdrop"] = ink_and_backdrop(img, l["box"])
        l["typo"] = infer(l["text"], l["box"], img)     # size / weight / letter-spacing from Inter's real metrics
    text_boxes = [t["box"] for t in lines]
    # small blocks too (icons / image placeholders ≥ 100 px²), minus glyph fragments: solid parts of large letters
    # sit inside text boxes and are small (a button/input IS bigger than its label, so it is never dropped)
    # minus glyph fragments: solid parts of letters sit inside a text box (a button/input is bigger than its label,
    # so it is never inside one); large headings' strokes (72 px "l" = 14×64) used to pass a size test
    # (small relative to that box: OCR also reads image placeholders as junk text like "[Ld" — the placeholder is
    # then about the size of the junk text's box and must stay)
    blocks = [b for b in solid_blocks(img, lines, min_area=100)
              if not any(_frac_inside(b["box"], tb) >= 0.6 and b["box"][2] * b["box"][3] < 0.5 * tb[2] * tb[3]
                         for tb in text_boxes)]
    for o in outlined_boxes(img):
        same = [b for b in blocks if _iou(o["box"], b["box"]) >= 0.7]
        if same:                      # a filled block that also has a border (e.g. an input)
            for b in same:
                b["border"] = o["border"]
        else:
            o["contains_text"] = [t["text"] for t in lines if _inside(t["box"], o["box"])][:4]
            blocks.append(o)
    bg_c = background(img)
    from .shadow import fit_shadow
    for b in blocks:                  # borders and corner radius, measured on every block
        _border_and_radius(img, b, bg_c)
        if min(b["box"][2], b["box"][3]) >= 40:      # a soft shadow → its CSS (offset, blur, opacity)
            fit = fit_shadow(img, b["box"], bg_c)
            if fit:
                b["shadow_fit"] = {k: fit[k] for k in ("y", "blur", "alpha")}
    for r in rules(img, text_boxes=text_boxes):   # thin horizontal dividers (a header's border-b)
        if all(_iou(r["box"], b["box"]) < 0.5 for b in blocks):
            blocks.append({"box": r["box"], "fill": r["fill"], "rule": True, "contains_text": []})
    def on_border(r):   # a line along a bordered block's edge is that border, not a divider
        x, y, w, h = r["box"]
        for b in blocks:
            if b.get("rule") or not b.get("border"):
                continue
            bx, by, bw, bh = b["box"]
            if h <= 3 and min(abs(y - by), abs(y - (by + bh - 1))) <= 2 and x >= bx - 3 and x + w <= bx + bw + 3:
                return True
            if w <= 3 and min(abs(x - bx), abs(x - (bx + bw - 1))) <= 2 and y >= by - 3 and y + h <= by + bh + 3:
                return True
        return False
    def covered(r):     # already found (a piece of a full-width rule found again)
        x, y, w, h = r["box"]
        return any(_frac_inside([x, y, w, h], [b["box"][0] - 2, b["box"][1] - 2, b["box"][2] + 4, b["box"][3] + 4]) >= 0.8
                   for b in blocks)
    for r in thin_lines(img, text_boxes):        # vertical and faint dividers
        if not on_border(r) and not covered(r) and all(_iou(r["box"], b["box"]) < 0.5 for b in blocks):
            blocks.append({"box": r["box"], "fill": r["fill"], "rule": True, "contains_text": []})
    # OCR junk the size of a box (the whole red Continue button read as "hE", conf 38) is not its label
    junk = [l for l in lines if l["conf"] < 60 and any(_iou(l["box"], b["box"]) > 0.6 for b in blocks)]
    for l in junk:
        lines.remove(l)
        for b in blocks:
            b["contains_text"] = [t for t in (b.get("contains_text") or []) if t != l["text"]]
    for r in crosses(img, [l["box"] for l in lines]):   # small "+" icons (a pair of crossing rules each)
        blocks.append({"box": r["box"], "fill": r["fill"], "rule": True, "contains_text": []})
    for l in block_labels(img, blocks, lines):   # light-on-dark button labels
        l["color"], l["backdrop"] = ink_and_backdrop(img, l["box"])
        l["typo"] = infer(l["text"], l["box"], img)
        lines.append(l)
        for b in blocks:
            if _inside(l["box"], b["box"]) and not b.get("rule"):
                b["contains_text"] = (b.get("contains_text") or []) + [l["text"]]
                break
    blocks.sort(key=lambda b: (b["box"][1], b["box"][0]))
    return {"size": [img.shape[1], img.shape[0]], "background": _hex(background(img)),
            "text_lines": lines, "blocks": blocks}
