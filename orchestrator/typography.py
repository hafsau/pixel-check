"""Typography inference from a measured text line, using Inter's real glyph metrics.

For one OCR line (its text and tight ink box) and the design image:
- weight: render the string in each Inter weight and pick the one whose glyph stroke thickness (ink px / half
  the edge px) matches the design's strokes;
- font size: the line's ink height ÷ that string's exact ink height in Inter (per string, not an average);
- letter-spacing: whatever width is left over after size and weight, per gap between characters (designs with
  tight headings were wrapping onto an extra line before this).
Calibration (orchestrator/typo_calib.json, from sandbox/calib.mjs renders): OCR ink boxes ≈ 1.01 × the font's ink
height and 0.99 × its ink width (n = 198 strings, sizes 12–48, weights 400/600).
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = Path(__file__).resolve().parent
FONT_DIR = HERE.parent / "var" / "fonts"
WEIGHTS = (400, 500, 600, 700)
CAL = json.loads((HERE / "typo_calib.json").read_text())


def _ensure_fonts():
    if all((FONT_DIR / f"inter-{w}.ttf").exists() for w in WEIGHTS):
        return
    from fontTools.ttLib import TTFont
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for w in WEIGHTS:
        f = TTFont(HERE.parent / "sandbox" / "fonts" / f"inter-latin-{w}-normal.woff2")
        f.flavor = None
        f.save(FONT_DIR / f"inter-{w}.ttf")


@functools.lru_cache(maxsize=None)
def _font(w: int, size: int):
    _ensure_fonts()
    return ImageFont.truetype(str(FONT_DIR / f"inter-{w}.ttf"), size)


@functools.lru_cache(maxsize=4096)
def metrics(text: str, w: int) -> tuple[float, float, float]:
    """(ink height, ink width, ink top below the em-box top) of `text` in Inter weight w, per 1 px of font size."""
    f = _font(w, 100)
    m = f.getmask(text)
    bb = m.getbbox()
    if not bb:
        return 0.0, 0.0, 0.0
    x0, y0, x1, y1 = f.getbbox(text)
    return (y1 - y0) / 100.0, (bb[2] - bb[0]) / 100.0, y0 / 100.0


def _stroke(mask: np.ndarray) -> float | None:
    if mask.sum() < 20:
        return None
    edge = mask & ~ndimage.binary_erosion(mask)
    return float(mask.sum() / max(edge.sum() / 2.0, 1))


def stroke_in_image(img: np.ndarray, box) -> float | None:
    x, y, w, h = [int(v) for v in box[:4]]
    patch = img[max(0, y - 1):y + h + 1, max(0, x - 1):x + w + 1]
    if patch.size == 0:
        return None
    ring = np.concatenate([patch[0], patch[-1], patch[:, 0], patch[:, -1]])
    d = np.linalg.norm(patch - np.median(ring, axis=0), axis=-1)
    if d.max() < 30:
        return None
    # ≥ 50 % of full ink contrast — the same coverage threshold as the reference rendering (mask > 128)
    return _stroke(d >= 0.5 * np.percentile(d, 99))


@functools.lru_cache(maxsize=4096)
def _stroke_rendered(text: str, w: int, size: int) -> float | None:
    f = _font(w, size)
    bb = f.getbbox(text)
    im = Image.new("L", (bb[2] + 8, bb[3] + 8), 0)
    ImageDraw.Draw(im).text((4, 4), text, fill=255, font=f)
    return _stroke(np.asarray(im) > 128)


def infer(text: str, box, img: np.ndarray | None = None, weight_hint=None) -> dict:
    """{'size_px', 'weight', 'tracking_em', 'top_em'} for one single-line OCR text with ink box [x, y, w, h]."""
    t = text.strip()
    x, y, bw, bh = box
    if len(t) < 1 or bh <= 0:
        return {}
    underline = False
    if img is not None and bh >= 8:
        # underline: a near-full-width ink run in the bottom rows, separate from the glyphs → measure without it
        xi, yi = int(x), int(y)
        patch = img[max(0, yi - 1):yi + int(bh) + 2, max(0, xi - 1):xi + int(bw) + 2]
        ring = np.concatenate([patch[0], patch[-1], patch[:, 0], patch[:, -1]])
        d = np.linalg.norm(patch - np.median(ring, axis=0), axis=-1)
        ink = d >= 0.5 * np.percentile(d, 99) if d.max() > 30 else np.zeros(d.shape, bool)
        rows = ink.mean(axis=1)
        bottom = [k for k in range(len(rows) - 1, max(len(rows) - 5, 0), -1) if rows[k] >= 0.8]
        if bottom:
            top_of_line = min(bottom)
            gap = top_of_line - 1
            while gap > 0 and rows[gap] < 0.05:
                gap -= 1
            new_h = gap - 0 + 1 - 1   # rows above the gap, relative to the patch (patch starts 1 px above)
            if new_h >= 5:
                bh = new_h
                underline = True
                box = [x, y, bw, bh]
    observed = stroke_in_image(img, box) if img is not None and len(t) >= 2 else None
    best = None
    for w in WEIGHTS:
        hr, wr, top = metrics(t, w)
        if hr <= 0:
            continue
        fs = bh / (CAL["h_ratio"] * hr)
        if observed is not None and fs >= 10:
            sr = _stroke_rendered(t, w, max(8, int(round(fs))))
            err = abs(np.log(observed / sr)) if sr else 9.0
        else:
            err = 0.0 if w == (weight_hint or 400) else 1.0
        if best is None or err < best[0]:
            best = (err, w, fs, wr, top)
    _, w, fs, wr, top = best
    expected_w = CAL["w_ratio"] * wr * fs
    gaps = max(len(t) - 1, 1)
    tracking = (bw - expected_w) / gaps / fs if len(t) >= 4 else 0.0
    tracking = float(np.clip(tracking, -0.08, 0.15))
    if abs(tracking) < 0.006:
        tracking = 0.0
    return {"size_px": int(round(fs)), "weight": w, "tracking_em": round(tracking, 3), "top_em": round(top, 3),
            "underline": underline}
