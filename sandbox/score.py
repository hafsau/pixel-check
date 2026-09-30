"""Pixel-Check scorer. Compares a render to its target design, per breakpoint.

Per breakpoint (all components in [0, 1]):
    S = 100 × (0.25 + 0.75·color) × (0.5 + 0.5·text) × (0.57·structure + 0.43·layout)
    (also computed at the best global offset, ≤ 32 px per axis, × (1 − 0.006·(|dy|+|dx|)); the highest wins)
    Match = min(S_mobile, S_tablet, S_desktop)      (mean is reported, never used to rank)

- structure: F1 of edge energy (Sobel on half-res greyscale), averaged over spatial tolerances
  ±2, ±4, ±8, ±16 px, so displacement costs points gradually (a single ±4 px tolerance made a
  12 px offset score below a render missing content). Replaces SSIM: SSIM scores flat
  regions as similar, so a blank render got 0.57 structure even when masked to content.
- layout: min(precision, recall) of content cells (8 px grid, 1-cell tolerance) × (0.5 + 0.5 ×
  ink-coverage agreement per 3×3-cell neighbourhood — v3, red-team "dust"): a 1–2 px shift
  costs ~nothing; missing blocks (recall) and extra blocks (precision) each cost fully. min, not
  F1: with perfect precision, F1 turned "56% of the content area missing" into 0.70. Same idea
  as Match = min over breakpoints — one failure can't hide behind another's success.
- color (a multiplier, not an add-on: a dark-mode render of a light design keeps every edge
  and block, so an additive colour term let inverted renders score ~71):
  area-weighted: bg_frac × background match (clip(1 − ΔE_bg/60)) + (1 − bg_frac) × content
  colour, where bg_frac = share of target pixels that are background — i.e. roughly "the share
  of the page whose colour matches". Content colour: per 16 px cell holding content in either image, ΔE(Lab) between the mean colour of
  the target's content pixels and the render's content pixels nearby; a cell with content on
  only one side scores 0. Score = mean(clip(1 − ΔE/40)). Averaging whole cells (v1) blended
  thin text into the background and rewarded blank renders.
- text: fraction of target strings found in the render DOM (fuzzy ≥ 0.85). Needs both the
  target text list and the render DOM; if either is missing the weight is redistributed and
  the report says so.

Content = pixels whose colour differs from that image's OWN background colour by > 24 (RGB
distance). Measuring the render against the target's background (v1) made a solid fill of the
wrong colour count as "content everywhere" (layout recall 1.0); the wrong background is
penalised by the colour multiplier instead.

CLI (inside the sandbox, disposable run):
    python3 score.py --targets DIR --renders DIR [--texts DIR]  -> JSON on stdout
DIR holds {mobile,tablet,desktop}.png (renders also *.dom.json; texts *.text.json).
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import numpy as np

import readable as _readable
from PIL import Image
from scipy import ndimage
from skimage.color import rgb2lab

BREAKPOINTS = ("mobile", "tablet", "desktop")
WEIGHTS = {"structure": 0.57, "layout": 0.43}   # spatial part; colour and text multiply
COLOR_FLOOR = 0.25          # colour 0 keeps 25 %
TEXT_FLOOR = 0.50           # no correct text keeps 50 % (red-team r2: lorem-ipsum copy on a perfect layout scored 64)
TEXT_NEAR_MIN, TEXT_NEAR_FRAC = 96.0, 0.15   # text counts only within max(96 px, 15 % of viewport width) of its design spot
BG_DE_SCALE = 60.0
BG_THRESHOLD = 24.0
LAYOUT_CELL = 8
COLOR_CELL = 16
TEXT_MATCH = 0.85
TOP_REGIONS = 8
CELL_DE_SCALE = 40.0        # whole-cell colour agreement (kills dotted / hollow "dust" fills)
OFFSET_MAX = 32             # global vertical offset search, px
OFFSET_PENALTY = 0.006      # score multiplier lost per px of global offset
TEXT_MIN_FONT = 8.0
TEXT_MIN_INK = 0.03         # share of content pixels a text box must have to count as readable
MIN_SIDE = 32


def load(path) -> np.ndarray:
    """RGB float32 in 0..255. Transparent pixels are composited on white (a Figma export without a
    frame fill otherwise reads as black); 16-bit greyscale is scaled down, not clipped."""
    im = Image.open(path)
    if im.mode in ("I;16", "I;16B", "I;16L", "I"):
        a = np.asarray(im, dtype=np.float32)
        im = Image.fromarray((a / (257.0 if a.max() > 255 else 1.0)).clip(0, 255).astype(np.uint8))
    if im.mode in ("RGBA", "LA", "P", "PA"):
        im = im.convert("RGBA")
        white = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(white, im)
    arr = np.asarray(im.convert("RGB"), dtype=np.float32)
    if min(arr.shape[:2]) < MIN_SIDE:
        raise ValueError(f"image too small: {arr.shape[1]}x{arr.shape[0]}")
    return arr


def background(img: np.ndarray) -> np.ndarray:
    """Most frequent colour (quantised to 8 levels/channel), refined to the mean of that bin."""
    q = (img // 32).astype(np.int32)
    keys = q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]
    mode = np.bincount(keys.ravel()).argmax()
    return np.clip(img[keys == mode].mean(axis=0, dtype=np.float64), 0, 255).astype(np.float32)   # float32 sums drifted to 255.4


def content_mask(img: np.ndarray, bg: np.ndarray) -> np.ndarray:
    return np.linalg.norm(img - bg, axis=-1) > BG_THRESHOLD


def cells(mask: np.ndarray, size: int, frac: float = 0.02) -> np.ndarray:
    h, w = mask.shape
    hh, ww = h // size, w // size
    m = mask[: hh * size, : ww * size].reshape(hh, size, ww, size).mean(axis=(1, 3))
    return m > frac


def _edges(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Horizontal- and vertical-gradient energy at half resolution, kept SEPARATE: with one
    combined magnitude, 2 px horizontal rules stood in for lines of text (red-team #3)."""
    g = Image.fromarray(img.astype(np.uint8)).convert("L")
    g = np.asarray(g.resize((g.width // 2, g.height // 2), Image.BOX), dtype=np.float32)
    return np.abs(ndimage.sobel(g, 0)), np.abs(ndimage.sobel(g, 1))


def _edge_f1(et: np.ndarray, er: np.ndarray, tol: int) -> float:
    st, sr = et.sum(), er.sum()
    if st == 0 and sr == 0:
        return 1.0
    if st == 0 or sr == 0:
        return 0.0
    k = 2 * tol + 1
    recall = np.minimum(et, ndimage.maximum_filter(er, size=k)).sum() / st
    precision = np.minimum(er, ndimage.maximum_filter(et, size=k)).sum() / sr
    return 0.0 if recall + precision == 0 else float(2 * recall * precision / (recall + precision))


STRUCTURE_TOLS = (1, 2, 4, 8)   # half-res px → ±2, ±4, ±8, ±16 px


def structure_score(t: np.ndarray, r: np.ndarray) -> float:
    """Edge-energy F1 at half resolution, per gradient direction, averaged over STRUCTURE_TOLS."""
    (ty, tx), (ry, rx) = _edges(t), _edges(r)
    return float(np.mean([_edge_f1(a, b, tol) for a, b in ((ty, ry), (tx, rx)) for tol in STRUCTURE_TOLS]))


def layout_score(tc: np.ndarray, rc: np.ndarray, tcov: np.ndarray | None = None,
                 rcov: np.ndarray | None = None) -> tuple[float, float, float]:
    """min(precision, recall) of content cells (1-cell tolerance) × (0.5 + 0.5·coverage agreement).

    Coverage agreement compares HOW MUCH ink each 3×3-cell neighbourhood holds, not just whether any:
    a 3 px dot per cell (red-team "dust") marks every cell present but covers ~14 % vs ~25 % for text,
    and a solid blob covers 100 %. Returns (score, precision, recall).
    """
    if not tc.any() and not rc.any():
        return 1.0, 1.0, 1.0
    if not tc.any() or not rc.any():
        return 0.0, float(not rc.any()), float(not tc.any())
    k = np.ones((3, 3), bool)
    precision = (rc & ndimage.binary_dilation(tc, k)).sum() / rc.sum()
    recall = (tc & ndimage.binary_dilation(rc, k)).sum() / tc.sum()
    agree = 1.0
    if tcov is not None and rcov is not None:
        kt = ndimage.uniform_filter(tcov, size=3, mode="constant")
        kr = ndimage.uniform_filter(rcov, size=3, mode="constant")
        union = tc | rc
        ratio = np.minimum(kt, kr) / np.maximum(np.maximum(kt, kr), 1e-6)
        agree = float(ratio[union].mean())
    return float(min(precision, recall) * (0.5 + 0.5 * agree)), float(precision), float(recall)


def coverage(mask: np.ndarray, size: int) -> np.ndarray:
    h, w = mask.shape
    hh, ww = h // size, w // size
    return mask[: hh * size, : ww * size].reshape(hh, size, ww, size).mean(axis=(1, 3))


def _grid(a: np.ndarray, size: int) -> np.ndarray:
    """Crop to whole cells and reshape to (rows, size, cols, size, ...)."""
    hh, ww = a.shape[0] // size, a.shape[1] // size
    a = a[: hh * size, : ww * size]
    return a.reshape(hh, size, ww, size, *a.shape[2:])


def color_score(t, r, tm, rm) -> tuple[float, np.ndarray]:
    """Content-pixel colour agreement per 16 px cell, content-weighted.

    Each target content cell is compared with the best-matching render content cell in its
    3×3 neighbourhood (tolerates small shifts moving anti-aliased pixels across cell edges).
    Target content with no render content nearby, and render content with no target content
    nearby, score 0. Returns (score, per-cell ΔE; nan = no content in either).
    """
    tg, rg = _grid(t, COLOR_CELL), _grid(r, COLOR_CELL)
    tmg, rmg = _grid(tm, COLOR_CELL), _grid(rm, COLOR_CELL)
    tn, rn = tmg.sum(axis=(1, 3)).astype(float), rmg.sum(axis=(1, 3)).astype(float)
    tlab = rgb2lab((tg * tmg[..., None]).sum(axis=(1, 3)) / np.maximum(tn, 1)[..., None] / 255.0)
    rlab = rgb2lab((rg * rmg[..., None]).sum(axis=(1, 3)) / np.maximum(rn, 1)[..., None] / 255.0)
    has_t, has_r = tn >= 4, rn >= 4
    H, W = has_t.shape
    best = np.full((H, W), np.inf)
    pad_lab = np.pad(rlab, ((1, 1), (1, 1), (0, 0)))
    pad_has = np.pad(has_r, 1)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            de = np.linalg.norm(tlab - pad_lab[dy:dy + H, dx:dx + W], axis=-1)
            best = np.where(pad_has[dy:dy + H, dx:dx + W], np.minimum(best, de), best)
    t_cell = np.where(np.isfinite(best), np.clip(1 - best / 40.0, 0, 1), 0.0)
    # whole-cell mean colour vs the best neighbouring render cell: a 3 px dot per cell has the right
    # ink colour but the wrong cell colour (red-team #2 "dust", 83–93 before this)
    tw, rw = rgb2lab(tg.mean(axis=(1, 3)) / 255.0), rgb2lab(rg.mean(axis=(1, 3)) / 255.0)
    pad_w = np.pad(rw, ((1, 1), (1, 1), (0, 0)), mode="edge")
    best_w = np.full((H, W), np.inf)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            best_w = np.minimum(best_w, np.linalg.norm(tw - pad_w[dy:dy + H, dx:dx + W], axis=-1))
    t_cell = np.minimum(t_cell, np.clip(1 - best_w / CELL_DE_SCALE, 0, 1))
    near_t = ndimage.binary_dilation(has_t, np.ones((3, 3), bool))
    extra = has_r & ~near_t
    num = (t_cell * tn)[has_t].sum()                      # target content, weighted by pixels
    den = tn[has_t].sum() + rn[extra].sum()               # + unmatched render content
    de_out = np.where(has_t, np.where(np.isfinite(best), best, 100.0), np.where(extra, 100.0, np.nan))
    if den == 0:
        return 1.0, de_out
    return float(num / den), de_out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _font_px(v) -> float:
    try:
        return float(re.sub(r"[^0-9.]", "", str(v)) or 16)
    except ValueError:
        return 16.0


def readable_dom(render_dom: list[dict], rm: np.ndarray) -> list[dict]:
    """DOM text a human can actually see in THIS render: on-screen, ≥ 8 px, not transparent, and with
    ink (content pixels) inside its box. Red-team #1: 1 px / transparent / off-screen text farmed credit."""
    h, w = rm.shape
    keep = []
    for e in render_dom or []:
        if not isinstance(e, dict) or not e.get("text"):
            continue
        if e.get("inked") is False or e.get("onscreen") is False:
            continue
        x, y, bw, bh = (e.get("box") or [0, 0, 0, 0])[:4]
        x0, y0, x1, y1 = max(0, int(x)), max(0, int(y)), min(w, int(x + bw)), min(h, int(y + bh))
        if x1 <= x0 or y1 <= y0 or _font_px(e.get("font_size", 16)) < TEXT_MIN_FONT:
            continue
        if rm[y0:y1, x0:x1].mean() < TEXT_MIN_INK:
            continue
        keep.append(e)
    return keep


def visible_targets(target_texts: list, tm: np.ndarray) -> list:
    """Target strings with ink in the target (drops hidden labels / logo alt text in ground truth)."""
    h, w = tm.shape
    out = []
    for t in target_texts or []:
        if isinstance(t, dict):
            box = t.get("box")
            if isinstance(box, (list, tuple)) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
                x, y, bw, bh = box
                x0, y0, x1, y1 = max(0, int(x)), max(0, int(y)), min(w, int(x + bw)), min(h, int(y + bh))
                if x1 <= x0 or y1 <= y0 or tm[y0:y1, x0:x1].mean() < TEXT_MIN_INK:
                    continue
            if _norm(t.get("text") or ""):
                out.append(t)
            continue
        if isinstance(t, str) and _norm(t):
            out.append(t)
    return out


def _centre(b):
    return (b[0] + b[2] / 2.0, b[1] + b[3] / 2.0)


def _matches(t: str, r: str) -> bool:
    if len(t) < 4:
        return t == r or t in r.split()
    return t in r or difflib.SequenceMatcher(None, t, r).ratio() >= TEXT_MATCH


def text_score(target_texts: list, render_dom: list[dict], width: int | None = None) -> tuple[float, list[str]]:
    """Share of target strings present as readable render text NEAR their design position.

    target_texts: str (position-free) or {"text", "box", "approx"?}; boxes marked approx are position-free.
    Position-aware since red-team r2: a strip of every design string at the top of the page earned full credit.
    """
    targets = []
    for t in target_texts:
        if isinstance(t, dict):
            box = t.get("box") if not t.get("approx") else None
            ok_box = isinstance(box, (list, tuple)) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)
            targets.append((_norm(t.get("text") or ""), box if ok_box else None))
        elif isinstance(t, str):
            targets.append((_norm(t), None))
    targets = [(t, b) for t, b in targets if t]
    if not targets:
        return 1.0, []
    rendered = [(_norm(e.get("text") or ""), e.get("box")) for e in render_dom if isinstance(e, dict)]
    rendered = [(r, b) for r, b in rendered if r]
    near = max(TEXT_NEAR_MIN, TEXT_NEAR_FRAC * (width or 1280))
    missing = []
    for t, tb in targets:
        found = False
        for r, rb in rendered:
            if not _matches(t, r):
                continue
            if tb is None or not (isinstance(rb, (list, tuple)) and len(rb) >= 4):
                found = True
                break
            (tx, ty), (rx, ry) = _centre(tb), _centre(rb[:4])
            # the glyphs can sit anywhere inside their element's box (block elements are often full-width):
            # distance from the design text's centre to the render element's box, 0 if inside
            dx = max(0.0, abs(tx - rx) - rb[2] / 2.0)
            dy = max(0.0, abs(ty - ry) - rb[3] / 2.0)
            if (dx * dx + dy * dy) ** 0.5 <= near:
                found = True
                break
        if not found:
            missing.append(t)
    return 1.0 - len(missing) / len(targets), missing


def diff_regions(tc, rc, de_cells, shape) -> list[dict]:
    """Top regions where target and render disagree, in pixel boxes, biggest first."""
    h, w = shape
    missing = tc & ~ndimage.binary_dilation(rc, np.ones((3, 3), bool))
    extra = rc & ~ndimage.binary_dilation(tc, np.ones((3, 3), bool))
    # colour disagreement upsampled from 16 px cells to the 8 px grid
    up = np.kron(np.nan_to_num(de_cells, nan=0.0) > 15, np.ones((COLOR_CELL // LAYOUT_CELL,) * 2, bool))
    colour = np.zeros_like(tc)
    colour[: up.shape[0], : up.shape[1]] = up[: tc.shape[0], : tc.shape[1]]
    colour &= (tc | rc) & ~missing & ~extra
    out = []
    for kind, m in (("missing", missing), ("extra", extra), ("color", colour)):
        lab, n = ndimage.label(ndimage.binary_closing(m, np.ones((3, 3), bool)))
        for sl in ndimage.find_objects(lab):
            y0, y1 = sl[0].start * LAYOUT_CELL, min(sl[0].stop * LAYOUT_CELL, h)
            x0, x1 = sl[1].start * LAYOUT_CELL, min(sl[1].stop * LAYOUT_CELL, w)
            out.append({"kind": kind, "box": [x0, y0, x1 - x0, y1 - y0], "area": (x1 - x0) * (y1 - y0)})
    out.sort(key=lambda d: -d["area"])
    return out[:TOP_REGIONS]


def _offset(tm: np.ndarray, rm: np.ndarray, axis: int) -> int:
    """Shift (px) along one axis that best aligns the render's content profile to the target's."""
    tp, rp = tm.mean(axis=1 - axis), rm.mean(axis=1 - axis)
    best, best_dy = -1.0, 0
    for dy in range(-OFFSET_MAX, OFFSET_MAX + 1, 2):
        a = tp[max(0, dy): len(tp) + min(0, dy)]
        b = rp[max(0, -dy): len(rp) + min(0, -dy)]
        v = float(np.minimum(a, b).sum())
        if v > best + 1e-9:
            best, best_dy = v, dy
    return best_dy


def _shift(img: np.ndarray, dy: int, fill: np.ndarray, dx: int = 0) -> np.ndarray:
    """Content moved by (dy down, dx right) px, vacated pixels filled with the background."""
    out = np.empty_like(img)
    out[:] = fill
    h, w = img.shape[:2]
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = img[ys, xs]
    return out


def _score_aligned(target, render, bg, rbg, tm, text) -> dict:
    rm = content_mask(render, rbg)
    tc, rc = cells(tm, LAYOUT_CELL), cells(rm, LAYOUT_CELL)
    structure = structure_score(target, render)
    layout, precision, recall = layout_score(tc, rc, coverage(tm, LAYOUT_CELL), coverage(rm, LAYOUT_CELL))
    content_color, de = color_score(target, render, tm, rm)
    bg_de = float(np.linalg.norm(rgb2lab(bg / 255.0) - rgb2lab(rbg / 255.0)))
    bg_match = float(np.clip(1 - bg_de / BG_DE_SCALE, 0, 1))
    # equal halves, not area-weighted: area weighting let a wrong CTA colour cost ~3 points (red-team #6)
    # no content on either side → colour is just the background (red-team r2 #8: free 1.0 before)
    color = bg_match if not (tm.any() or rm.any()) else 0.5 * bg_match + 0.5 * content_color
    comps = {"structure": structure, "layout": layout}
    weights = dict(WEIGHTS)
    missing_text: list[str] = []
    text_factor = 1.0
    if text is not None:
        comps["text"], missing_text = text
        text_factor = TEXT_FLOOR + (1 - TEXT_FLOOR) * comps["text"]
    s = 100.0 * (COLOR_FLOOR + (1 - COLOR_FLOOR) * color) * text_factor * sum(weights[k] * comps[k] for k in weights)
    comps.update(color=color, content_color=content_color, bg_match=bg_match)
    return {
        "score": s,
        "components": {k: round(v, 4) for k, v in comps.items()},
        "weights": weights,
        "layout_precision": round(precision, 4), "layout_recall": round(recall, 4),
        "background": {"target": [int(x) for x in bg], "render": [int(x) for x in rbg]},
        "regions": diff_regions(tc, rc, de, target.shape[:2]),
        "missing_text": missing_text[:20],
    }


def _check(a: np.ndarray, name: str) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    if a.ndim != 3 or a.shape[2] != 3:
        raise ValueError(f"{name}: expected HxWx3 RGB, got shape {a.shape}")
    if min(a.shape[:2]) < MIN_SIDE:
        raise ValueError(f"{name}: too small {a.shape[1]}x{a.shape[0]}")
    if not np.isfinite(a).all() or a.min() < 0 or a.max() > 255:
        raise ValueError(f"{name}: values must be finite and within 0..255")
    return a


def score_pair(target: np.ndarray, render: np.ndarray, target_texts=None, render_dom=None, *,
               notext: np.ndarray | None = None, coded: np.ndarray | None = None) -> dict:
    """Score one breakpoint. Also tries the best global vertical offset (≤ 32 px) with a 0.6 %/px
    penalty, so "perfect but 20 px low" is not ranked below junk (red-team #5)."""
    target, render = _check(target, "target"), _check(render, "render")
    if target.shape != render.shape:
        return {"score": 0.0, "error": f"size mismatch target {target.shape[:2]} vs render {render.shape[:2]}"}
    bg, rbg = background(target), background(render)
    tm = content_mask(target, bg)
    text = None   # (score, missing) or None = no comparable text → weight redistributed
    if target_texts is not None and render_dom is not None:
        targets = visible_targets(target_texts, tm)
        if targets:
            if notext is not None and coded is not None:
                seen = _readable.readable_entries(render_dom, render, _check(notext, "notext"), _check(coded, "coded"))
            else:  # legacy renders without the extra passes: CSS flags + ink in box
                seen = readable_dom(render_dom, content_mask(render, rbg))
            text = text_score(targets, seen, target.shape[1])
    res = _score_aligned(target, render, bg, rbg, tm, text)
    res["offset_px"] = [0, 0]
    rm0 = content_mask(render, rbg)
    dy, dx = _offset(tm, rm0, 0), _offset(tm, rm0, 1)
    for oy, ox in {(dy, 0), (0, dx), (dy, dx)} - {(0, 0)}:
        alt = _score_aligned(target, _shift(render, oy, rbg, ox), bg, rbg, tm, text)
        alt["score"] *= max(0.0, 1 - OFFSET_PENALTY * (abs(oy) + abs(ox)))
        if alt["score"] > res["score"]:
            res = alt
            res["offset_px"] = [oy, ox]
    res["score"] = round(res["score"], 2)
    return res


def score_run(targets: Path, renders: Path, texts: Path | None = None) -> dict:
    per = {}
    for bp in BREAKPOINTS:
        t, r = load(targets / f"{bp}.png"), load(renders / f"{bp}.png")
        tt = rd = None
        if texts is not None and (texts / f"{bp}.text.json").exists() and (renders / f"{bp}.dom.json").exists():
            tt = json.loads((texts / f"{bp}.text.json").read_text())   # str or {"text", "box"}
            rd = json.loads((renders / f"{bp}.dom.json").read_text())
        aux = {k: load(renders / f"{bp}.{k}.png") for k in ("notext", "coded") if (renders / f"{bp}.{k}.png").exists()}
        per[bp] = score_pair(t, r, tt, rd, **aux) if len(aux) == 2 else score_pair(t, r, tt, rd)
    scores = [per[bp]["score"] for bp in BREAKPOINTS]
    worst = BREAKPOINTS[int(np.argmin(scores))]
    return {"match": round(min(scores), 2), "mean": round(float(np.mean(scores)), 2), "worst": worst, "breakpoints": per}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True, type=Path)
    ap.add_argument("--renders", required=True, type=Path)
    ap.add_argument("--texts", type=Path)
    a = ap.parse_args()
    json.dump(score_run(a.targets, a.renders, a.texts), sys.stdout)
