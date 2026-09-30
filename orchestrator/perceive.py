"""Perceive: the vision model reads each design frame once → spec.json (human-editable).

The spec is the ONLY view of the design the coder ever gets (plus text critiques later).
"""
from __future__ import annotations

import difflib
import json
import re
from concurrent.futures import ThreadPoolExecutor

from . import config
from .measure import measure
from .tf_client import TFClient, image_part, parse_json

FRAME_PROMPT = """You are a senior front-end engineer reading a UI design at {w}x{h} px ({bp} breakpoint).
Describe it precisely enough that someone who cannot see it could rebuild it in HTML/CSS.

Return JSON only, exactly this shape:
{{
  "background": "#rrggbb",
  "texts": [{{"text": "exact visible text", "role": "heading|subheading|body|label|button|link|input-placeholder|nav|caption|other",
             "box": [x, y, w, h], "color": "#rrggbb", "size_px": 16, "weight": 400}}],
  "blocks": [{{"kind": "button|input|card|panel|divider|image-placeholder|navbar|badge|other",
              "box": [x, y, w, h], "fill": "#rrggbb", "border": "#rrggbb or none", "radius_px": 0}}],
  "layout": "2-5 sentences: columns, alignment, spacing, what sits beside or below what"
}}
Rules: list EVERY visible text exactly as written, top-to-bottom; boxes are pixels in this {w}x{h} image;
solid grey rectangles are image placeholders; colours as hex; do not invent anything that is not visible."""


def read_frame(client: TFClient, bp: str, png: bytes) -> dict:
    w, h = config.BREAKPOINTS[bp]
    msg = [{"role": "user", "content": [{"type": "text", "text": FRAME_PROMPT.format(w=w, h=h, bp=bp)}, image_part(png)]}]
    for attempt in range(2):
        r = client.chat(config.MODEL_VISION, msg, step=f"perceive {bp}", max_tokens=6000, temperature=0.0)
        data = parse_json(r.content)
        if isinstance(data, dict) and isinstance(data.get("texts"), list):
            data["size"] = [w, h]
            return data
    raise ValueError(f"perceive {bp}: unparseable vision output: {r.content[:300]!r}")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower().lstrip("| ")


def _sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if len(a) > 3 and (a in b or b in a):
        return 0.95 * min(len(a), len(b)) / max(len(a), len(b)) + 0.05 if a != b else 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def merge(vlm: dict, meas: dict) -> dict:
    """Gemma's strings/roles/semantics + measured boxes/colours → one frame spec.

    Each VLM text is matched to the best unused OCR line (≥ 0.75 similarity, allowing the
    VLM string to be part of a longer OCR line). Unmatched texts get a position interpolated
    from their matched neighbours in reading order and snap into an unlabelled block (e.g. a
    button whose white-on-colour label OCR missed); they are flagged "approx".
    """
    lines = meas["text_lines"]
    used: set[int] = set()
    texts = []
    for t in vlm.get("texts", []):
        best, score = None, 0.0
        for i, l in enumerate(lines):
            if i in used:
                continue
            s = _sim(t.get("text", ""), l["text"])
            if s > score:
                best, score = i, s
        item = {"text": t.get("text", ""), "role": t.get("role", "other"),
                "size_px": t.get("size_px"), "weight": t.get("weight")}
        if best is not None and score >= 0.75:
            l = lines[best]
            if _norm(l["text"]) == _norm(t.get("text", "")) or score >= 0.95:
                used.add(best)
            item.update(box=l["box"], color=l["color"], on=l["backdrop"], measured=True)
            # ink height ≈ 0.72–0.95 × font size for Inter depending on ascenders/descenders
            item["size_px"] = item["size_px"] or round(l["box"][3] / 0.8)
        else:
            item.update(box=None, color=t.get("color"), measured=False)
        texts.append(item)
    # interpolate unmatched positions from neighbours, then snap into empty blocks
    empty_blocks = [b for b in meas["blocks"] if not b.get("contains_text")]
    for i, it in enumerate(texts):
        if it["box"] is not None:
            continue
        prev = next((texts[j]["box"] for j in range(i - 1, -1, -1) if texts[j]["box"] and texts[j]["measured"]), None)
        nxt = next((texts[j]["box"] for j in range(i + 1, len(texts)) if texts[j]["box"] and texts[j]["measured"]), None)
        y_lo = prev[1] + prev[3] if prev else 0
        y_hi = nxt[1] if nxt else meas["size"][1]
        cands = [b for b in empty_blocks if y_lo - 4 <= b["box"][1] and b["box"][1] + b["box"][3] <= y_hi + 4]
        if cands and it["role"] in ("button", "input-placeholder", "badge", "link", "nav", "other", "label"):
            b = cands[0]
            empty_blocks.remove(b)
            bx, by, bw, bh = b["box"]
            size = it["size_px"] or 16
            it["box"] = [bx + 12, by + (bh - size) // 2, max(bw - 24, 10), size]
            it["inside_block"] = b["box"]
            it["on"] = b["fill"]
            b["contains_text"] = [it["text"]]
        else:
            it["box"] = [prev[0] if prev else 0, (y_lo + y_hi) // 2 - 8, 200, 16]
        it["approx"] = True
    return {
        "size": meas["size"],
        "background": meas["background"],
        "texts": texts,
        "blocks": [{k: v for k, v in b.items()} for b in meas["blocks"]],
        "layout": vlm.get("layout", ""),
        "vlm_blocks": [{"kind": b.get("kind"), "fill": b.get("fill")} for b in vlm.get("blocks", [])][:20],
    }


def layout_facts(frame: dict) -> str:
    """Content column and text alignment derived from measured boxes (the coder kept centring
    left-aligned text when it had to infer this from raw x values)."""
    W = frame["size"][0]
    ts = [t for t in frame["texts"] if t.get("measured") and t["box"]]
    if not ts:
        return "no measured text"
    # anchor on the largest measured text (the heading), not the most common edge (footer links win that)
    anchor = max(ts, key=lambda t: (t.get("size_px") or 0, -t["box"][1]))
    best = anchor["box"][0]
    aligned = [t for t in ts if abs(t["box"][0] - best) <= 4]
    right = max(t["box"][0] + t["box"][2] for t in aligned)
    blocks = [b["box"] for b in frame["blocks"] if abs(b["box"][0] - best) <= 6]
    if blocks:
        right = max(right, max(b[0] + b[2] for b in blocks))
    width = right - best
    margin_r = W - right
    centred = abs(best - margin_r) <= 12
    col = (f"main content column x={best}..{right} (width {width}px, " +
           (f"horizontally centred in the {W}px viewport" if centred else f"{best}px from the left edge") + ")")
    n_left = len(aligned)
    centre_x = best + width / 2
    n_centre = sum(1 for t in ts if abs(t["box"][0] + t["box"][2] / 2 - centre_x) <= 6 and abs(t["box"][0] - best) > 4)
    align = (f"{n_left}/{len(ts)} measured texts are LEFT-aligned to x={best}" +
             (f", {n_centre} are centred in the column" if n_centre else "") + ".")
    return col + "; " + align + " Vertical rhythm (top-to-bottom, gap = this top − previous bottom): " + rhythm(frame)


def rhythm(frame: dict) -> str:
    """Measured vertical gaps between consecutive elements (texts and blocks, merged when one
    contains the other) — the numbers a developer would read from Figma's inspect panel."""
    items = []
    for b in frame["blocks"]:
        label = (b.get("contains_text") or ["(block)"])[0]
        items.append((b["box"][1], b["box"][1] + b["box"][3], f"[{label[:28]}] box h{b['box'][3]}"))
    for t in frame["texts"]:
        if not t.get("measured") or not t["box"]:
            continue
        x, y, w, h = t["box"]
        inside = any(bx - 3 <= x and by - 3 <= y and x + w <= bx + bw + 3 and y + h <= by + bh + 3 for bx, by, bw, bh in (b["box"] for b in frame["blocks"]))
        if not inside:
            items.append((y, y + h, f"'{t['text'][:28]}'"))
    items.sort()
    out, prev_bottom = [], 0
    for top, bottom, label in items[:18]:
        out.append(f"{label} at y={top} (gap {top - prev_bottom})")
        prev_bottom = max(prev_bottom, bottom)
    return "; ".join(out)


def perceive(client: TFClient, frames: dict[str, bytes]) -> dict:
    """frames: {bp: png}. Returns {"breakpoints": {bp: merged frame spec}}. Frames read in parallel."""
    with ThreadPoolExecutor(len(frames)) as ex:
        vlm = dict(zip(frames, ex.map(lambda kv: read_frame(client, *kv), frames.items())))
        meas = dict(zip(frames, ex.map(lambda kv: measure(kv[1]), frames.items())))
    return {"breakpoints": {bp: merge(vlm[bp], meas[bp]) for bp in frames}, "raw_vlm": vlm}


def spec_for_prompt(spec: dict) -> str:
    """Cross-breakpoint table for the coder: each element ONCE, with its box at every breakpoint.

    Three independent per-frame lists made the coder (a) re-create measured blocks as extra
    overlay divs and (b) treat content absent from a short frame as non-existent, when it is
    below the fold. This format makes the one-DOM-tree mapping explicit.
    """
    bps = list(spec["breakpoints"])
    frames = spec["breakpoints"]
    order = max(bps, key=lambda b: len(frames[b]["texts"]))           # frame listing the most texts
    rows, seen = [], set()
    for src in [order] + [b for b in bps if b != order]:
        for t in frames[src]["texts"]:
            key = _norm(t["text"])
            if not key or key in seen:
                continue
            seen.add(key)
            cells = []
            for bp in bps:
                m = next((x for x in frames[bp]["texts"] if _sim(x["text"], t["text"]) >= 0.9), None)
                if m is None:
                    cells.append("not in frame")
                    continue
                x, y, w, h = m["box"]
                tag = "~" if m.get("approx") else ""
                cells.append(f"{tag}[{x},{y},{w},{h}] {m.get('size_px') or '?'}px {m.get('color') or ''} on {m.get('on') or '?'}")
            rows.append(f"| {t['text'][:80]} | {t['role']} | " + " | ".join(cells) + " |")
    out = ["ELEMENTS (each text once; box = [x,y,w,h] px in that frame; ~ = estimated; 'not in frame' = hidden at "
           "that size OR below the fold of that frame — keep it in the DOM unless it is clearly desktop-only):",
           "| text | role | " + " | ".join(f"{bp} {frames[bp]['size'][0]}x{frames[bp]['size'][1]}" for bp in bps) + " |",
           "|---|---|" + "---|" * len(bps)] + rows
    out.append("\nBLOCKS (filled or bordered boxes measured in the design; these ARE the inputs/buttons/cards/panels — "
               "style the corresponding element with this box, do not add extra overlay divs):")
    for bp in bps:
        f = frames[bp]
        out.append(f"{bp}: page background {f['background']}")
        for b in f["blocks"][:25]:
            label = f" contains {b['contains_text'][:2]}" if b.get("contains_text") else " (no text: placeholder/decoration)"
            border = f" border {b['border']}" if b.get("border") else ""
            out.append(f"  - [{','.join(map(str, b['box']))}] fill {b['fill']}{border}{label}")
    out.append("\nMEASURED LAYOUT FACTS:")
    for bp in bps:
        out.append(f"{bp}: " + layout_facts(frames[bp]))
    out.append("\nLAYOUT (from the vision model):")
    for bp in bps:
        out.append(f"{bp}: {frames[bp].get('layout', '')}")
    return "\n".join(out)
