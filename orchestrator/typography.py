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
import os
import threading
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = Path(__file__).resolve().parent
FONT_DIR = HERE.parent / "var" / "fonts"
WEIGHTS = (400, 500, 600, 700)
CAL = json.loads((HERE / "typo_calib.json").read_text())
# the font catalogue (Oct 12): 16 open-licence families, their latin woff2 files in sandbox/fonts
CATALOG = json.loads((HERE.parent / "sandbox" / "fonts" / "catalog.json").read_text())
DEFAULT = "Inter"


_FONT_LOCK = threading.Lock()


def _ensure_fonts():
    """Inter TTFs from the woff2 files, once: under a lock and written atomically (threads reading a half-written TTF
    raised 'unknown file format'). The API image builds them at build time (orchestrator.preflight --static)."""
    if all((FONT_DIR / f"inter-{w}.ttf").exists() for w in WEIGHTS):
        return
    with _FONT_LOCK:
        if all((FONT_DIR / f"inter-{w}.ttf").exists() for w in WEIGHTS):
            return
        from fontTools.ttLib import TTFont
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        for w in WEIGHTS:
            dest = FONT_DIR / f"inter-{w}.ttf"
            if dest.exists():
                continue
            f = TTFont(HERE.parent / "sandbox" / "fonts" / f"inter-latin-{w}-normal.woff2")
            f.flavor = None
            tmp = FONT_DIR / f".inter-{w}.{os.getpid()}.{threading.get_ident()}.tmp"
            f.save(tmp)
            os.replace(tmp, dest)


def weights(family: str = DEFAULT) -> tuple[int, ...]:
    return tuple(CATALOG[family]["weights"]) if family in CATALOG else WEIGHTS


def _ttf(family: str, w: int) -> Path:
    """A catalogue face as a TTF (PIL cannot read woff2), converted once, atomically."""
    if family == DEFAULT:
        _ensure_fonts()
        return FONT_DIR / f"inter-{w}.ttf"
    slug = CATALOG[family]["slug"]
    dest = FONT_DIR / f"{slug}-{w}.ttf"
    if dest.exists():
        return dest
    with _FONT_LOCK:
        if not dest.exists():
            from fontTools.ttLib import TTFont
            FONT_DIR.mkdir(parents=True, exist_ok=True)
            f = TTFont(HERE.parent / "sandbox" / "fonts" / f"{slug}-latin-{w}-normal.woff2")
            f.flavor = None
            tmp = FONT_DIR / f".{slug}-{w}.{os.getpid()}.{threading.get_ident()}.tmp"
            f.save(tmp)
            os.replace(tmp, dest)
    return dest


@functools.lru_cache(maxsize=None)
def _font(w: int, size: int, family: str = DEFAULT):
    return ImageFont.truetype(str(_ttf(family, w)), size)


@functools.lru_cache(maxsize=8192)
def metrics(text: str, w: int, family: str = DEFAULT) -> tuple[float, float, float]:
    """(ink height, ink width, ink top below the em-box top) of `text` in `family` weight w, per 1 px of font size."""
    f = _font(w, 100, family)
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


@functools.lru_cache(maxsize=8192)
def _stroke_rendered(text: str, w: int, size: int, family: str = DEFAULT) -> float | None:
    f = _font(w, size, family)
    bb = f.getbbox(text)
    im = Image.new("L", (bb[2] + 8, bb[3] + 8), 0)
    ImageDraw.Draw(im).text((4, 4), text, fill=255, font=f)
    return _stroke(np.asarray(im) > 128)


def infer(text: str, box, img: np.ndarray | None = None, weight_hint=None, family: str = DEFAULT) -> dict:
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
    for w in weights(family):
        hr, wr, top = metrics(t, w, family)
        if hr <= 0:
            continue
        fs = bh / (CAL["h_ratio"] * hr)
        if observed is not None and fs >= 10:
            sr = _stroke_rendered(t, w, max(8, int(round(fs))), family)
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
            "underline": underline, "font": family}


_NORM_H = 32


def _ink_gray(img: np.ndarray, box) -> np.ndarray | None:
    """A word's ink as grey levels 0–1 (contrast against its own surround), cropped to the ink."""
    x, y, w, h = [int(v) for v in box[:4]]
    p = img[max(0, y - 1):y + h + 1, max(0, x - 1):x + w + 1]
    if p.size == 0:
        return None
    ring = np.concatenate([p[0], p[-1], p[:, 0], p[:, -1]])
    d = np.linalg.norm(p - np.median(ring, axis=0), axis=-1)
    if d.max() < 30:
        return None
    d = d / d.max()
    ys, xs = np.nonzero(d > 0.5)
    return d[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(ys) else None


@functools.lru_cache(maxsize=32768)
def _rendered_gray(text: str, w: int, size: int, family: str) -> np.ndarray | None:
    """Rendered at 4× and box-filtered down: close to Chromium's unhinted text (PIL hints small glyphs, which made
    look-alike families win lines of Inter captures)."""
    f = _font(w, size * 4, family)
    bb = f.getbbox(text)
    im = Image.new("L", (bb[2] + 32, bb[3] + 32), 0)
    ImageDraw.Draw(im).text((16, 16), text, fill=255, font=f)
    im = im.resize((max(1, im.size[0] // 4), max(1, im.size[1] // 4)), Image.BOX)
    a = np.asarray(im, np.float32) / 255
    ys, xs = np.nonzero(a > 0.5)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(ys) else None


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    """Grey-level correlation of two glyph images at a common height (b stretched onto a's aspect: size and tracking
    factored out, letter shapes compared)."""
    wa = max(4, int(round(a.shape[1] * _NORM_H / a.shape[0])))
    A = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((wa, _NORM_H), Image.BILINEAR), np.float32)
    B = np.asarray(Image.fromarray((b * 255).astype(np.uint8)).resize((wa, _NORM_H), Image.BILINEAR), np.float32)
    A -= A.mean()
    B -= B.mean()
    return float((A * B).sum() / (np.sqrt((A * A).sum() * (B * B).sum()) + 1e-6))


def family_scores(text: str, box, img: np.ndarray, families=None, words=None, max_words: int = 3) -> dict[str, float]:
    """How well each catalogue family's glyphs match this line: per clean word (letters only, ≥ 3), the best weight's
    grey-level correlation with the design's ink, averaged. Whole OCR lines were noisy (icons in the box, misread
    letters); words are not (Oct 12)."""
    import re
    ws_ = [w for w in (words or []) if re.fullmatch(r"[A-Za-z]{3,}", w.get("text", ""))]
    if not ws_ and re.fullmatch(r"[A-Za-z]{3,}", text.strip()):
        ws_ = [{"text": text.strip(), "box": box}]
    ws_ = sorted(ws_, key=lambda w: -len(w["text"]))[:max_words]
    inks = [(w["text"], w["box"], _ink_gray(img, w["box"])) for w in ws_]
    inks = [x for x in inks if x[2] is not None]
    if not inks:
        return {}
    out = {}
    for fam in families or CATALOG:
        ss = []
        for t, b, a in inks:
            best = -1.0
            for w in weights(fam):
                hr, _, _ = metrics(t, w, fam)
                if hr <= 0:
                    continue
                fs = max(8, int(round(b[3] / (CAL["h_ratio"] * hr))))
                r = _rendered_gray(t, w, fs, fam)
                if r is not None:
                    best = max(best, _corr(a, r))
            ss.append(best)
        out[fam] = float(np.mean(ss))
    return out


def page_families(votes: list[dict], mono_lines: int = 3, display_px: int = 40, margin: float = 0.04,
                  display_margin: float = 0.1, body_margin: float = 0.02) -> dict:
    """Per-line family scores → the page's families. The body family has the best total score over all lines.
    Pages mix a body face with a monospace face or a display headline face — not two look-alike text sans (those
    single wins were noise on Inter captures). So another family is kept only when it is monospace and clearly
    wins (≥ margin) ≥ mono_lines lines, or clearly wins (≥ display_margin) a display-size line. Another body face must
    beat Inter by ≥ body_margin per voting line."""
    totals: dict[str, float] = {}
    for v in votes:
        for f, sc in (v.get("scores") or {}).items():
            totals[f] = totals.get(f, 0.0) + sc
    if not totals:
        return {"body": DEFAULT, "kept": [DEFAULT]}
    body = max(totals, key=totals.get)
    n = sum(1 for v in votes if v.get("scores"))
    if body != DEFAULT and DEFAULT in totals and totals[body] - totals[DEFAULT] < body_margin * n:
        body = DEFAULT                # little evidence against the default (a few short lines): stay with Inter
    mono_wins: dict[str, int] = {}
    display: set[str] = set()
    for v in votes:
        f, sc = v.get("winner"), v.get("scores") or {}
        if not f or f == body:
            continue
        lead = sc.get(f, 0) - sc.get(body, 0)
        if (CATALOG.get(f) or {}).get("mono") and lead >= margin:
            mono_wins[f] = mono_wins.get(f, 0) + 1
        if (v.get("size_px") or 0) >= display_px and lead >= display_margin:
            display.add(f)
    kept = [body] + sorted({f for f, n in mono_wins.items() if n >= mono_lines} | display)
    return {"body": body, "kept": kept}
