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


def state_diff(base: dict, state: dict) -> dict:
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
    panel = _union([t["box"] for t in appeared_t] + [b["box"] for b in appeared_b])
    if panel is None:
        kind = "none"
    elif panel[2] >= 0.85 * W and panel[3] >= 0.4 * H:
        kind = "overlay"
    elif panel[3] >= 0.8 * H and (panel[0] >= 0.3 * W or panel[0] + panel[2] <= 0.7 * W):
        kind = "drawer"
    else:
        kind = "inline"
    return {
        "appeared": {"texts": appeared_t, "blocks": appeared_b},
        "disappeared": {"texts": [bt[i] for i in ub], "blocks": [bb[i] for i in range(len(bb)) if i not in kept_b]},
        "persisted": {"texts": persisted, "blocks": [sb[j] for j in sorted(kept_s)]},
        "moved": moved,
        "kind": kind,
        "panel": panel,
    }
