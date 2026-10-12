"""Responsive honesty report (council Gate A, Oct 1) from render.mjs checks.json.

At 360 / 375 / 500 / 1024 / 1600 px (widths without a design frame):
- 0 horizontal overflow and no text overlaps beyond those the nearest design size itself has;
- content stays where the nearest design frame puts it: |centre_ratio − frame's centre_ratio| ≤ 0.05
  (catches layouts pinned to the left between breakpoints);
At every width (design ones too): no vertical gap taller than one viewport on the full page, and the page
background covers the whole page (catches content pushed below the fold with magic margins).
The nearest frame is the one whose Tailwind classes apply at that width: < 768 mobile, < 1280 tablet, else desktop.
"""
from __future__ import annotations


SCREENS = (640, 768, 1024, 1280, 1536)       # Tailwind sm md lg xl 2xl


def _screen_min(width: int) -> int:
    """The min-width of the largest standard screen at or below the width (0 = no prefix)."""
    return max([s for s in SCREENS if s <= width], default=0)


def nearest(w: int, sizes: dict | None = None) -> str:
    """The design frame whose layout is in effect at width w: each frame's classes switch on at its Tailwind screen
    (a 1071 px desktop uses lg: → from 1024 px). Standard frames: tablet from 768, desktop from 1280."""
    t = _screen_min(sizes["tablet"][0]) if sizes else 768
    d = _screen_min(sizes["desktop"][0]) if sizes else 1280
    return "mobile" if w < t else "tablet" if w < d else "desktop"


def report(checks: dict) -> dict:
    bp = checks.get("breakpoints", {})
    sizes = checks.get("sizes")
    rows, fails = {}, []
    for w, v in sorted(((int(k), v) for k, v in (checks.get("between") or {}).items())):
        ref = bp.get(nearest(w, sizes), {})
        drift = abs((v.get("centre_ratio") or 0) - (ref.get("centre_ratio") or 0)) if v.get("content") and ref.get("content") else None
        # overlaps the design itself has at its nearest size (a decorative mark over a headline) are not breakage
        overlaps = max(0, (v.get("text_overlaps") or 0) - (ref.get("text_overlaps") or 0))
        overflow = max(v.get("overflow_px") or 0, v.get("clipped_overflow_px") or 0)   # text cut off by a clipping wrapper too
        ok = (overflow == 0 and overlaps == 0 and (drift is None or drift <= 0.05)
              and v.get("max_vertical_gap", 0) <= v.get("viewport_h", 9999) and v.get("background_covers", True))
        rows[w] = {"overflow": overflow, "overlaps": overlaps, "centre_drift": None if drift is None else round(drift, 3),
                   "max_gap": v.get("max_vertical_gap"), "bg_covers": v.get("background_covers"), "ok": ok}
        if not ok:
            fails.append(w)
    for name, v in bp.items():
        if v.get("max_vertical_gap", 0) > v.get("height", 9999) or not v.get("background_covers", True) or v.get("overflow_px", 0):
            fails.append(name)
        rows[name] = {"overflow": v.get("overflow_px"), "max_gap": v.get("max_vertical_gap"), "bg_covers": v.get("background_covers")}
    return {"pass": not fails, "fails": fails, "widths": rows}
