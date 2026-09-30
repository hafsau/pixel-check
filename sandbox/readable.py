"""Which rendered text can a human actually read? Decided by pixels, not CSS.

render.mjs screenshots every breakpoint twice: normally and with every glyph transparent. A DOM text
element is readable only if enough pixels inside its box differ between the two. This one test covers
occlusion (text behind an opaque element), clip-path, filter:opacity(0), zero-height overflow, text the
colour of its background, blend modes, 1 px / transparent text and off-screen text (red-team r1 #1, r2 #1–2).
"""
from __future__ import annotations

import re

import numpy as np

CHANGE_THRESHOLD = 24.0      # RGB distance for a pixel to count as "painted by text"
PX_PER_CHAR_PER_FONTPX = 0.3  # readable if changed px ≥ 0.3 × chars × font size (real glyphs: ~2–4×)
MIN_CHANGED = 6


def font_px(v) -> float:
    try:
        return float(re.sub(r"[^0-9.]", "", str(v)) or 16)
    except ValueError:
        return 16.0


def changed_mask(render: np.ndarray, notext: np.ndarray) -> np.ndarray:
    return np.linalg.norm(render.astype(np.float32) - notext.astype(np.float32), axis=-1) > CHANGE_THRESHOLD


def is_readable(e: dict, changed: np.ndarray) -> bool:
    box = e.get("box")
    if not isinstance(box, (list, tuple)) or len(box) < 4 or any(not isinstance(v, (int, float)) for v in box[:4]):
        return False
    h, w = changed.shape
    x, y, bw, bh = box[:4]
    x0, y0, x1, y1 = max(0, int(x)), max(0, int(y)), min(w, int(x + bw)), min(h, int(y + bh))
    if x1 <= x0 or y1 <= y0:
        return False
    text = str(e.get("text") or "")
    need = max(MIN_CHANGED, PX_PER_CHAR_PER_FONTPX * len(text.strip()) * font_px(e.get("font_size", 16)))
    # nested text elements share pixels with their parent's box; count only this element's box
    return int(changed[y0:y1, x0:x1].sum()) >= need


def parse_rgb(code) -> np.ndarray | None:
    m = re.match(r"rgba?\(([^)]+)\)", str(code or ""))
    if not m:
        return None
    parts = [float(v) for v in re.split(r"[ ,/]+", m.group(1).strip())]
    if len(parts) < 3 or (len(parts) >= 4 and parts[3] == 0):
        return None
    return np.array(parts[:3], np.float32)


def own_glyph_pixels(e: dict, coded: np.ndarray, notext: np.ndarray) -> int:
    """Pixels in e's box that show e's own code colour over the text-free background.

    Per pixel: obs = α·code + (1−α)·bg (anti-aliasing). α is estimated by projection; a pixel counts
    when α ≥ 0.5 and the residual is small, i.e. the pixel really is this element's glyph."""
    c = parse_rgb(e.get("code"))
    box = e.get("box")
    if c is None or not isinstance(box, (list, tuple)) or len(box) < 4:
        return 0
    h, w, _ = coded.shape
    x, y, bw, bh = box[:4]
    x0, y0, x1, y1 = max(0, int(x)), max(0, int(y)), min(w, int(x + bw)), min(h, int(y + bh))
    if x1 <= x0 or y1 <= y0:
        return 0
    obs = coded[y0:y1, x0:x1].astype(np.float32)
    bg = notext[y0:y1, x0:x1].astype(np.float32)
    d = c - bg                                   # code minus background, per pixel
    dd = (d * d).sum(-1)
    ok = dd > 60.0 ** 2                          # colour must be distinguishable from what is behind it
    alpha = np.where(ok, ((obs - bg) * d).sum(-1) / np.maximum(dd, 1), 0)
    resid = np.linalg.norm((obs - bg) - alpha[..., None] * d, axis=-1)
    return int((ok & (alpha >= 0.5) & (resid < 24)).sum())


GLYPH_PX_PER_CHAR = 3.0      # honest on-screen text: min 12.2, median 23.8 px/char (calibrated 2026-09-29); hidden text: 0


def readable_entries(dom: list, render: np.ndarray, notext: np.ndarray, coded: np.ndarray | None = None) -> list[dict]:
    ch = changed_mask(render, notext)
    out = []
    for e in dom or []:
        if not (isinstance(e, dict) and e.get("text") and is_readable(e, ch)):
            continue
        if coded is not None and e.get("code"):
            if own_glyph_pixels(e, coded, notext) < max(3, GLYPH_PX_PER_CHAR * len(str(e["text"]).strip())):
                continue
        out.append(e)
    return out
