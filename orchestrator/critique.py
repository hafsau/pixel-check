"""Critique: turn an evaluation into precise, text-only feedback and 3 different fix strategies.

Signals (none of them give the coder an image):
1. element diff — spec (measured design boxes) vs render DOM (exact boxes), per breakpoint;
2. scorer report — per-breakpoint score, worst breakpoint, diff regions, missing text, in-between widths;
3. visual notes — the vision model compares design vs render images and writes differences in words.
Nemotron (critic) reads all three and proposes 3 strategies that differ in approach.
"""
from __future__ import annotations

import difflib
import json
import re

from . import config
from .tf_client import TFClient, image_part, parse_json


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower().lstrip("| ")


def element_diff(spec: dict, dom: dict[str, list], max_rows: int = 40) -> str:
    """Per breakpoint: where each measured design text is vs where the render put it."""
    lines = []
    for bp, frame in spec["breakpoints"].items():
        rendered = [e for e in dom.get(bp, []) if e.get("text")]
        rows = []
        for t in frame["texts"]:
            if not t.get("box") or t.get("approx"):
                continue
            key = _norm(t["text"])
            best, score = None, 0.0
            for e in rendered:
                r = difflib.SequenceMatcher(None, key, _norm(e["text"])).ratio()
                if key and key in _norm(e["text"]):
                    r = max(r, 0.9)
                if r > score:
                    best, score = e, r
            tx, ty, tw, th = t["box"]
            label = t["text"][:48]
            if best is None or score < 0.75:
                rows.append(f"  MISSING  '{label}' (design at x={tx},y={ty}, {t.get('size_px')}px)")
                continue
            rx, ry, rw, rh = best["box"]
            label = f"{label}' [#{best['pc']}]" if best.get("pc") is not None else label + "'"
            label = label[:-1] if label.endswith("'") else label
            fs = float(re.sub(r"[^0-9.]", "", str(best.get("font_size", "0"))) or 0)
            issues = []
            if abs(ry - ty) > 6:
                issues.append(f"y {ry}→{ty} ({'down' if ty > ry else 'up'} {abs(ty - ry)}px)")
            if abs(rx - tx) > 6:
                issues.append(f"x {rx}→{tx} ({'right' if tx > rx else 'left'} {abs(tx - rx)}px)")
            if t.get("size_px") and fs and abs(fs - t["size_px"]) >= 2:
                issues.append(f"font {fs:.0f}px→{t['size_px']}px")
            if abs(rw - tw) > max(12, 0.15 * tw) and t.get("role") in ("button", "input-placeholder", "heading", "body", "caption"):
                issues.append(f"text width {rw}→{tw}px (wrapping/size)")
            if not best.get("onscreen", True):
                issues.append("render has it OFF-SCREEN")
            if issues:
                rows.append(f"  '{label}: " + ", ".join(issues))
        if rows:
            lines.append(f"{bp} ({len(rows)} issues):")
            lines += rows[:max_rows]
        else:
            lines.append(f"{bp}: all measured texts within 6 px")
    return "\n".join(lines)


def _pairs(frame: dict, rendered: list[dict]) -> list[dict]:
    """Measured design texts matched to render DOM entries: [{id, label, d: box, r: box, ...}]."""
    out, used = [], set()
    for t in frame["texts"]:
        if not t.get("box") or t.get("approx"):
            continue
        key = _norm(t["text"])
        best, score = None, 0.0
        tx, ty = t["box"][0] + t["box"][2] / 2, t["box"][1] + t["box"][3] / 2
        for k, e in enumerate(rendered):
            if k in used:
                continue
            r = difflib.SequenceMatcher(None, key, _norm(e["text"])).ratio()
            if key and key in _norm(e["text"]):
                r = max(r, 0.9)
            # duplicates ("Enterprise" in the nav and on a card): among equal text matches prefer the nearest one
            b = e.get("box") or [0, 0, 0, 0]
            dist = ((b[0] + b[2] / 2 - tx) ** 2 + (b[1] + b[3] / 2 - ty) ** 2) ** 0.5
            r -= min(dist, 2000) / 1e5
            if r > score:
                best, score = k, r
        if best is None or score < 0.75:
            out.append({"id": None, "label": t["text"][:40], "d": t["box"], "r": None, "size": t.get("size_px")})
            continue
        used.add(best)
        e = rendered[best]
        fs = float(re.sub(r"[^0-9.]", "", str(e.get("font_size", "0"))) or 0)
        out.append({"id": e.get("pc"), "label": t["text"][:40], "d": t["box"], "r": e["box"], "size": t.get("size_px"),
                    "rsize": fs, "role": t.get("role")})
    return out


def _rows(items: list[dict], key: str) -> list[list[dict]]:
    """Group items into visual rows by vertical overlap of their boxes."""
    rows: list[list[dict]] = []
    for it in sorted(items, key=lambda i: i[key][1]):
        y, h = it[key][1], it[key][3]
        for row in rows:
            ry0 = min(r[key][1] for r in row)
            ry1 = max(r[key][1] + r[key][3] for r in row)
            if min(ry1, y + h) - max(ry0, y) >= 0.5 * min(h, ry1 - ry0):
                row.append(it)
                break
        else:
            rows.append([it])
    for row in rows:
        row.sort(key=lambda i: i[key][0])
    return rows


def _tag(it) -> str:
    return f"#{it['id']} '{it['label'][:24]}'" if it["id"] is not None else f"'{it['label'][:24]}'"


def flow_diff(spec: dict, dom: dict[str, list], max_rows: int = 24) -> str:
    """Flow-aware corrections per breakpoint: STRUCTURE (row/column arrangement differs), then per-row
    GAP corrections (the margin change above each row — fixing a gap moves everything below it, so these
    do not double-count the way absolute positions do), x offsets, and font-size / wrapping errors."""
    out = []
    for bp, frame in spec["breakpoints"].items():
        rendered = [e for e in dom.get(bp, []) if e.get("text")]
        items = _pairs(frame, rendered)
        found = [i for i in items if i["r"] is not None]
        lines = [f"{bp}:"]
        for i in items:
            if i["r"] is None:
                lines.append(f"  MISSING {_tag(i)} (design x={i['d'][0]}, y={i['d'][1]})")
        if not found:
            out += lines + ["  (no matched text)"]
            continue
        drows = _rows(found, "d")
        rid = {id(i): k for k, row in enumerate(_rows(found, "r")) for i in row}
        # structure: items side by side in one but not the other
        notes = []
        for row in drows:
            if len(row) >= 2 and len({rid[id(i)] for i in row}) > 1:
                xs = ", ".join(f"x={i['d'][0]}" for i in row)
                notes.append(f"design puts {', '.join(_tag(i) for i in row)} SIDE BY SIDE ({xs}); render stacks them")
        rrows = _rows(found, "r")
        drow_of = {id(i): k for k, row in enumerate(drows) for i in row}
        for row in rrows:
            if len(row) >= 2 and len({drow_of[id(i)] for i in row}) > 1:
                notes.append(f"render puts {', '.join(_tag(i) for i in row[:6])} side by side; design stacks them "
                             f"(design x: {sorted({i['d'][0] for i in row})})")
        # columns: repeated design rows with the same x set = a grid
        sig = {}
        for row in drows:
            if len(row) >= 2:
                sig.setdefault(tuple(round(i["d"][0] / 8) for i in row), []).append(row)
        for xs, rows_ in sig.items():
            # only when the render does NOT already reproduce the grid (items of a design row split across render rows)
            if len(rows_) >= 2 and any(len({rid[id(i)] for i in r}) > 1 for r in rows_):
                lefts = [i["d"][0] for i in rows_[0]]
                notes.append(f"design has a {len(lefts)}-column grid ({len(rows_)} rows) with columns at x={lefts}: "
                             f"{', '.join(_tag(r[0]) for r in rows_[:4])}…")
        if notes:
            lines.append("  STRUCTURE (fix with the parent's flex/grid, not per-item margins):")
            lines += [f"   - {n}" for n in notes[:6]]
        # vertical gaps between consecutive design rows (only rows the render keeps together)
        lines.append("  ROWS top→bottom (step = distance from the previous row's top to this row's top; change the space ABOVE this row by Δ — everything below moves with it):")
        prev_d = prev_r = None
        for k, row in enumerate(drows[:max_rows]):
            d_top = min(i["d"][1] for i in row)
            r_top = min(i["r"][1] for i in row)
            head = _tag(row[0]) + (f" +{len(row) - 1} more" if len(row) > 1 else "")
            if prev_d is None:
                dg, rg = d_top, r_top
                what = "top of page"
            else:
                dg, rg = d_top - prev_d, r_top - prev_r
                what = "step"
            parts = []
            if abs(dg - rg) > 4:
                parts.append(f"{what} {rg}→{dg} (Δ {dg - rg:+d}px)")
            dx = row[0]["d"][0] - row[0]["r"][0]
            if abs(dx) > 6:
                parts.append(f"x {row[0]['r'][0]}→{row[0]['d'][0]} (Δ {dx:+d}px)")
            for i in row:
                if i.get("size") and i.get("rsize") and abs(i["rsize"] - i["size"]) >= 2:
                    parts.append(f"{_tag(i)} font {i['rsize']:.0f}→{i['size']}px")
                # wrapping = different number of lines (height), not a different box width: block elements span
                # their container, so comparing widths flagged wrapping that wasn't there
                dh, rh = i["d"][3], i["r"][3]
                if i.get("size") and max(dh, rh) > 1.6 * min(dh, rh) and max(dh, rh) - min(dh, rh) > 0.8 * i["size"]:
                    parts.append(f"{_tag(i)} wraps differently: {round(rh / (1.25 * i['size'])) or 1}→"
                                 f"{round(dh / (1.25 * i['size'])) or 1} lines (adjust its width / font size)")
            lines.append(f"   {k + 1}. {head}: " + ("; ".join(parts) if parts else "ok"))
            prev_d, prev_r = d_top, r_top   # top-to-top: robust to odd element heights (e.g. 1 px input boxes)
        out += lines
    return "\n".join(out)


def _block_anchor(pc, nodes: list[dict]) -> dict | None:
    """The element whose margin really moves a row: the OUTERMOST block-level ancestor-or-self of the text
    element `pc` that starts at the same y (vertical margins on inline elements do nothing). None if the id
    is rendered more than once (inside a .map — one id, many rows: that is a structure fix, not a margin)."""
    idxs = [i for i, n in enumerate(nodes) if n.get("pc") == str(pc)]
    if len(idxs) != 1:
        return None
    i = idxs[0]
    top = (nodes[i].get("b") or [0, 0, 0, 0])[1]
    best = None if nodes[i].get("inl") else i
    j = nodes[i].get("par", -1)
    while j is not None and j >= 0:
        n = nodes[j]
        if abs((n.get("b") or [0, -999, 0, 0])[1] - top) > 2:
            break
        if not n.get("inl") and n.get("pc") is not None and sum(1 for m in nodes if m.get("pc") == n.get("pc")) == 1:
            best = j
        j = n.get("par", -1)
    return nodes[best] if best is not None else None


def computed_pins(edits: list[dict], dom: dict, nodes: dict) -> list[dict]:
    """Attach the OTHER breakpoints' computed values for inherited / parent-set properties, so scoping can pin
    them exactly (class-derived defaults were wrong for space-y margins and inherited font weight/size)."""
    order = {"mobile": ["tablet", "desktop"], "tablet": ["desktop"], "desktop": []}
    for e in edits:
        if e.get("bp") not in order:
            continue
        add = e.get("add", "")
        pins = {}
        for other in order[e["bp"]]:
            n = next((x for x in nodes.get(other, []) if x.get("pc") == str(e["id"])), None)
            d = next((x for x in dom.get(other, []) if str(x.get("pc")) == str(e["id"])), None)
            vals = []
            if "mt-" in add and n is not None:
                v = int(n.get("mt", 0))
                vals.append(f"!mt-[{v}px]" if v >= 0 else f"!-mt-[{-v}px]")
            if "font-" in add and d is not None and d.get("font_weight"):
                w = min((400, 500, 600, 700), key=lambda x: abs(x - int(float(d["font_weight"]))))
                vals.append({400: "font-normal", 500: "font-medium", 600: "font-semibold", 700: "font-bold"}[w])
            if "text-[" in add and "px]" in add and n is not None and n.get("fs"):
                vals.append(f"text-[{int(n['fs'])}px]")
            if vals:
                pins[other] = vals
        if pins:
            e["pins"] = pins
    return edits


def auto_edits(spec: dict, dom: dict[str, list], nodes: dict[str, list], min_step: int = 4) -> list[dict]:
    """Deterministic fixes from measurements (no model): per breakpoint, each row's step error becomes a
    margin delta on the element that really moves that row; font-size errors become text-[Npx]."""
    edits = []
    # margin collapse: the first child's margin-top escaped through the root, so the page (and its background)
    # starts below y=0 → flow-root on the root contains it (seen in a live run: white band above a dark page)
    for bp in spec["breakpoints"]:
        roots = [n for n in nodes.get(bp, []) if n.get("par", -1) == -1 and n.get("pc") is not None]
        if roots and (roots[0].get("b") or [0, 0])[1] > 0 and not any(e.get("add") == "flow-root" for e in edits):
            edits.append({"id": int(roots[0]["pc"]), "bp": "all", "add": "flow-root", "why": "root margin collapse"})
    for bp, frame in spec["breakpoints"].items():
        found = [i for i in _pairs(frame, [e for e in dom.get(bp, []) if e.get("text")]) if i["r"] is not None]
        if not found:
            continue
        drows = _rows(found, "d")
        rrow = {id(i): k for k, row in enumerate(_rows(found, "r")) for i in row}
        drow = {id(i): k for k, row in enumerate(drows) for i in row}
        prev_d = prev_r = None
        for row in drows:
            d_top, r_top = min(i["d"][1] for i in row), min(i["r"][1] for i in row)
            delta = (d_top - r_top) if prev_d is None else (d_top - prev_d) - (r_top - prev_r)
            first = min(row, key=lambda i: i["r"][1])
            anchor = _block_anchor(first["id"], nodes.get(bp, [])) if first["id"] is not None else None
            # rows whose arrangement differs between design and render are a STRUCTURE fix (moving them with
            # margins pulled grid rows on top of each other in a live run → overlap → DQ)
            same_render_row = len({rrow[id(i)] for i in row}) == 1
            mixed = any(drow[id(j)] != drow[id(row[0])] for j in found if rrow[id(j)] == rrow[id(row[0])])
            if abs(delta) > min_step and anchor is not None and same_render_row and not mixed:
                # computed margin from the browser (parent space-y / gap rules don't show in the child's classes);
                # "!" so the new value wins over a parent's space-y selector
                v = int(anchor.get("mt", 0)) + int(delta)
                cls = f"!mt-[{v}px]" if v >= 0 else f"!-mt-[{-v}px]"
                edits.append({"id": int(anchor["pc"]), "bp": bp, "add": cls, "why": f"row step {delta:+d}px"})
            for i in row:
                if i["id"] is not None and i.get("size") and i.get("rsize") and abs(i["rsize"] - i["size"]) >= 2:
                    edits.append({"id": int(i["id"]), "bp": bp, "add": f"text-[{int(i['size'])}px]", "why": "font size"})
            prev_d, prev_r = d_top, r_top
        edits += _column_fix(bp, drows, found, rrow, drow, nodes.get(bp, []))
    return computed_pins(edits, dom, nodes)


def _ancestors(nodes: list[dict], i: int) -> list[int]:
    out = []
    while i is not None and i >= 0 and len(out) < 64:
        out.append(i)
        i = nodes[i].get("par", -1)
    return out


def _column_fix(bp, drows, found, rrow, drow, nodes) -> list[dict]:
    """If ≥ 2 consistent rows share the same x error, the column container is off (padding/margin), not each
    row: shift the content of their lowest common block ancestor by Δ via its padding (both sides, so a centred,
    fixed-width container stays centred)."""
    groups: dict[int, list] = {}
    for row in drows:
        if len({rrow[id(i)] for i in row}) != 1:
            continue
        first = row[0]
        dx = first["d"][0] - first["r"][0]
        if abs(dx) > 6 and first["id"] is not None:
            groups.setdefault(round(dx / 4), []).append((first, dx))
    out = []
    for _, items in groups.items():
        if len(items) < 2:
            continue
        idxs = []
        for it, _dx in items:
            m = [k for k, n in enumerate(nodes) if n.get("pc") == str(it["id"])]
            if len(m) == 1:
                idxs.append(m[0])
        if len(idxs) < 2:
            continue
        common = set(_ancestors(nodes, idxs[0]))
        for k in idxs[1:]:
            common &= set(_ancestors(nodes, k))
        lca = next((a for a in _ancestors(nodes, idxs[0]) if a in common and not nodes[a].get("inl")
                    and nodes[a].get("pc") is not None and sum(1 for n in nodes if n.get("pc") == nodes[a]["pc"]) == 1), None)
        if lca is None:
            continue
        dx = round(sum(d for _, d in items) / len(items))
        n = nodes[lca]
        pl, pr = int(n.get("pl", 0)) + dx, int(n.get("pr", 0)) - dx if False else int(n.get("pr", 0))
        if pl < 0:
            continue
        out.append({"id": int(n["pc"]), "bp": bp, "add": f"!pl-[{pl}px]", "why": f"column x {dx:+d}px"})
    return out


def visual_checks(spec: dict, targets: dict, renders: dict, dom: dict, nodes: dict) -> tuple[str, list[dict]]:
    """Blocks / borders / rules / font weight, measured on both images (see visual_diff.py)."""
    from .visual_diff import block_diff, weight_diff
    lines, edits = [], []
    for bp, frame in spec["breakpoints"].items():
        if f"{bp}.png" not in renders or bp not in targets:
            continue
        dtb = [t["box"] for t in frame["texts"] if t.get("box")]
        rtb = [e["box"] for e in dom.get(bp, []) if e.get("text") and e.get("box")]
        f1, e1 = block_diff(bp, targets[bp], renders[f"{bp}.png"], nodes.get(bp, []), dtb, rtb)
        pairs = _pairs(frame, [e for e in dom.get(bp, []) if e.get("text")])
        f2, e2 = weight_diff(bp, targets[bp], renders[f"{bp}.png"], pairs, dom.get(bp, []))
        if f1 or f2:
            lines.append(f"{bp}:")
            lines += [f"  - {x}" for x in (f1 + f2)[:14]]
        edits += e1 + e2
    edits = computed_pins(edits, dom, nodes)
    return ("BLOCKS / RULES / WEIGHT (measured on both images):\n" + "\n".join(lines)) if lines else "", edits


def report_summary(report: dict) -> str:
    if report.get("disqualified"):
        why = report.get("reason") or report.get("integrity_failures") or report.get("lint", {}).get("violations")
        return f"DISQUALIFIED (score 0): {why}"
    out = [f"Match (worst breakpoint) = {report['match']:.1f}; worst = {report['worst']}"]
    for bp, v in report["breakpoints"].items():
        c = v["components"]
        out.append(f"{bp}: {v['score']:.1f} (structure {c['structure']:.2f}, layout {c['layout']:.2f}, "
                   f"colour {c['color']:.2f}, text {c.get('text', 1):.2f}; offset {v.get('offset_px', [0, 0])} px (dy, dx))")
        regs = [f"{r['kind']} at [{','.join(map(str, r['box']))}]" for r in v.get("regions", [])[:5]]
        if regs:
            out.append("   biggest differences: " + "; ".join(regs))
        if v.get("missing_text"):
            out.append("   design text not readable in render: " + "; ".join(v["missing_text"][:6]))
    bad = {w: v for w, v in (report.get("between") or {}).items() if v.get("overflow_px") or v.get("text_overlaps")}
    if bad:
        out.append("in-between widths with problems: " + "; ".join(
            f"{w}px: overflow {v['overflow_px']}px, {v['text_overlaps']} text overlaps" for w, v in bad.items()))
    return "\n".join(out)


VISUAL_PROMPT = """Image 1 is the DESIGN, image 2 is an IMPLEMENTATION of it ({bp}, {w}x{h}px).
List the most important visible differences, biggest first (max 8). Be concrete: name the element by its text,
say what differs (position, size, colour, alignment, wrapping, missing or extra element, spacing) and which way to change it.
Reply as JSON: {{"differences": ["...", "..."]}}"""


def visual_notes(client: TFClient, bp: str, design_png: bytes, render_png: bytes) -> list[str]:
    w, h = config.BREAKPOINTS[bp]
    msg = [{"role": "user", "content": [{"type": "text", "text": VISUAL_PROMPT.format(bp=bp, w=w, h=h)},
                                        image_part(design_png), image_part(render_png)]}]
    r = client.chat(config.MODEL_VISION, msg, step=f"visual diff {bp}", max_tokens=800, temperature=0.0)
    d = parse_json(r.content)
    diffs = d.get("differences") if isinstance(d, dict) else None
    return [str(x) for x in diffs][:8] if isinstance(diffs, list) else []


STRATEGY_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string"},
        "strategies": {
            "type": "array", "minItems": 3, "maxItems": 3,
            "items": {"type": "object", "properties": {
                "title": {"type": "string"}, "target_breakpoint": {"type": "string"},
                "instructions": {"type": "string"}, "risk": {"type": "string"}},
                "required": ["title", "target_breakpoint", "instructions", "risk"], "additionalProperties": False},
        },
    },
    "required": ["diagnosis", "strategies"], "additionalProperties": False,
}

CRITIC_SYSTEM = """You are a principal front-end engineer reviewing a React + Tailwind page that must match a design at
three viewports (mobile 390, tablet 768 = md:, desktop 1280 = xl:) from ONE DOM tree. The score is the WORST breakpoint,
so fix the worst one without breaking the others. You get exact measurements; trust them over impressions.
Every strategy must aim to fix ALL the measured position/size/missing issues of the worst breakpoint (and any other
breakpoint it can fix without harm) — not one issue each. The 3 strategies differ in APPROACH:
  1. "edit": keep the current structure, correct the values (classes, px) element by element;
  2. "restructure": rebuild the layout containers (column width/position, alignment, stacking, spacing model) to match
     the measured column and y positions, then re-place the elements;
  3. "rewrite": what a fresh implementation should do differently, as a list of rules learned from this attempt's
     mistakes (it will be written from scratch from the spec).
Be concrete (name elements by their text, give Tailwind classes and px values from the measurements). State each
strategy's cross-breakpoint risk. Reply with JSON only, matching the schema."""


def critique(client: TFClient, code: str, report: dict, diff_text: str, notes: dict[str, list[str]]) -> dict:
    visual = "\n".join(f"{bp}: " + " | ".join(n) for bp, n in notes.items() if n) or "(none)"
    user = ("Current App.jsx:\n```jsx\n" + code + "\n```\n\nSCORES:\n" + report_summary(report) +
            "\n\nELEMENT POSITIONS (render → design):\n" + diff_text +
            "\n\nVISUAL DIFFERENCES (vision model, may be imprecise):\n" + visual +
            "\n\nJSON schema:\n" + json.dumps(STRATEGY_SCHEMA))
    r = client.chat(config.MODEL_CRITIC, [{"role": "system", "content": CRITIC_SYSTEM}, {"role": "user", "content": user}],
                    step="critique", schema=STRATEGY_SCHEMA, thinking=config.CRITIC_THINKING, max_tokens=6000)
    d = r.data if isinstance(r.data, dict) else parse_json(r.content) or parse_json(r.reasoning)
    if not isinstance(d, dict) or not isinstance(d.get("strategies"), list) or not d["strategies"]:
        raise ValueError(f"critique unparseable: {r.content[:300]!r}")
    return d


def feedback_text(report: dict, diff_text: str, notes: dict[str, list[str]]) -> str:
    """What the coder sees for a revision (same facts as the critic, minus the strategy list)."""
    visual = "\n".join(f"{bp}: " + " | ".join(n) for bp, n in notes.items() if n)
    return report_summary(report) + "\n\nELEMENT POSITIONS (render → design):\n" + diff_text + (
        "\n\nVISUAL DIFFERENCES (vision model):\n" + visual if visual else "")
