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
