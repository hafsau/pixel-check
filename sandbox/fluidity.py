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


def nearest(w: int) -> str:
    return "mobile" if w < 768 else "tablet" if w < 1280 else "desktop"


def report(checks: dict) -> dict:
    bp = checks.get("breakpoints", {})
    rows, fails = {}, []
    for w, v in sorted(((int(k), v) for k, v in (checks.get("between") or {}).items())):
        ref = bp.get(nearest(w), {})
        drift = abs((v.get("centre_ratio") or 0) - (ref.get("centre_ratio") or 0)) if v.get("content") and ref.get("content") else None
        # overlaps the design itself has at its nearest size (a decorative mark over a headline) are not breakage
        overlaps = max(0, (v.get("text_overlaps") or 0) - (ref.get("text_overlaps") or 0))
        ok = (v.get("overflow_px", 0) == 0 and overlaps == 0 and (drift is None or drift <= 0.05)
              and v.get("max_vertical_gap", 0) <= v.get("viewport_h", 9999) and v.get("background_covers", True))
        rows[w] = {"overflow": v.get("overflow_px"), "overlaps": overlaps, "centre_drift": None if drift is None else round(drift, 3),
                   "max_gap": v.get("max_vertical_gap"), "bg_covers": v.get("background_covers"), "ok": ok}
        if not ok:
            fails.append(w)
    for name, v in bp.items():
        if v.get("max_vertical_gap", 0) > v.get("height", 9999) or not v.get("background_covers", True) or v.get("overflow_px", 0):
            fails.append(name)
        rows[name] = {"overflow": v.get("overflow_px"), "max_gap": v.get("max_vertical_gap"), "bg_covers": v.get("background_covers")}
    return {"pass": not fails, "fails": fails, "widths": rows}
