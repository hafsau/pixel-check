"""Perceive: the vision model reads each design frame once → spec.json (human-editable).

The spec is the ONLY view of the design the coder ever gets (plus text critiques later).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

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


def read_frame(client: TFClient, bp: str, png: bytes, model: str | None = None) -> dict:
    w, h = config.BREAKPOINTS[bp]
    msg = [{"role": "user", "content": [{"type": "text", "text": FRAME_PROMPT.format(w=w, h=h, bp=bp)}, image_part(png)]}]
    last = ""
    for attempt, temp in enumerate((0.0, 0.3)):
        r = client.chat(model or config.MODEL_VISION, msg, step=f"perceive {bp}", max_tokens=8000, temperature=temp)
        last = r.content or ""
        for data in (parse_json(last), _repair_json(last)):
            if isinstance(data, dict) and isinstance(data.get("texts"), list):
                data["size"] = [w, h]
                return data
    raise ValueError(f"perceive {bp}: unparseable vision output: {last[:300]!r}")


def hedged_read(client: TFClient, bp: str, png: bytes, hedge_after_s: float | None, model: str | None = None) -> dict:
    """read_frame with one backup request when the first has not answered after `hedge_after_s` (Token Factory's
    vision latency has a long tail: median 25 s, p90 56 s, max 293 s over 277 reads). The first valid answer wins;
    the slower request is left to finish in the background (its cost is still recorded in the ledger)."""
    if not hedge_after_s:
        return read_frame(client, bp, png, model)
    ex = ThreadPoolExecutor(2)
    try:
        pending = {ex.submit(read_frame, client, bp, png, model)}
        done, _ = wait(pending, timeout=hedge_after_s)
        if not done:
            pending.add(ex.submit(read_frame, client, bp, png, model))
        err = None
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for f in done:
                try:
                    return f.result()
                except ValueError as e:
                    err = e
        raise err
    finally:
        ex.shutdown(wait=False)


class VisionCache:
    """Vision reads keyed by frame bytes + model + breakpoint + prompt: a frame already read costs nothing and
    reads the same way again. Only valid reads are stored; an unreadable entry is ignored."""
    def __init__(self, root):
        self.root = Path(root)

    def key(self, bp: str, png: bytes, model: str) -> str:
        h = hashlib.sha256()
        for part in (model.encode(), bp.encode(), FRAME_PROMPT.encode(), png):
            h.update(hashlib.sha256(part).digest())
        return h.hexdigest()

    def get(self, k: str) -> dict | None:
        try:
            data = json.loads((self.root / f"{k}.json").read_text())
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and isinstance(data.get("texts"), list) else None

    def put(self, k: str, data: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f"{k}.tmp"
        tmp.write_text(json.dumps(data))
        tmp.replace(self.root / f"{k}.json")


def cached_read(client: TFClient, bp: str, png: bytes, cache: VisionCache | None, hedge_after_s: float | None,
                model: str | None = None) -> dict:
    model = model or config.MODEL_VISION
    k = cache.key(bp, png, model) if cache else None
    hit = cache.get(k) if cache else None
    if hit is not None:
        return hit
    data = hedged_read(client, bp, png, hedge_after_s, model)
    if cache:
        cache.put(k, data)
    return data


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
    used: set[tuple] = set()          # (line, word) pairs taken by a matched text
    nwords = lambda i: max(1, len(lines[i].get("words") or [None]))
    texts = []
    # candidates: single OCR lines, joins of 2–3 vertically consecutive lines (wrapped headings/paragraphs: OCR
    # returns "Enter your info to sign" and "in" separately), and runs of words inside one line (the vision model
    # reads "Questions?" and "Contact us." as two texts where OCR has one line; "Get help" + an icon read as "Hl")
    cands = [([i], l["text"], l["box"], None) for i, l in enumerate(lines)]
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
                cands.append((list(group), " ".join(lines[k]["text"] for k in group), list(box), None))
        ws = a.get("words") or []
        for s0 in range(len(ws)):
            for s1 in range(s0 + 1, min(len(ws), s0 + 8) + 1):
                if s1 - s0 == len(ws):
                    continue
                part = ws[s0:s1]
                x0, y0 = min(w["box"][0] for w in part), min(w["box"][1] for w in part)
                x1 = max(w["box"][0] + w["box"][2] for w in part); y1 = max(w["box"][1] + w["box"][3] for w in part)
                cands.append(([i], " ".join(w["text"] for w in part), [x0, y0, x1 - x0, y1 - y0], (s0, s1)))

    for i, a in enumerate(lines):     # same-row runs: OCR split "Product Designer · San Francisco" at the dot
        group, box = [i], list(a["box"])
        while len(group) < 3:
            nxt = None
            for j, b in enumerate(lines):
                if j in group:
                    continue
                bb = b["box"]
                ov = min(box[1] + box[3], bb[1] + bb[3]) - max(box[1], bb[1])
                gap = bb[0] - (box[0] + box[2])
                if ov >= 0.5 * min(box[3], bb[3]) and 0 <= gap <= 3 * max(box[3], bb[3]) and (nxt is None or bb[0] < lines[nxt]["box"][0]):
                    nxt = j
            if nxt is None:
                break
            b = lines[nxt]["box"]
            group.append(nxt)
            y0, y1 = min(box[1], b[1]), max(box[1] + box[3], b[1] + b[3])
            box = [box[0], y0, b[0] + b[2] - box[0], y1 - y0]
            cands.append((list(group), " ".join(lines[k]["text"] for k in group), list(box), None))

    def words_of(c):
        if c[3] is not None:
            return {(c[0][0], k) for k in range(*c[3])}
        return {(i, k) for i in c[0] for k in range(nwords(i))}

    for t in vlm.get("texts", []):
        best, score = None, 0.0
        for c in cands:
            if words_of(c) & used:
                continue
            sc = _sim(t.get("text", ""), c[1])
            if sc > score or (sc == score and best is not None and c[3] is None and best[3] is not None):
                best, score = c, sc
        item = {"text": t.get("text", ""), "role": t.get("role", "other"),
                "size_px": t.get("size_px"), "weight": t.get("weight")}
        # ≥ 0.9 (or containment, which _sim scores ≥ 0.95): "Continue with Google" vs an OCR line "Continue with
        # Email" scored 0.8 and stole its box when OCR missed the white-on-dark Google label
        if best is not None and score >= 0.9:
            idxs, _, box, sub = best
            first = lines[idxs[0]]
            if sub is not None or len(idxs) > 1 or _norm(first["text"]) == _norm(t.get("text", "")) or score >= 0.95:
                used.update(words_of(best))
            ltexts = [best[1]] if sub is not None else [lines[k]["text"] for k in idxs]
            item.update(box=box, color=first["color"], on=first["backdrop"], measured=True, lines=len(idxs),
                        line_boxes=[box] if sub is not None else [lines[k]["box"] for k in idxs], line_texts=ltexts)
            ty = first.get("typo") or {}
            item["size_px"] = ty.get("size_px") or font_px(first["text"], first["box"][2], first["box"][3], t.get("size_px"))
            if ty:
                item.update(weight=ty["weight"], tracking_em=ty["tracking_em"], top_em=ty["top_em"],
                            underline=ty.get("underline", False))
        else:
            part = _partial(t.get("text", ""), [c for c in cands if not (words_of(c) & used)])
            if part:      # OCR read part of it ("SEE MY" of "SEE MY WORK", "ORK" of "WORK"): extend the box
                c, box = part
                first = lines[c[0][0]]
                used.update(words_of(c))
                item.update(box=box, color=first["color"], on=first["backdrop"], measured=True, extended=True, lines=1,
                            line_boxes=[box], line_texts=[t.get("text", "")])
                ty = first.get("typo") or {}
                item["size_px"] = ty.get("size_px") or font_px(c[1], c[2][2], c[2][3], t.get("size_px"))
                if ty:
                    item.update(weight=ty["weight"], tracking_em=ty["tracking_em"], top_em=ty["top_em"],
                                underline=ty.get("underline", False))
            else:
                item.update(box=None, color=t.get("color"), measured=False,
                            vlm_box=t.get("box") if isinstance(t.get("box"), list) and len(t["box"]) == 4 else None)
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
    # a block's label = the merged (vision-model) strings inside it, not raw OCR: "HM Continue with Google" (icon read
    # as "HM") keyed the mobile Google button apart from the same button on tablet/desktop
    blocks = [{k: v for k, v in b.items()} for b in meas["blocks"]]
    for b in blocks:
        if b.get("rule"):
            continue
        inside = [t["text"] for t in sorted(texts, key=lambda t: (t["box"][1], t["box"][0]) if t.get("box") else (0, 0))
                  if t.get("box") and not (t.get("approx") and not t.get("inside_block"))
                  and _inside_box(t["box"], b["box"])]   # reading order by position (the model's order varies)
        if inside or b.get("contains_text"):
            b["contains_text"] = inside
    unread = [l["box"] for i, l in enumerate(lines) if not any((i, k) in used for k in range(nwords(i)))]
    return fold_headings({
        "size": meas["size"],
        "background": meas["background"],
        "texts": texts,
        "blocks": blocks,
        "layout": vlm.get("layout", ""),
        "vlm_blocks": [{"kind": b.get("kind"), "fill": b.get("fill")} for b in vlm.get("blocks", [])][:20],
    }, loose=unread)


def _rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)] if isinstance(h, str) and len(h) == 7 else None


def _close(a, b, tol=150) -> bool:      # dark vs dark: the vision model guesses #000 or #333
    ca, cb = _rgb(a), _rgb(b)
    return ca is None or cb is None or sum(abs(p - q) for p, q in zip(ca, cb)) <= tol


def _clip_size(frame: dict, t: dict) -> int:
    """Font size of a headline the fold cut (its height is clipped): width per character, scaled by a measured
    headline of the same colour in the frame (calibrated typography); else Inter's mean caps width."""
    n = max(1, len(re.sub(r"\s", "", t["text"])))
    per = t["box"][2] / n
    sibs = [s for s in frame["texts"] if s is not t and s.get("measured") and not s.get("clipped") and s.get("box")
            and s.get("size_px") and len(s["text"].replace(" ", "")) >= 3 and s["size_px"] >= 32
            and _close(s.get("color"), t.get("color"))]
    if sibs:
        s = max(sibs, key=lambda s: s["size_px"])
        return int(round(s["size_px"] * per / (s["box"][2] / len(s["text"].replace(" ", "")))))
    return int(round(per / 0.552))


def fold_headings(frame: dict, loose: list | None = None) -> dict:
    """A giant headline cut by the frame's bottom edge: OCR cannot read it, its strokes are measured as ≥ 2 blocks of
    one dark colour along the bottom edge spanning ≥ 30 % of the width. When a text could not be placed (approx box),
    the strokes are that text: their union is its box, its size comes from width per character, the blocks go."""
    W, H = frame["size"]
    # a text the vision model itself placed in the upper part of the frame is not the one the bottom edge cut
    pending = [t for t in frame["texts"] if t.get("approx") and not t.get("inside_block")
               and not (t.get("vlm_box") and t["vlm_box"][1] < 0.4 * H)]
    if not pending:
        return frame
    groups: dict = {}
    for b in frame["blocks"]:
        x, y, w, h = b["box"]
        c = _rgb(b.get("fill"))
        if b.get("rule") or b.get("contains_text") or c is None or y + h < H - 3 or sum(c) > 3 * 110:
            continue
        key = next((k for k in groups if sum(abs(p - q) for p, q in zip(k, c)) <= 24), tuple(c))
        groups.setdefault(key, []).append(b)
    edge = [{"box": list(b)} for b in loose or [] if b[1] + b[3] >= H - 3 and b[3] >= 24]   # unread OCR junk at the edge
    for g in groups.values():
        if len(g) + len(edge) < 2:
            continue
        hmax = max(b["box"][3] for b in g)
        boxes = [b["box"] for b in g] + [e["box"] for e in edge if e["box"][3] >= 0.6 * hmax]
        x0 = min(b[0] for b in boxes); x1 = max(b[0] + b[2] for b in boxes)
        y0 = min(b[1] for b in boxes)
        if x1 - x0 < 0.3 * W:
            continue
        t = pending[-1]          # cut by the bottom edge: the last text still unplaced in reading order
        t.update(box=[x0, y0, x1 - x0, H - y0], measured=True, clipped=True, lines=1, line_boxes=[[x0, y0, x1 - x0, H - y0]],
                 line_texts=[t["text"]], color="#%02x%02x%02x" % tuple(_rgb(g[0]["fill"])))   # measured, not guessed
        t.pop("approx", None)
        t["size_px"] = _clip_size(frame, t)
        frame["blocks"] = [b for b in frame["blocks"] if b not in g]
        pending.remove(t)
        if not pending:
            break
    return frame


def cross_frame_spelling(breakpoints: dict) -> dict:
    """A text the frame could not read cleanly (clipped by the fold, or unmeasured) that is one or two characters
    away from a text measured in another frame takes that spelling — the frames show the same copy."""
    measured = [t["text"] for f in breakpoints.values() for t in f["texts"] if t.get("measured") and not t.get("clipped")]
    for f in breakpoints.values():
        for t in f["texts"]:
            if not (t.get("clipped") or not t.get("measured")):
                continue
            here = {s["text"] for s in f["texts"] if s is not t}
            best = max(((difflib.SequenceMatcher(None, t["text"].lower(), m.lower()).ratio(), m) for m in measured
                        if m != t["text"] and m not in here), default=(0, None))
            if best[1] and best[0] >= 0.75 and abs(len(best[1]) - len(t["text"])) <= 2:
                t["text"] = best[1]
                if t.get("clipped"):
                    t["size_px"] = _clip_size(f, t)
    return breakpoints


def _partial(text: str, cands: list):
    """The longest one-line OCR candidate whose text is part of `text` (≥ 3 characters and ≥ half of it) → (candidate,
    box extended by the missing characters at the OCR read's own character width), or None."""
    t = _norm(text)
    best = None
    for c in cands:
        if len(c[0]) != 1:
            continue
        o = _norm(c[1])
        if len(o) < 3 or len(o) * 2 < len(t) or o == t:
            continue
        k = t.find(o)
        if k < 0:
            continue
        if best is None or len(o) > len(_norm(best[1])):
            best = c
    if best is None:
        return None
    o = _norm(best[1])
    k = t.find(o)
    x, y, w, h = best[2]
    cw = w / len(o)
    return best, [round(x - k * cw), y, round(w + (len(t) - len(o)) * cw), h]


def _inside_box(inner, outer, slack=3) -> bool:
    return (inner[0] >= outer[0] - slack and inner[1] >= outer[1] - slack and
            inner[0] + inner[2] <= outer[0] + outer[2] + slack and inner[1] + inner[3] <= outer[1] + outer[3] + slack)


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


_DEFAULT = object()


def perceive(client: TFClient, frames: dict[str, bytes], cache=_DEFAULT, hedge_after_s=_DEFAULT) -> dict:
    """frames: {bp: png}. Returns {"breakpoints": {bp: merged frame spec}}. Frames read in parallel, each with a
    backup request when slow and from the vision cache when already read (config.VISION_CACHE_DIR / VISION_HEDGE_S)."""
    if cache is _DEFAULT:
        cache = VisionCache(config.VISION_CACHE_DIR) if config.VISION_CACHE_DIR else None
    if hedge_after_s is _DEFAULT:
        hedge_after_s = config.VISION_HEDGE_S

    def safe_read(kv):
        try:
            return cached_read(client, *kv, cache=cache, hedge_after_s=hedge_after_s)
        except ValueError:
            return None
    with ThreadPoolExecutor(len(frames)) as ex:
        vlm = dict(zip(frames, ex.map(safe_read, frames.items())))
        meas = dict(zip(frames, ex.map(lambda kv: measure(kv[1]), frames.items())))
    for bp in frames:   # a frame the vision model couldn't read still gets a spec (OCR-only, flagged)
        if vlm[bp] is None:
            vlm[bp] = ocr_fallback(meas[bp])
    return {"breakpoints": cross_frame_spelling({bp: merge(vlm[bp], meas[bp]) for bp in frames}), "raw_vlm": vlm}


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
