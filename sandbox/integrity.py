"""Runtime anti-cheat verdict (static rules live in lint.mjs). A candidate failing any rule scores 0.

Readability comes from pixels (readable.py: text-transparent + per-element colour-coded screenshots),
so hidden text can't dilute ratios or dodge detection.

Rules
- same DOM tree at every breakpoint (JS layout switching is banned; this double-checks it);
- ≤ 30 % of visible elements absolute/fixed;
- duplicated layouts: the same readable text in separate nodes that are never readable at the same
  breakpoint (one layout per breakpoint, toggled with hidden/md:block) — fails when > 20 % of readable
  strings (and ≥ 4 of them), or ≥ 10 regardless of ratio;
- hidden-text stuffing: text laid out on-screen but never readable that matches ≥ 2 target strings.
  Hidden text that matches nothing (sr-only a11y labels) just earns no credit;
- traced layout: > 30 % of readable text sits in elements stacked into the same explicit grid cell or
  overlapping a sibling — i.e. a screenshot pinned in place with offsets instead of a layout that flows.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

MAX_POSITIONED = 0.30
MAX_DUPLICATED_LAYOUT = 0.20
MIN_DUPLICATED = 4
MAX_DUPLICATED_ABS = 10
STUFFING_MATCHES = 2
MAX_TRACED = 0.30


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _readable_idx(out: Path, bp: str) -> set[int] | None:
    import numpy as np  # noqa: F401  (score imports it anyway)
    import readable
    import score
    paths = [out / f"{bp}.{k}" for k in ("png", "notext.png", "coded.png", "dom.json")]
    if not all(p.exists() for p in paths):
        return None
    dom = json.loads(paths[3].read_text())
    seen = readable.readable_entries(dom, score.load(paths[0]), score.load(paths[1]), score.load(paths[2]))
    return {e["idx"] for e in seen if "idx" in e}


def _overlap(a, b) -> float:
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    small = min(a[2] * a[3], b[2] * b[3])
    return (ix * iy) / small if small > 0 else 0.0


def pixel_checks(out: Path, target_strings: list[str]) -> dict | None:
    """Readability-based integrity metrics from render outputs; None if the extra passes are missing."""
    bps = [bp for bp in ("mobile", "tablet", "desktop") if (out / f"{bp}.nodes.json").exists()]
    if len(bps) != 3:
        return None
    nodes = {bp: json.loads((out / f"{bp}.nodes.json").read_text()) for bp in bps}
    readable_at = {}
    for bp in bps:
        r = _readable_idx(out, bp)
        if r is None:
            return None
        readable_at[bp] = r
    n = min(len(v) for v in nodes.values())
    size = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}

    # duplicated layouts over readable text
    by_text: dict[str, list[set]] = {}
    for i in range(n):
        t = _norm(nodes[bps[0]][i].get("t", ""))
        rs = {bp for bp in bps if i in readable_at[bp]}
        if t and rs:
            by_text.setdefault(t, []).append(rs)
    dup = [t for t, sets in by_text.items() if len(t) >= 4 and any(
        not (sets[a] & sets[c]) for a in range(len(sets)) for c in range(a + 1, len(sets)))]

    # hidden text: on-screen at some breakpoint, never readable
    hidden = []
    for i in range(n):
        t = _norm(nodes[bps[0]][i].get("t", ""))
        if not t or any(i in readable_at[bp] for bp in bps):
            continue
        onscreen = False
        for bp in bps:
            e = nodes[bp][i]
            b = e.get("b") or [0, 0, 0, 0]
            W, H = size[bp]
            # fully inside the viewport: text cut off at the fold edge is not "hidden" (close_down12 false positive)
            if e.get("v") and b[2] > 0 and b[3] > 0 and b[0] >= 0 and b[1] >= 0 and b[0] + b[2] <= W and b[1] + b[3] <= H:
                onscreen = True
        if onscreen:
            hidden.append(t)
    targets = [_norm(s) for s in target_strings if _norm(s)]
    # distinct design strings found anywhere in hidden text (one node can hold them all)
    stuffed = [tg for tg in dict.fromkeys(targets) if any(
        (len(tg) >= 4 and tg in h) or difflib.SequenceMatcher(None, tg, h).ratio() >= 0.85 for h in hidden)]

    # positioned share over elements a human can see (sr-only is absolute but 1×1 px: not counted)
    positioned = 0.0
    for bp in bps:
        vis = [e for e in nodes[bp][:n] if e.get("v") and (e.get("b") or [0, 0, 0, 0])[2] >= 4 and (e.get("b") or [0, 0, 0, 0])[3] >= 4]
        if vis:
            positioned = max(positioned, sum(bool(e.get("p")) for e in vis) / len(vis))

    # traced layout: text inside stacked-grid children or sibling-overlapping elements
    traced_ratio = 0.0
    for bp in bps:
        nd = nodes[bp]
        texts = [i for i in readable_at[bp] if i < n and nd[i].get("t")]
        # only elements that contain readable text can make text "traced" (dust pages have 10k+ empty divs;
        # comparing all sibling pairs was quadratic)
        carries: set[int] = set()
        for i in texts:
            j, hops = i, 0
            while j >= 0 and j not in carries and hops < 64:
                carries.add(j)
                j = nd[j].get("par", -1)
                hops += 1
        kids: dict[int, list[int]] = {}
        for i in carries:
            if nd[i].get("v"):
                kids.setdefault(nd[i].get("par", -1), []).append(i)
        flagged: set[int] = set()
        for par, ch in kids.items():
            groups: dict[str, list[int]] = {}
            for i in ch:
                if nd[i].get("ga"):
                    groups.setdefault(nd[i]["ga"], []).append(i)
            for g in groups.values():
                if len(g) >= 2:
                    flagged.update(g)
            # inline boxes of wrapping text span whole lines and "overlap" siblings in honest paragraphs
            blocky = [i for i in ch if not nd[i].get("inl")]
            for a in range(len(blocky)):
                for c in range(a + 1, len(blocky)):
                    if _overlap(nd[blocky[a]].get("b", [0, 0, 0, 0]), nd[blocky[c]].get("b", [0, 0, 0, 0])) > 0.5:
                        flagged.update((blocky[a], blocky[c]))
        # a text node is traced if it or an ancestor is flagged
        def traced(i):
            seen = 0
            while i >= 0 and seen < 64:
                if i in flagged:
                    return True
                i = nd[i].get("par", -1)
                seen += 1
            return False
        if texts:
            traced_ratio = max(traced_ratio, sum(traced(i) for i in texts) / len(texts))
    return {"readable_strings": len(by_text), "duplicated": dup, "duplicated_ratio": len(dup) / max(len(by_text), 1),
            "hidden": hidden[:20], "hidden_count": len(hidden), "stuffed": stuffed[:10], "traced_ratio": round(traced_ratio, 3),
            "positioned_ratio": round(positioned, 3)}


def failures(checks: dict, out: Path | None = None, target_strings: list[str] | None = None) -> list[str]:
    integ = checks.get("integrity") or {}
    fails = []
    if not integ.get("same_tree", False):
        fails.append("DOM tree differs between breakpoints (JS layout switching)")
    px = pixel_checks(out, target_strings or []) if out is not None else None
    worst = px["positioned_ratio"] if px is not None else max((integ.get("positioned_ratio") or {"_": 0}).values())
    if worst > MAX_POSITIONED:
        fails.append(f"{worst:.0%} of visible elements are absolute/fixed (max {MAX_POSITIONED:.0%})")
    if px is not None:
        n_dup, ratio = len(px["duplicated"]), px["duplicated_ratio"]
        if (ratio > MAX_DUPLICATED_LAYOUT and n_dup >= MIN_DUPLICATED) or n_dup >= MAX_DUPLICATED_ABS:
            fails.append(f"{ratio:.0%} of readable texts are duplicated in separate per-breakpoint layouts: {', '.join(px['duplicated'][:3])}")
        if len(px["stuffed"]) >= STUFFING_MATCHES:
            fails.append(f"hidden copies of design text ({len(px['stuffed'])}): {', '.join(px['stuffed'][:3])}")
        if px["traced_ratio"] > MAX_TRACED:
            fails.append(f"{px['traced_ratio']:.0%} of readable text is pinned in stacked/overlapping boxes (traced, not laid out)")
    else:  # legacy renders: CSS-flag based metrics from render.mjs
        dup = integ.get("duplicated_layout_ratio", 0)
        n_dup = integ.get("duplicated_count", 0)
        if (dup > MAX_DUPLICATED_LAYOUT and n_dup >= MIN_DUPLICATED) or n_dup >= MAX_DUPLICATED_ABS:
            fails.append(f"{dup:.0%} of texts are duplicated in separate per-breakpoint layouts")
    if checks.get("runtime_errors"):
        fails.append(f"runtime error: {checks['runtime_errors'][0][:120]}")
    return fails
