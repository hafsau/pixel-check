"""Check diagnostics (Oct 13, council review of the Lovable build): explain a check's score, never change it.

The score (sandbox/score.py) stays the single number. These are readings beside it, computed on the server from what
the check already has — the design frames and their measured texts, the build's captures and its DOM:
- text the scorer could not credit: missing from the build, moved (how far), below the first screen, or near its spot
  but unreadable (covered, e.g. by a platform badge, or too faint). "Missing" only when the text is not there at all.
- drift profile: the build's vertical offset band by band down the screen and the page's vertical scale. The scorer
  aligns the whole screen once (≤ 32 px), so drift that grows down the page costs points row after row.
- named differences: the font family the build uses vs the design's, and its text size vs the design's.
- points lost per factor (layout, colour, text, alignment shift), splitting 100 − score.
Every function tolerates missing or odd input: diagnostics are extras and never fail a check.
"""
from __future__ import annotations

import difflib
import io
import math
import re
from collections import Counter

import numpy as np

TEXT_MATCH = 0.85                          # as sandbox/score.py
TEXT_NEAR_MIN, TEXT_NEAR_FRAC = 96.0, 0.15
COLOR_FLOOR, TEXT_FLOOR, OFFSET_PENALTY = 0.25, 0.50, 0.006
WEIGHTS = {"structure": 0.57, "layout": 0.43}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _matches(t: str, r: str) -> bool:
    """As the scorer, except short targets match whole words only ("days" is not in "sundays")."""
    if len(t) <= 4:
        return t == r or t in r.split()
    return t in r or difflib.SequenceMatcher(None, t, r).ratio() >= TEXT_MATCH


def _centre(b) -> tuple[float, float]:
    return (b[0] + b[2] / 2.0, b[1] + b[3] / 2.0)


def _box(b) -> list | None:
    return list(b[:4]) if isinstance(b, (list, tuple)) and len(b) >= 4 and all(isinstance(v, (int, float)) for v in b[:4]) else None


def _px(v) -> float | None:
    try:
        return float(re.sub(r"[^0-9.]", "", str(v)))
    except ValueError:
        return None


# ------------------------------------------------------------------------------------------------ text

def text_status(missing: list[str], design: list[dict], dom: list[dict], viewport: tuple[int, int]) -> list[dict]:
    """Each text the scorer did not credit → missing | moved (dy, dx) | below (the first screen) | unreadable."""
    w, h = viewport
    near = max(TEXT_NEAR_MIN, TEXT_NEAR_FRAC * w)
    rendered = [(_norm(e.get("text")), _box(e.get("box"))) for e in dom or [] if isinstance(e, dict)]
    out = []
    for m in missing or []:
        t = _norm(m)
        d = next((x for x in design or [] if _norm(x.get("text")) == t), None) or \
            next((x for x in design or [] if t and t in _norm(x.get("text"))), None)
        db = _box(d.get("box")) if d else None
        cands = [b for r, b in rendered if b and r and _matches(t, r)]
        if not cands:
            out.append({"text": m, "status": "missing"})
            continue
        if db is None:
            out.append({"text": m, "status": "moved"})
            continue
        (tx, ty) = _centre(db)

        def dist(b):
            cx, cy = _centre(b)
            return math.hypot(max(0.0, abs(tx - cx) - b[2] / 2), max(0.0, abs(ty - cy) - b[3] / 2))
        b = min(cands, key=dist)
        cx, cy = _centre(b)
        dy, dx = round(cy - ty), round(cx - tx)
        if b[1] >= h:
            out.append({"text": m, "status": "below", "dy": dy, "dx": dx})
        elif dist(b) <= near:
            out.append({"text": m, "status": "unreadable"})
        else:
            out.append({"text": m, "status": "moved", "dy": dy, "dx": dx})
    return out


# ------------------------------------------------------------------------------------------------ drift

def _edges(img: np.ndarray) -> np.ndarray:
    g = img[..., :3].astype(np.float32).mean(axis=2) if img.ndim == 3 else img.astype(np.float32)
    g = g[: g.shape[0] // 2 * 2, : g.shape[1] // 2 * 2].reshape(g.shape[0] // 2, 2, g.shape[1] // 2, 2).mean(axis=(1, 3))
    gy, gx = np.zeros_like(g), np.zeros_like(g)
    gy[1:-1] = g[2:] - g[:-2]
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    return np.minimum(np.hypot(gx, gy), 64.0) / 64.0


def _robust_line(ys: np.ndarray, ds: np.ndarray):
    """Theil–Sen: the median of pairwise slopes, so one wrong band cannot tilt the line it is judged against."""
    slopes = [(ds[j] - ds[i]) / (ys[j] - ys[i]) for i in range(len(ys)) for j in range(i + 1, len(ys)) if ys[j] != ys[i]]
    k = float(np.median(slopes)) if slopes else 0.0
    c = float(np.median(ds - k * ys))
    return lambda y: k * y + c


def drift(design: np.ndarray, build: np.ndarray, bands: int = 6, max_shift: float = 0.35) -> dict | None:
    """Vertical offset of the build, band by band (design rows y0–y1 → where they best match in the build), and the
    vertical scale from a line through the band offsets (1.0 = same spacing; 0.81 = 19 % tighter). None if the
    images differ in size. A band with too little content to place reads dy None."""
    if design is None or build is None or design.shape[:2] != build.shape[:2]:
        return None
    ed, eb = _edges(design), _edges(build)
    H = ed.shape[0]
    step = H / bands
    reach = int(max_shift * H)
    pad = np.zeros((reach, eb.shape[1]), eb.dtype)
    ebp = np.vstack([pad, eb, pad])          # content shifted off the screen meets nothing and costs fully
    out, pts = [], []
    for i in range(bands):
        y0, y1 = int(round(i * step)), int(round((i + 1) * step))
        band = ed[y0:y1]
        rows = band.sum(axis=1)
        if rows.sum() < 0.004 * band.size:         # (nearly) blank band: nothing to place
            out.append({"y0": y0 * 2, "y1": y1 * 2, "dy": None})
            continue
        best, best_cost = None, None
        mass = float(band.sum())
        for dy in range(-reach, reach + 1):
            other = ebp[reach + y0 + dy:reach + y1 + dy]
            # 0 = the band's edges sit exactly there in the build; 1 = nothing in common (empty rows score 1, not 0)
            cost = float(np.abs(band - other).sum()) / (mass + float(other.sum()) + 1e-6) + 1e-4 * abs(dy)
            if best_cost is None or cost < best_cost:
                best, best_cost = dy, cost
        if best is None:
            out.append({"y0": y0 * 2, "y1": y1 * 2, "dy": None})
            continue
        centre = y0 + float((rows * np.arange(len(rows))).sum() / rows.sum())
        out.append({"y0": y0 * 2, "y1": y1 * 2, "dy": best * 2})
        pts.append((len(out) - 1, centre * 2, best * 2))
    # a band can lock onto a look-alike row (repeated cards) or onto other content when its own left the screen:
    # drop the band furthest off the line while it is > max(16 px, 3 × the median miss), keep ≥ 3, mark it unsure
    while len(pts) >= 4:
        ys, ds = np.array([p[1] for p in pts]), np.array([p[2] for p in pts])
        res = np.abs(ds - _robust_line(ys, ds)(ys))
        worst = int(res.argmax())
        if res[worst] <= max(16.0, 3 * float(np.median(res))):
            break
        out[pts[worst][0]].update(dy=None, unsure=True)
        pts.pop(worst)
    scale = None
    if len(pts) >= 2:
        ys, ds = np.array([p[1] for p in pts]), np.array([p[2] for p in pts])
        if np.ptp(ys) > 0:
            scale = round(1.0 + float(np.polyfit(ys, ds, 1)[0]), 3)
    return {"bands": out, "scale": scale}


# ------------------------------------------------------------------------------------------------ named differences

def font_finding(design_fonts: dict | None, dom: list[dict]) -> dict | None:
    """{"design", "build"} when the build's main font family (by amount of text) is not the design's body font."""
    want = (design_fonts or {}).get("body") if isinstance(design_fonts, dict) else None
    if not want:
        return None
    count = Counter()
    for e in dom or []:
        if isinstance(e, dict) and e.get("font_family") and (e.get("text") or "").strip():
            count[e["font_family"].strip()] += len(e["text"].strip())
    if not count:
        return None
    got = count.most_common(1)[0][0]
    return None if got.lower() == str(want).lower() else {"design": want, "build": got}


def text_size_ratio(design: list[dict], dom: list[dict], min_matches: int = 3) -> float | None:
    """Median of build font size / design text size over texts found in both (≥ 3), e.g. 0.82 = 18 % smaller."""
    sizes = {}
    for e in dom or []:
        if isinstance(e, dict):
            px = _px(e.get("font_size"))
            if px:
                sizes.setdefault(_norm(e.get("text")), px)
    ratios = []
    for d in design or []:
        want = d.get("size_px")
        got = sizes.get(_norm(d.get("text")))
        if isinstance(want, (int, float)) and want > 0 and got:
            ratios.append(got / want)
    return round(float(np.median(ratios)), 2) if len(ratios) >= min_matches else None


# ------------------------------------------------------------------------------------------------ points lost

def points_lost(bp: dict) -> dict | None:
    """100 − score split over the score's factors (sandbox/score.py: colour × text × spatial × alignment shift),
    in proportion to how much each factor shrinks the product (log share)."""
    c = (bp or {}).get("components") if isinstance(bp, dict) else None
    if not isinstance(c, dict) or "error" in bp:
        return None
    w = bp.get("weights") or WEIGHTS
    colour = c.get("color", c.get("content_color", 1.0))
    factors = {
        "layout": sum(w.get(k, 0) * float(c.get(k, 1.0)) for k in ("structure", "layout")),
        "color": COLOR_FLOOR + (1 - COLOR_FLOOR) * float(colour),
        "text": TEXT_FLOOR + (1 - TEXT_FLOOR) * float(c["text"]) if c.get("text") is not None else 1.0,
        "offset": max(1e-6, 1 - OFFSET_PENALTY * sum(abs(v) for v in (bp.get("offset_px") or [0, 0])[:2])),
    }
    logs = {k: -math.log(max(1e-6, min(1.0, f))) for k, f in factors.items()}
    total = sum(logs.values())
    gap = max(0.0, 100.0 - float(bp.get("score") or 0))
    if total <= 0 or gap <= 0:
        return {k: 0 for k in factors}
    return {k: max(0.0, round(gap * v / total, 2)) for k, v in logs.items()}      # max: no "-0.0" in the JSON


# ------------------------------------------------------------------------------------------------ all of it

def _array(img) -> np.ndarray | None:
    if isinstance(img, np.ndarray):
        return img
    if isinstance(img, (bytes, bytearray)):
        from PIL import Image
        return np.asarray(Image.open(io.BytesIO(img)).convert("RGB"))
    return None


def diagnose(report: dict, *, frames: dict, build: dict, design_texts: dict, dom: dict, fonts: dict | None) -> dict:
    """{bp: {"text", "drift", "lost", "font", "text_size"}} for each scored size; a size that cannot be read is left out."""
    out = {}
    for bp, r in ((report or {}).get("breakpoints") or {}).items():
        if not isinstance(r, dict):
            continue
        try:
            d, b = _array(frames.get(bp)), _array(build.get(bp))
            view = (b.shape[1], b.shape[0]) if b is not None else (1280, 800)
            sec = {"text": text_status(r.get("missing_text") or [], design_texts.get(bp) or [], dom.get(bp) or [], view),
                   "drift": drift(d, b) if d is not None and b is not None else None,
                   "lost": points_lost(r),
                   "font": font_finding(fonts, dom.get(bp) or []),
                   "text_size": text_size_ratio(design_texts.get(bp) or [], dom.get(bp) or [])}
        except Exception:                      # an extra: never fail the check over it
            continue
        out[bp] = sec
    return out
