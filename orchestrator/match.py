"""Cross-frame matching of text-free boxes (icons, image placeholders, dividers, tiles).

Texts match by their string; a labelled box by the texts inside it. A text-free box has neither, and keying it by
"nearest text" or reading order paired the wrong elements when the nearest text changed between frames (lambda's
column dividers: "Experts…" on tablet, "03" on desktop; calcom's tiles; vercel's check icons). Here every text-free
box observation is placed relative to several text anchors that exist in both frames, and observations are paired
frame-to-frame by a minimum-cost assignment (Hungarian) over predicted-position error, with style as a hard
constraint. Measured on DOM ground truth with tools/match_eval.py.
"""
from __future__ import annotations

import re

import numpy as np
from scipy.optimize import linear_sum_assignment

from .scaffold import BPS, Item, _elem_box

TEXTFREE = re.compile(r"^b:[0-9a-f]{3}o?r?(~|@)")
MAX_COST = 1.6          # ≈ 80 px of predicted-position error
ORDER = ("desktop", "tablet", "mobile")


def _box(it: Item, bp: str):
    return it.at[bp]["box"] if it.kind == "block" else _elem_box(it, bp)


def _style(a: dict) -> tuple:
    b = a["box"]
    f = a.get("fill") or "#000000"
    rule = min(b[2], b[3]) <= 3
    orient = ("v" if b[3] > b[2] else "h") if rule else "-"
    return (tuple(int(f[i:i + 2], 16) // 40 for i in (1, 3, 5)) if len(f) == 7 else f, bool(a.get("border")), orient)


def _compatible(a: dict, b: dict) -> bool:
    """Same kind of box: orientation and border agree, fills within measurement noise (perception read lambda's
    header divider as #3d3d21 on desktop and #262625 elsewhere — binned colours split one element in two)."""
    sa, sb = _style(a), _style(b)
    if sa[1:] != sb[1:]:
        return False
    fa, fb = a.get("fill") or "#000000", b.get("fill") or "#000000"
    if len(fa) != 7 or len(fb) != 7:
        return fa == fb
    return sum(abs(int(fa[i:i + 2], 16) - int(fb[i:i + 2], 16)) for i in (1, 3, 5)) <= 72


def _gap(a, b) -> float:
    dx = max(0, a[0] - (b[0] + b[2]), b[0] - (a[0] + a[2]))
    dy = max(0, a[1] - (b[1] + b[3]), b[1] - (a[1] + a[3]))
    return dx + 1.5 * dy


def _cost(obs_ref: dict, ref: str, obs: dict, bp: str, anchors: list[Item]) -> float:
    """Predicted-position error of obs (at bp) given the cluster's observation at ref, through the 3 nearest
    anchors (texts shown in both frames); best anchor wins. Sizes must be compatible."""
    if not _compatible(obs_ref, obs):
        return 9.0
    rb, ob = obs_ref["box"], obs["box"]
    rule = min(rb[2], rb[3]) <= 3
    if not rule:
        hr = ob[3] / max(rb[3], 1)
        if not 0.5 <= hr <= 2.0:
            return 9.0
    both = [a for a in anchors if ref in a.at and bp in a.at]
    if not both:
        return 9.0
    near = sorted(both, key=lambda a: _gap(_box(a, ref), rb))[:3]
    best = 9.0
    for a in near:
        ar, ab = _box(a, ref), _box(a, bp)
        # offset from the anchor's left/top edge, x scaled by the anchor's own width change (reflowed text)
        px = ab[0] + (rb[0] - ar[0]) * (ab[2] / max(ar[2], 1) if abs(rb[0] - ar[0]) > ar[2] else 1.0)
        py = ab[1] + (rb[1] - ar[1])
        err = abs(px - ob[0]) + abs(py - ob[1])
        best = min(best, err / 50.0 + 0.25 * min(1.0, _gap(ar, rb) / 200.0))
    return best


def _ranks(observations: list[dict]) -> dict:
    """id(obs) → (style, group size, reading-order rank) among observations of the same style in that frame."""
    groups: dict = {}
    import math
    for o in observations:   # style + height class (icons, tiles and image placeholders share a fill colour)
        groups.setdefault((_style(o), round(math.log2(max(o["box"][3], 1)))), []).append(o)
    out = {}
    for st, g in groups.items():
        g = sorted(g, key=lambda o: (round(o["box"][1] / 8), o["box"][0]))
        for k, o in enumerate(g):
            out[id(o)] = (st, len(g), k)
    return out


def rematch_textfree(items: list[Item]) -> list[Item]:
    tf = [it for it in items if it.kind == "block" and TEXTFREE.match(it.key) and not it.children]
    if not tf:
        return items
    anchors = [it for it in items if it.kind == "text" and len(it.at) >= 2]
    obs = {bp: [it.at[bp] for it in tf if bp in it.at] for bp in BPS}
    clusters: list[dict] = []          # {bp: observation}
    for bp in ORDER:
        cur = obs[bp]
        if not clusters:
            clusters = [{bp: o} for o in cur]
            continue
        if not cur:
            continue
        C = np.full((len(cur), len(clusters)), 9.0)
        rank_here = _ranks(cur)
        for i, o in enumerate(cur):
            for j, cl in enumerate(clusters):
                if bp in cl:
                    continue
                ref = next(r for r in ORDER if r in cl)
                c = _cost(cl[ref], ref, o, bp, anchors)
                # same-style group of equal size in both frames (6 tiles here, 6 there): reading-order rank agrees
                rr = _ranks([x[ref] for x in clusters if ref in x])
                ri, rj = rank_here[id(o)], rr.get(id(cl[ref]))
                if rj and ri[0] == rj[0] and ri[1] == rj[1] and ri[2] == rj[2]:
                    c = min(c, 0.8)
                C[i, j] = c
        rows, cols = linear_sum_assignment(C)
        taken = set()
        for i, j in zip(rows, cols):
            if C[i, j] <= MAX_COST:
                clusters[j][bp] = cur[i]
                taken.add(i)
        clusters += [{bp: cur[i]} for i in range(len(cur)) if i not in taken]
    out = [it for it in items if it not in tf]
    for n, cl in enumerate(clusters):
        a = next(cl[bp] for bp in ORDER if bp in cl)
        st = _style(a)
        it = Item(f"b:tf{n}:{st[2]}", "block")
        it.at = {bp: o for bp, o in cl.items()}
        out.append(it)
    return out
