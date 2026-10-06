"""Soft box shadows measured from pixels: the darkening beside a block → a CSS box-shadow (0, y, blur, rgba black).

Browsers draw `box-shadow: 0 y blur rgba(0,0,0,a)` as the box shifted down by y, blurred with a Gaussian of
sigma = blur / 2, at opacity a. Across a side of the box, `d` px outside its edge, that is a·(1 − Φ((d − e)/σ)) with
e = y below, −y above and 0 at the sides. The profile is read in the middle of each side (corners mix two sides),
as the median darkening 1 − pixel / background, and fitted by grid search (opacity by least squares per grid point).
"""
from __future__ import annotations

import math

import numpy as np

D_MAX = 110
from scipy.special import ndtr as _PHI      # the standard normal CDF, vectorised


def _profiles(img: np.ndarray, box, bg: np.ndarray) -> dict:
    H, W, _ = img.shape
    x, y, w, h = [int(v) for v in box]
    bgv = np.maximum(bg.astype(np.float32), 1.0)
    def dark(px):    # a low percentile: text and shapes crossing the halo are darker than the shadow beneath them
        v = float(np.clip(1 - np.percentile((px.astype(np.float32) / bgv).mean(axis=-1), 70), 0, 1))
        return v if v <= 0.5 else np.nan          # still very dark: content, not a shadow — left out of the fit
    cx0, cx1 = x + w // 4, x + 3 * w // 4
    cy0, cy1 = y + h // 4, y + 3 * h // 4
    out = {}
    if y + h + 2 < H:
        out["bottom"] = [dark(img[y + h + d, cx0:cx1]) for d in range(1, min(D_MAX, H - y - h - 1))]
    if y > 2:
        out["top"] = [dark(img[y - d, cx0:cx1]) for d in range(1, min(D_MAX, y))]
    if x > 2:
        out["left"] = [dark(img[cy0:cy1, x - d]) for d in range(1, min(D_MAX, x))]
    if x + w + 2 < W:
        out["right"] = [dark(img[cy0:cy1, x + w + d]) for d in range(1, min(D_MAX, W - x - w - 1))]
    return {k: np.array(v) for k, v in out.items() if len(v) >= 12}


def fit_shadow(img: np.ndarray, box, bg: np.ndarray) -> dict | None:
    """→ {"y", "blur", "alpha"} or None (no soft shadow: too faint, too small a box, or a hard edge)."""
    if min(box[2], box[3]) < 40:
        return None
    prof = _profiles(img, box, bg)
    if not prof or max(float(np.nanmax(p[:6], initial=0)) for p in prof.values()) < 0.02:
        return None
    ok = {k: ~np.isnan(p) for k, p in prof.items()}
    prof = {k: np.nan_to_num(p) for k, p in prof.items()}
    best = None
    for blur in range(4, 124, 4):
        sig = blur / 2
        for oy in range(0, 82, 2):
            num = den = 0.0
            models = {}
            for side, p in prof.items():
                d = np.arange(1, len(p) + 1, dtype=np.float32)
                e = {"bottom": oy, "top": -oy}.get(side, 0)
                m = (1 - _PHI((d - e) / sig)) * ok[side]
                models[side] = m
                num += float((m * p).sum())
                den += float((m * m).sum())
            if den <= 0:
                continue
            a = max(0.0, min(1.0, num / den))
            err = sum(float((((p - a * models[s]) * ok[s]) ** 2).sum()) for s, p in prof.items())
            if best is None or err < best[0]:
                best = (err, oy, blur, a)
    if best is None:
        return None
    err, oy, blur, a = best
    n = sum(int(m.sum()) for m in ok.values())
    total = sum(float(((p * ok[k]) ** 2).sum()) for k, p in prof.items())
    if a < 0.03 or total <= 0 or err / total > 0.35 or blur <= 4 and a > 0.3:
        return None              # faint, badly explained (a step, not a fade), or a hard line
    return {"y": int(oy), "blur": int(blur), "alpha": round(a, 2), "rms": round(math.sqrt(err / n), 4)}


def shadow_class(s: dict | None) -> str:
    if not s:
        return "shadow-none"
    return f"shadow-[0_{s['y']}px_{s['blur']}px_rgba(0,0,0,{s['alpha']:g})]"
