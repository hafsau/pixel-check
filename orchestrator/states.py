"""Interaction states: what an interaction changes between a base frame and a state frame (same breakpoint).

A state frame is the design after a trigger (menu open, tab selected, accordion expanded). state_diff matches texts
by string + position (duplicates by nearest position) and blocks by overlap + fill, and classifies the change:
  overlay — a full-width panel over most of the viewport (lambda / vercel mobile menus)
  drawer  — a full-height panel anchored to one side (lennysjobs mobile menu)
  inline  — content inserted in the flow (an accordion answer pushing the next question down)
  none    — nothing appeared
The diff is the measured input for the interaction writer (Nemotron) and for the generated acceptance tests.
"""
from __future__ import annotations

import re

JITTER = 6          # px: same element re-measured, not moved
MATCH_IOU = 0.8


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _centre(b):
    return b[0] + b[2] / 2, b[1] + b[3] / 2


def _iou(a, b) -> float:
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = a[2] * a[3] + b[2] * b[3] - i
    return i / u if u else 0.0


def _fill_close(a, b) -> bool:
    fa, fb = a.get("fill") or "#000000", b.get("fill") or "#000000"
    if len(fa) != 7 or len(fb) != 7:
        return fa == fb
    return sum(abs(int(fa[i:i + 2], 16) - int(fb[i:i + 2], 16)) for i in (1, 3, 5)) <= 40


def _union(boxes):
    if not boxes:
        return None
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    return [x0, y0, max(b[0] + b[2] for b in boxes) - x0, max(b[1] + b[3] for b in boxes) - y0]


def _match_texts(base: list, state: list):
    """Greedy nearest-position pairing among equal strings → (pairs, unmatched base, unmatched state)."""
    cands = []
    for i, b in enumerate(base):
        for j, s in enumerate(state):
            if _norm(b["text"]) and _norm(b["text"]) == _norm(s["text"]):
                (bx, by), (sx, sy) = _centre(b["box"]), _centre(s["box"])
                cands.append((abs(bx - sx) + abs(by - sy), i, j))
    pairs, ub, us = [], set(range(len(base))), set(range(len(state)))
    for _, i, j in sorted(cands):
        if i in ub and j in us:
            pairs.append((i, j))
            ub.discard(i)
            us.discard(j)
    return pairs, sorted(ub), sorted(us)


def _in_area(box, area, pad=6) -> bool:
    cx, cy = _centre(box)
    return area[0] - pad <= cx <= area[0] + area[2] + pad and area[1] - pad <= cy <= area[1] + area[3] + pad


def classify(panel, W, H, covered: bool = False) -> str:
    """covered: page content below the panel's top disappeared — a short full-width menu still covers the page."""
    if panel is None:
        return "none"
    if panel[2] >= 0.85 * W and (panel[3] >= 0.4 * H or covered):
        return "overlay"
    if panel[3] >= 0.8 * H and (panel[0] >= 0.3 * W or panel[0] + panel[2] <= 0.7 * W):
        return "drawer"
    return "inline"


def panel_of(texts: list, blocks: list):
    return _union([t["box"] for t in texts] + [b["box"] for b in blocks])


def dim_region(base_img, state_img, exclude=(), min_px: int = 2000):
    """Where the state frame is the base frame dimmed by one constant factor, found without knowing the panel: the
    dominant brightness ratio among bright base pixels, then every pixel that follows it. → {"opacity", "mask"} or
    None. Used to keep the dimmed page behind a drawer out of the panel (perception reads it as new items)."""
    import numpy as np
    from scipy import ndimage
    b = np.asarray(base_img, dtype=float)
    s = np.asarray(state_img, dtype=float)
    if b.shape != s.shape:
        return None
    keep = np.ones(b.shape[:2], bool)
    for ex in exclude or ():
        x, y, w, h = [int(v) for v in ex]
        keep[max(0, y - 4):y + h + 4, max(0, x - 4):x + w + 4] = False
    lb, ls = b.mean(axis=2), s.mean(axis=2)
    bright = keep & (lb > 60)
    if bright.sum() < min_px:
        return None
    ratio = ls[bright] / lb[bright]
    hist, edges = np.histogram(ratio, bins=50, range=(0.0, 1.0))
    hist[int(0.85 * 50):] = 0
    k = int(hist.argmax())
    if hist[k] < max(min_px // 2, 0.15 * bright.sum()):
        return None
    near = ratio[np.abs(ratio - (edges[k] + 0.01)) <= 0.04]
    r0 = float(np.median(near))
    a = 1 - r0
    if a < 0.15:
        return None
    # tolerance relative to the EXPECTED dimmed value (8 % of the base let bright glyphs under a dark drawer pass)
    mask = keep & (lb > 8) & (np.abs(ls - lb * r0) <= np.maximum(3, 0.25 * lb * r0)) & (np.abs(ls - lb) > 2)
    # dimming darkens the page background too; an opaque panel of the page colour leaves it unchanged (a cover)
    q = (lb // 4).astype(int)
    bgv = np.bincount(q[keep].ravel()).argmax() * 4 + 2
    bgpx = keep & (np.abs(lb - bgv) <= 4)
    if bgpx.sum() >= min_px and mask[bgpx].mean() < 0.3:
        return None
    raw = mask
    mask = ndimage.binary_closing(mask, np.ones((9, 9), bool))
    # the panel the backdrop leaves undimmed: below the first dimmed row, the widest run of columns that are (mostly)
    # not dimmed — a drawer whose background equals the page colour is invisible to measurement but obvious here.
    # (raw mask: closing erodes the image edges and made edge columns look undimmed)
    undimmed = None
    rows = np.nonzero(raw.mean(axis=1) > 0.2)[0]
    if len(rows):
        top = int(rows.min())
        low = raw[top:].mean(axis=0) < 0.3
        best, run = None, None
        for x, v in enumerate(list(low) + [False]):
            if v and run is None:
                run = x
            elif not v and run is not None:
                if best is None or x - run > best[1] - best[0]:
                    best = (run, x)
                run = None
        if best and 16 <= best[1] - best[0] < 0.85 * raw.shape[1]:
            undimmed = [best[0], top, best[1] - best[0], int(raw.shape[0] - top)]
    mask = ndimage.binary_dilation(mask, np.ones((5, 5), bool))
    if undimmed:   # stray coincidental matches under the panel (glyph edges) are not backdrop
        x, y, w, h = undimmed
        mask[y:y + h, x:x + w] = False
    return {"opacity": round(a, 2), "mask": mask, "undimmed": undimmed}


def state_diff(base: dict, state: dict, trigger_box=None) -> dict:
    """trigger_box: changes inside the trigger's area (hamburger → X) are the trigger's open look, reported as
    trigger_changes and kept out of the panel."""
    W, H = state.get("size") or base.get("size") or [0, 0]
    bt = [t for t in base.get("texts", []) if t.get("box")]
    st = [t for t in state.get("texts", []) if t.get("box")]
    pairs, ub, us = _match_texts(bt, st)
    persisted, moved = [], []
    for i, j in pairs:
        b, s = bt[i]["box"], st[j]["box"]
        if abs(b[0] - s[0]) <= JITTER and abs(b[1] - s[1]) <= JITTER:
            persisted.append(st[j])
        else:
            moved.append(dict(st[j], from_box=b))
    bb, sb = base.get("blocks", []), state.get("blocks", [])
    kept_b, kept_s = set(), set()
    for i, b in enumerate(bb):
        for j, s in enumerate(sb):
            if j not in kept_s and _iou(b["box"], s["box"]) >= MATCH_IOU and _fill_close(b, s):
                kept_b.add(i)
                kept_s.add(j)
                break
    appeared_t = [st[j] for j in us]
    appeared_b = [sb[j] for j in range(len(sb)) if j not in kept_s]
    gone_t = [bt[i] for i in ub]
    gone_b = [bb[i] for i in range(len(bb)) if i not in kept_b]
    trig = {"appeared": {"texts": [], "blocks": []}, "disappeared": {"texts": [], "blocks": []}}
    if trigger_box:
        inside = lambda x: _in_area(x["box"], trigger_box)
        trig = {"appeared": {"texts": [t for t in appeared_t if inside(t)], "blocks": [b for b in appeared_b if inside(b)]},
                "disappeared": {"texts": [t for t in gone_t if inside(t)], "blocks": [b for b in gone_b if inside(b)]}}
        appeared_t = [t for t in appeared_t if not inside(t)]
        appeared_b = [b for b in appeared_b if not inside(b)]
        gone_t = [t for t in gone_t if not inside(t)]
        gone_b = [b for b in gone_b if not inside(b)]
    panel = _union([t["box"] for t in appeared_t] + [b["box"] for b in appeared_b])
    covered = bool(panel) and any(_centre(t["box"])[1] > panel[1] for t in gone_t)
    kind = classify(panel, W, H, covered)
    return {
        "appeared": {"texts": appeared_t, "blocks": appeared_b},
        "disappeared": {"texts": gone_t, "blocks": gone_b},
        "trigger_changes": trig,
        "persisted": {"texts": persisted, "blocks": [sb[j] for j in sorted(kept_s)]},
        "moved": moved,
        "kind": kind,
        "panel": panel,
    }


def backdrop(base_img, state_img, panel_box, min_px: int = 2000, exclude=()):
    """A dimming layer behind a drawer/overlay: outside the panel the state frame is the base frame darkened by a
    constant factor (lambda's tablet drawer dims the page to ~40 %). Fitted on bright base pixels:
    state ≈ base·(1 − a) + 0·a  →  a = 1 − state/base. → {"color": "#000000", "opacity": a} or None."""
    import numpy as np
    b = np.asarray(base_img, dtype=float)
    s = np.asarray(state_img, dtype=float)
    if b.shape != s.shape:
        return None
    mask = np.ones(b.shape[:2], bool)
    if panel_box:
        x, y, w, h = [int(v) for v in panel_box]
        mask[max(0, y):y + h, max(0, x):x + w] = False
    for ex in exclude or ():          # the trigger (hamburger → X) changes on its own
        x, y, w, h = [int(v) for v in ex]
        mask[max(0, y - 4):y + h + 4, max(0, x - 4):x + w + 4] = False
    lb, ls = b.mean(axis=2), s.mean(axis=2)
    bright = mask & (lb > 60)
    if bright.sum() < min_px:
        return None
    ratio = ls[bright] / lb[bright]
    a = float(1 - np.median(ratio))
    spread = float(np.percentile(ratio, 75) - np.percentile(ratio, 25))
    if a < 0.15 or spread > 0.12:
        return None
    # where it applies: the dimmed pixels' extent (lambda's header above the drawer stays undimmed)
    dimmed = mask & (lb > 8) & (ls < lb * (1 - a / 2))     # dark page backgrounds dim too (11 → 1)
    ys, _ = np.nonzero(dimmed)
    H, W = b.shape[:2]
    # a backdrop spans the viewport width from its top edge down (content only shows where the page has ink)
    box = [0, int(ys.min()), int(W), int(H - ys.min())] if len(ys) else None
    return {"color": "#000000", "opacity": round(a, 2), "box": box}


def trigger_look(base_img, state_img, trigger_box):
    """What the trigger shows once open, read from the images (perception misses thin diagonal icons): the state
    frame's ink inside the trigger box, if it differs from the base frame. → {"box" (relative to the trigger),
    "fill", "shape": "x" | "unknown"} or None."""
    import numpy as np
    b = np.asarray(base_img, dtype=float)
    s = np.asarray(state_img, dtype=float)
    x, y, w, h = [int(v) for v in trigger_box]
    bc, sc = b[y:y + h, x:x + w], s[y:y + h, x:x + w]
    if bc.size == 0 or np.abs(bc - sc).max() < 40 or (np.abs(bc - sc).sum(axis=2) > 60).mean() < 0.01:
        return None
    ring = np.concatenate([sc[0], sc[-1], sc[:, 0], sc[:, -1]])
    bgc = np.median(ring, axis=0)
    ink = np.linalg.norm(sc - bgc, axis=-1) > 40
    if ink.sum() < 6:
        return None
    ys, xs = np.nonzero(ink)
    box = [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]
    u = (xs - xs.min()) / max(1, box[2] - 1)
    v = (ys - ys.min()) / max(1, box[3] - 1)
    on_diag = (np.abs(u - v) < 0.18) | (np.abs(u + v - 1) < 0.18)
    both = (np.abs(u - v) < 0.18).mean() > 0.25 and (np.abs(u + v - 1) < 0.18).mean() > 0.25
    shape = "x" if on_diag.mean() > 0.8 and both and abs(box[2] - box[3]) <= 4 else "unknown"
    dist = np.linalg.norm(sc - bgc, axis=-1)
    fill = sc[ink & (dist >= np.percentile(dist[ink], 80))].mean(axis=0)   # core pixels, not antialiased edges
    return {"box": box, "fill": "#" + "".join(f"{int(round(c)):02x}" for c in fill), "shape": shape}
