"""Repair agent (Phase 3 step 2): fix SOMEONE ELSE's build towards its design at every size, keeping their code.

check (sandbox) → measured feedback in text (per size: each text's rendered box and font against the design's,
missing texts, width-sweep failures — no images reach the model) → Nemotron proposes class edits scoped to one size
(orchestrator/code.class_edits: it cannot add, move or delete elements) → applied deterministically by the JSX tool
→ re-check → the best round is kept (worst size first, then fewer width-sweep failures), ≤ `rounds` rounds.
one_shot() is the benchmark arm without sandbox feedback (design spec only). The bar: docs/REPAIR.md.
"""
from __future__ import annotations

import difflib
import re

from . import jsx_edit

BPS = ("mobile", "tablet", "desktop")
MAX_ROWS = 30
MAX_BOX_ROWS = 12
FAR = 64          # px: a bigger offset is a consequence of the layout around it, not a margin to add

REPAIR_SYSTEM = """You repair SOMEONE ELSE's responsive React + Tailwind page by editing Tailwind classes ONLY — you
cannot move, add or delete elements, and you keep the author's styling unless a listed error asks. Every element
carries data-pc="N"; refer to it by that id.
Each edit targets ONE size via "bp": "mobile" (390 px), "tablet" (768 px) or "desktop" (1280 px), or "all". Give
plain UNPREFIXED classes; the tool adds the md:/xl: prefix, replaces the old value of that property at that size and
keeps the other sizes as they are.
Rules:
- STRUCTURE notes come first: change the named PARENT's layout at that size (grid grid-cols-N, flex-row / flex-col,
  gap-*, justify-*), never each item's margins.
- A Δ is relative to the CURRENT value at that size (read the classes): change the margin/padding by Δ, not to Δ.
- Never add a margin or padding larger than 64 px. "far off" items move by themselves once the layout around them
  is right — leave them unless a STRUCTURE note names their parent.
- "absolute — top Δ, left Δ": the element is absolutely positioned; change its top-/left- value by Δ at that size
  (or, better, make it static/relative in the flow if the design stacks it with its neighbours).
- Centre with mx-auto, justify-center, items-center or text-center — never with ml-/mr- offsets.
- "font a→b px": set text-[b px]. "sideways scroll": replace fixed widths with w-full / max-w-[..px] / flex-wrap.
- MISSING text that exists in the code is hidden at that size: fix its display class (block / flex / inline) there.
Reply with JSON only."""


def untag(code: str) -> str:
    return re.sub(r' data-pc="\d+"', "", code)


def lines_kept(original: str, repaired: str) -> float:
    """Share of the original's non-blank lines that survive unchanged (whitespace-insensitive)."""
    a = [" ".join(l.split()) for l in original.splitlines() if l.strip()]
    b = [" ".join(l.split()) for l in repaired.splitlines() if l.strip()]
    if not a:
        return 1.0
    same = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return round(same / len(a), 3)


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _px(v) -> float | None:
    try:
        return float(str(v).replace("px", ""))
    except (TypeError, ValueError):
        return None


def summary(report: dict) -> dict:
    fl = report.get("fluidity") or {}
    per = report.get("per_bp") or {bp: (v or {}).get("score") for bp, v in (report.get("breakpoints") or {}).items()}
    return {"worst": report.get("match"), "per_bp": per, "fluid_fails": len([f for f in fl.get("fails") or [] if f]),
            "fails": fl.get("fails") or []}


def better(a: dict, b: dict) -> bool:
    """a beats b: worst size up by > 0.5 without new width-sweep failures (or by ≥ 3 with them), or level (± 0.5)
    with fewer width-sweep failures."""
    wa, wb = a.get("worst") or 0, b.get("worst") or 0
    if a["fluid_fails"] > b["fluid_fails"]:
        return wa >= wb + 3
    return wa > wb + 0.5 or (abs(wa - wb) <= 0.5 and a["fluid_fails"] < b["fluid_fails"])


def _clusters(vals: list[float], tol: float = 24) -> int:
    n, last = 0, None
    for v in sorted(vals):
        if last is None or v - last > tol:
            n += 1
        last = v
    return n


def _grid(boxes: list) -> tuple[int, int]:
    """(columns, rows): rows = distinct tops (8 px), columns = the most items sharing a row. Different x positions
    alone are not columns (a centred label in a left-aligned form)."""
    rows: list[list] = []
    for b in sorted(boxes, key=lambda b: b[1]):
        if rows and abs(b[1] - rows[-1][0][1]) <= 8:
            rows[-1].append(b)
        else:
            rows.append([b])
    return max((len(r) for r in rows), default=0), len(rows)


def _structure(placed: list[tuple], elements: list[dict] | None) -> tuple[list[str], set]:
    """placed: [(bp, dom_entry, design_box)]. Items sharing a parent element whose design arrangement (columns ×
    rows) differs from the build's → one hint naming the parent's id. → (hints, {(bp, pc)} covered by a hint)."""
    if not elements:
        return [], set()
    parent = {str(e["id"]): e.get("parent") for e in elements}
    groups: dict = {}
    for bp, d, tb in placed:
        p = parent.get(str(d.get("pc")))
        if p is not None:
            groups.setdefault((bp, p), []).append((d, tb))
    out, covered = [], set()
    for (bp, p), items in groups.items():
        if len(items) < 3:
            continue
        dc, dr = _grid([tb for _, tb in items])
        bc, br = _grid([d["box"] for d, _ in items])
        if max(dc, bc) >= 2 and (dc, dr) != (bc, br):
            covered |= {(bp, str(d.get("pc"))) for d, _ in items}
            ids = ", ".join(str(d.get("pc")) for d, _ in items)
            out.append(f"STRUCTURE [{p}] {bp}: its items [{ids}] form {dc} columns × {dr} rows in the design, {bc} × {br} "
                       f"in the build — change [{p}]'s layout at {bp} (e.g. grid grid-cols-{dc} / flex-col / flex-row + gap), "
                       f"not each item's margins")
    return out, covered


def _hex(c: str) -> str | None:
    if isinstance(c, str) and c.startswith("#") and len(c) == 7:
        return c.lower()
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", c or "")
    return "#%02x%02x%02x" % tuple(int(v) for v in m.groups()) if m else None


def _cdist(a: str, b: str) -> int:
    return sum(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) for i in (1, 3, 5))


def _blocks(spec: dict, nodes: dict) -> list[tuple]:
    """Design boxes (cards, buttons, inputs, panels) against the build's elements of that colour → rows."""
    rows = []
    for bp in BPS:
        frame = (spec.get("breakpoints") or {}).get(bp) or {}
        W, H = frame.get("size") or (1, 1)
        built = [(n, _hex(n.get("bg"))) for n in (nodes or {}).get(bp) or [] if n.get("v", True) and n.get("bg")]
        built = [(n, c) for n, c in built if c]
        used: set = set()
        for b in sorted(frame.get("blocks") or [], key=lambda b: -(b.get("box") or [0, 0, 0, 0])[2] * (b.get("box") or [0, 0, 0, 0])[3]):
            f = _hex(b.get("fill"))
            x, y, w, h = b.get("box") or (0, 0, 0, 0)
            if b.get("rule") or not f or min(w, h) < 8 or w * h < 1200:
                continue
            same = [(n, c) for n, c in built if _cdist(c, f) <= 60 and id(n) not in used]
            if not same:
                if w * h >= 0.01 * W * H:
                    rows.append((w * h / 400, f"MISSING BOX {f} {bp}: the design has a {f} box at {x},{y} ({w}×{h}); "
                                              f"no element has that background there", None))
                continue
            n, _ = min(same, key=lambda nc: abs(nc[0]["b"][0] - x) + abs(nc[0]["b"][1] - y) +
                       abs(nc[0]["b"][2] - w) + abs(nc[0]["b"][3] - h))
            used.add(id(n))
            bx, by, bw, bh = n["b"]
            bits, mag = [], 0
            if abs(bw - w) > max(8, 0.15 * w):
                bits.append(f"width {bw}→{w}")
                mag += abs(bw - w)
            if abs(bh - h) > max(8, 0.15 * h):
                bits.append(f"height {bh}→{h}")
                mag += abs(bh - h)
            off = max(abs(bx - x), abs(by - y))
            if n.get("p") and off > 8:      # absolutely positioned: its own top / left move it
                bits.append(f"absolute — top Δ {y - by:+d}px, left Δ {x - bx:+d}px")
                mag += off
            elif off > FAR:
                bits.append(f"far off (Δ y {y - by:+d}, x {x - bx:+d} px) — fix the layout around it, not with margins")
                mag += off
            elif off > 16:
                bits.append(f"x {bx}→{x}, y {by}→{y}")
                mag += off
            if bits:
                rows.append((mag, f"BOX [{n.get('pc')}] {f} {bp}: " + ", ".join(bits), (bp, str(n.get("pc")))))
    return sorted(rows, key=lambda r: -r[0])[:MAX_BOX_ROWS]


def feedback(report: dict, doms: dict, spec: dict, elements: list[dict] | None = None, nodes: dict | None = None) -> str:
    """Measured errors, render → design, by element id (structure first). Text only."""
    rows, placed = _blocks(spec, nodes), []
    # an element (or its positioned ancestor) placed with absolute / fixed: top / left move it, not the flow
    absolute = {(bp, str(n.get("pc"))): True for bp in BPS for n in (nodes or {}).get(bp) or [] if n.get("p")}
    for bp in BPS:
        frame = (spec.get("breakpoints") or {}).get(bp) or {}
        built = [d for d in (doms or {}).get(bp) or [] if d.get("inked", True)]
        by = {}
        for d in built:
            by.setdefault(_norm(d.get("text")), d)
        for t in frame.get("texts") or []:
            if not t.get("measured") or not t.get("box"):
                continue
            d = by.get(_norm(t["text"]))
            if d is None:
                cands = [x for x in built if difflib.SequenceMatcher(None, _norm(x.get("text")), _norm(t["text"])).ratio() >= 0.85]
                d = cands[0] if cands else None
            tx, ty, tw, th = t["box"]
            if d is None:
                rows.append((999, f"MISSING '{t['text'][:50]}' {bp}: the design shows it at {tx},{ty} ({tw}×{th})", None))
                continue
            x, y, w, h = d["box"]
            placed.append((bp, d, t["box"]))
            fs, dfs = _px(d.get("font_size")), t.get("size_px")
            bits, mag = [], 0
            far = max(abs(y - ty), abs(x - tx)) > FAR
            if absolute.get((bp, str(d.get("pc")))) and max(abs(y - ty), abs(x - tx)) > 8:
                bits.append(f"absolute — top Δ {ty - y:+d}px, left Δ {tx - x:+d}px")
                mag += max(abs(y - ty), abs(x - tx))
            elif far:
                bits.append(f"far off (Δ y {ty - y:+d}, x {tx - x:+d} px) — likely caused by the layout above or around "
                            f"it; fix that, not with margins")
                mag += max(abs(y - ty), abs(x - tx))
            else:
                if abs(y - ty) > 8:
                    bits.append(f"y {y}→{ty} (Δ {ty - y:+d}px)")
                    mag += abs(y - ty)
                if abs(x - tx) > 8:
                    bits.append(f"x {x}→{tx} (Δ {tx - x:+d}px)")
                    mag += abs(x - tx)
            if fs and dfs and abs(fs - dfs) >= 2:
                bits.append(f"font {fs:g}→{dfs:g} px")
                mag += 4 * abs(fs - dfs)
            if tw and w and abs(w - tw) > 0.15 * tw and t.get("lines", 1) > 1:
                bits.append(f"width {w}→{tw} (wrapping)")
                mag += abs(w - tw) / 4
            if bits:
                rows.append((mag, f"[{d.get('pc')}] '{t['text'][:40]}' {bp}: " + ", ".join(bits), (bp, str(d.get("pc")))))
    rows.sort(key=lambda r: -r[0])
    hints, covered = _structure(placed, elements)
    rows.sort(key=lambda r: -r[0])
    out = hints + [r[1] for r in rows if r[2] not in covered][:MAX_ROWS]
    fl = report.get("fluidity") or {}
    for w, v in (fl.get("widths") or {}).items():
        if not str(w).isdigit() or v.get("ok", True):
            continue
        why = []
        if v.get("overflow"):
            culprits = ((report.get("between") or {}).get(str(w)) or {}).get("overflowers") or []
            named = "; ".join(f"[{c.get('pc')}] <{c.get('tag')}> is {c.get('w')} px wide (ends at {c.get('right')} px)"
                              for c in culprits[:3])
            why.append(f"{v['overflow']} px sideways scroll" + (f" — {named}" if named else " (something is wider than the screen)"))
        if v.get("overlaps"):
            why.append(f"{v['overlaps']} overlapping texts")
        if v.get("centre_drift") and v["centre_drift"] > 0.05:
            why.append(f"content shifted {round(v['centre_drift'] * 100)} % off centre")
        if why:
            out.append(f"WIDTH {w}px: " + "; ".join(why) + " — fix with fluid widths (w-full / max-w-*), not fixed px")
    scores = summary(report)["per_bp"]
    head = "Scores per size: " + ", ".join(f"{bp} {scores.get(bp)}" for bp in BPS if scores.get(bp) is not None)
    return head + "\n" + "\n".join(out) if out else ""


def _propose_default(client):
    from .code import class_edits

    def propose(tagged: str, fb: str, temperature: float = 0.4) -> list[dict]:
        edits, _ = class_edits(client, tagged, fb, "STRUCTURE notes first, then the worst size; remove sideways scroll "
                               "at narrow widths", temperature=temperature, system=REPAIR_SYSTEM)
        return edits
    return propose


TEMPERATURES = (0.3, 0.7, 1.0)


def _ask(propose, code: str, fb: str, t: float) -> list[dict]:
    try:
        return propose(code, fb, temperature=t) or []
    except TypeError:             # a proposer without a temperature
        return propose(code, fb) or []


def repair(code: str, *, spec: dict, check, propose, rounds: int = 3, candidates: int = 3, emit=lambda *a, **k: None,
           feedback_fn=None, pmap=map) -> dict:
    """check(code) → {"report", "dom"}; propose(tagged_code, feedback, temperature=) → edits [{id, bp, add, remove}].
    Each round: `candidates` proposals (different temperatures), each applied and checked; every size keeps the edits
    of the candidate that improved it most (edits are scoped to one size); the merge is checked and kept if better.
    The next round is told which edits made which size worse. pmap: a parallel map for the checks."""
    from .perceive import spec_for_prompt
    feedback_fn = feedback_fn or feedback
    design = spec_for_prompt(spec)
    tagged, elements = jsx_edit.tag(code)
    emit("check", round=0)
    cur = check(tagged)
    start = summary(cur["report"])
    best_code, best, best_res = tagged, start, cur
    history, notes = [dict(start, round=0)], []
    for r in range(1, rounds + 1):
        fb = feedback_fn(best_res["report"], best_res.get("dom") or {}, spec, elements, best_res.get("nodes") or {})
        if not fb:
            break
        if notes:
            fb += "\nLAST ROUND (do not repeat): " + " ".join(notes)
        fb = "MEASURED errors of the current page (render → design):\n" + fb + "\n\nDESIGN (target) per size:\n" + design
        
        props = [_ask(propose, best_code, fb, t) for t in TEMPERATURES[:candidates]]
        cands = []
        for edits in props:
            if edits:
                new, n, _ = jsx_edit.apply(best_code, edits)
                if n:
                    cands.append((edits, new))
        if not cands:
            break
        emit("check", round=r, candidates=len(cands))
        results = list(pmap(check, [new for _, new in cands]))
        sums = [summary(res["report"]) for res in results]
        notes = []
        merged = []
        for bp in BPS:
            base = (best["per_bp"] or {}).get(bp) or 0
            gains = [((s["per_bp"] or {}).get(bp) or 0, k) for k, s in enumerate(sums)]
            top, k = max(gains)
            if top > base + 0.3:
                merged += [e for e in cands[k][0] if e.get("bp") == bp]
            for score, j in gains:
                if score < base - 0.3:
                    ids = sorted({e["id"] for e in cands[j][0] if e.get("bp") in (bp, "all")})
                    adds = sorted({e.get("add", "") for e in cands[j][0] if e.get("bp") in (bp, "all")})[:4]
                    notes.append(f"edits {adds} on {ids} made {bp} worse ({base:g}→{score:g}).")
        overall = max(range(len(sums)), key=lambda k: (sums[k]["worst"] or 0, -sums[k]["fluid_fails"]))
        options = [(sums[overall], cands[overall][1], results[overall], len(cands[overall][0]))]
        if merged:
            new, n, _ = jsx_edit.apply(best_code, merged)
            if n and new not in [c for _, c in cands]:
                res = check(new)
                options.append((summary(res["report"]), new, res, n))
            elif n:
                j = [c for _, c in cands].index(new)
                options.append((sums[j], new, results[j], n))
        s, new, res, n = max(options, key=lambda o: (o[0]["worst"] or 0, -o[0]["fluid_fails"]))
        history.append(dict(s, round=r, applied=n, candidates=len(cands)))
        if better(s, best):
            best_code, best, best_res = new, s, res
    final = untag(best_code) if best_code != tagged else code
    return {"code": final, "start": start, "best": best, "history": history, "lines_kept": lines_kept(code, final)}


def one_shot(code: str, *, spec: dict, check, propose) -> dict:
    """Benchmark arm: the design spec only (no measurement of the build), one proposal, checked once."""
    from .perceive import spec_for_prompt
    tagged, _ = jsx_edit.tag(code)
    start = summary(check(tagged)["report"])
    edits = propose(tagged, "No measurements are available. Make the page match this design at every size:\n" +
                    spec_for_prompt(spec)) or []
    new, n, _ = jsx_edit.apply(tagged, edits) if edits else (tagged, 0, [])
    after = summary(check(new)["report"]) if n else start
    final = untag(new) if n else code
    return {"code": final, "start": start, "best": after, "history": [dict(start, round=0), dict(after, round=1)],
            "lines_kept": lines_kept(code, final)}
