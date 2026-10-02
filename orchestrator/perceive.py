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


def _repair_json(text: str):
    """Fix the malformations seen from the vision model: number arrays without commas ("[275 20 345 40]"), raw
    newlines inside strings, trailing commas. Returns parsed JSON or None."""
    t = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", (text or "").strip())
    t = re.sub(r"\[(\s*-?\d+(?:\.\d+)?(?:\s+-?\d+(?:\.\d+)?)+\s*)\]",
               lambda m: "[" + ", ".join(m.group(1).split()) + "]", t)
    out, in_str, esc = [], False, False
    for ch in t:                       # escape raw newlines that occur inside strings
        if in_str and ch == "\n":
            out.append("\\n")
            continue
        out.append(ch)
        if esc:
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == '"':
            in_str = not in_str
    t = re.sub(r",\s*([}\]])", r"\1", "".join(out))
    return parse_json(t)


def read_frame(client: TFClient, bp: str, png: bytes) -> dict:
    w, h = config.BREAKPOINTS[bp]
    msg = [{"role": "user", "content": [{"type": "text", "text": FRAME_PROMPT.format(w=w, h=h, bp=bp)}, image_part(png)]}]
    last = ""
    for attempt, temp in enumerate((0.0, 0.3)):
        r = client.chat(config.MODEL_VISION, msg, step=f"perceive {bp}", max_tokens=6000, temperature=temp)
        last = r.content or ""
        for data in (parse_json(last), _repair_json(last)):
            if isinstance(data, dict) and isinstance(data.get("texts"), list):
                data["size"] = [w, h]
                return data
    raise ValueError(f"perceive {bp}: unparseable vision output: {last[:300]!r}")


def ocr_fallback(meas: dict) -> dict:
    """When the vision model fails on a frame: texts straight from OCR, roles guessed from size and position."""
    lines = meas["text_lines"]
    sizes = sorted(((l.get("typo") or {}).get("size_px") or l["box"][3]) for l in lines)
    big = sizes[-1] if sizes else 0
    texts = []
    for l in lines:
        fs = (l.get("typo") or {}).get("size_px") or l["box"][3]
        inside = any(_frac(l["box"], b["box"]) > 0.8 and b["box"][3] <= 64 for b in meas["blocks"])
        role = "heading" if fs >= max(big * 0.8, 22) else "button" if inside else "body"
        texts.append({"text": l["text"], "role": role, "box": l["box"], "size_px": fs})
    return {"texts": texts, "blocks": [], "layout": "", "fallback": "ocr"}


def _frac(box, outer) -> float:
    x, y, w, h = box
    iw = max(0, min(x + w, outer[0] + outer[2]) - max(x, outer[0]))
    ih = max(0, min(y + h, outer[1] + outer[3]) - max(y, outer[1]))
    return (iw * ih) / (w * h) if w * h else 0.0


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower().lstrip("| ")


def _sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if len(a) <= 3 and (b == a or b.startswith(a + " ") or b.startswith(a + ".") or b.split()[0] == a):
        return 0.95   # short strings ("$20") as the first word / prefix of an OCR line ("$20...")
    if len(a) > 3 and (a in b or b in a):
        return 0.95 * min(len(a), len(b)) / max(len(a), len(b)) + 0.05 if a != b else 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


INK_NO_DESC, INK_DESC = 0.785, 0.982       # Inter, calibrated in our renderer (sandbox/calib.mjs, Oct 1)


def font_px(text: str, ink_w: float, ink_h: float, hint) -> int:
    """Median of independent font-size estimates — ink height, ink width per character, the vision model's guess.
    OCR boxes can include stray glyphs (an input caret read as '|'), and the vision model guesses sizes."""
    t = re.sub(r"^\|\s*", "", text.strip())
    desc = bool(re.search(r"[gjpqy,;]", t))
    est = [ink_h / (INK_DESC if desc else INK_NO_DESC)]
    if len(t) >= 3:
        est.append(ink_w / (len(t) * (0.483 if desc else 0.552)))
    if hint:
        est.append(float(hint))
    est.sort()
    mid = est[len(est) // 2] if len(est) % 2 else (est[len(est) // 2 - 1] + est[len(est) // 2]) / 2
    return max(8, int(round(mid)))


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
    # candidates: single OCR lines and joins of 2–3 vertically consecutive lines (wrapped headings/paragraphs:
    # OCR returns "Enter your info to sign" and "in" separately)
    cands = [([i], l["text"], l["box"]) for i, l in enumerate(lines)]
    for i, a in enumerate(lines):
        group, box = [i], list(a["box"])
        for j, b in enumerate(lines):
            if j <= i or len(group) >= 3:
                continue
            gap = b["box"][1] - (box[1] + box[3])
            if 0 <= gap <= max(a["box"][3], 8) * 1.2 and abs(b["box"][0] - a["box"][0]) <= max(40, a["box"][2] * 0.5):
                group = group + [j]
                x0, y0 = min(box[0], b["box"][0]), min(box[1], b["box"][1])
                x1 = max(box[0] + box[2], b["box"][0] + b["box"][2])
                y1 = max(box[1] + box[3], b["box"][1] + b["box"][3])
                box = [x0, y0, x1 - x0, y1 - y0]
                cands.append((list(group), " ".join(lines[k]["text"] for k in group), list(box)))
    for t in vlm.get("texts", []):
        best, score = None, 0.0
        for c in cands:
            if any(k in used for k in c[0]):
                continue
            sc = _sim(t.get("text", ""), c[1])
            if sc > score:
                best, score = c, sc
        item = {"text": t.get("text", ""), "role": t.get("role", "other"),
                "size_px": t.get("size_px"), "weight": t.get("weight")}
        # ≥ 0.9 (or containment, which _sim scores ≥ 0.95): "Continue with Google" vs an OCR line "Continue with
        # Email" scored 0.8 and stole its box when OCR missed the white-on-dark Google label
        if best is not None and score >= 0.9:
            idxs, _, box = best
            first = lines[idxs[0]]
            if len(idxs) > 1 or _norm(first["text"]) == _norm(t.get("text", "")) or score >= 0.95:
                used.update(idxs)
            item.update(box=box, color=first["color"], on=first["backdrop"], measured=True, lines=len(idxs),
                        line_boxes=[lines[k]["box"] for k in idxs])
            ty = first.get("typo") or {}
            item["size_px"] = ty.get("size_px") or font_px(first["text"], first["box"][2], first["box"][3], t.get("size_px"))
            if ty:
                item.update(weight=ty["weight"], tracking_em=ty["tracking_em"], top_em=ty["top_em"],
                            underline=ty.get("underline", False))
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
    def safe_read(kv):
        try:
            return read_frame(client, *kv)
        except ValueError:
            return None
    with ThreadPoolExecutor(len(frames)) as ex:
        vlm = dict(zip(frames, ex.map(safe_read, frames.items())))
        meas = dict(zip(frames, ex.map(lambda kv: measure(kv[1]), frames.items())))
    for bp in frames:   # a frame the vision model couldn't read still gets a spec (OCR-only, flagged)
        if vlm[bp] is None:
            vlm[bp] = ocr_fallback(meas[bp])
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
