"""Measured scaffold: compile the spec into a first-draft App.jsx deterministically (no model).

One DOM tree for all breakpoints, laid out as flex-wrap lines inside containers:
- items = measured texts + measured blocks (blocks that contain texts become their containers);
- per breakpoint each item gets order, margin-top / margin-left (from the measured positions), width;
- a line break before an item is a text-free spacer element shown only at the breakpoints that need it;
- items not visible at a breakpoint are hidden there (if they'd be on-screen) or pushed below the fold.
Text metrics are calibrated for Inter in our renderer (tools: sandbox/calib.mjs): ink height = 0.785·fs
(no descenders) or 0.982·fs (with descenders); with leading-none the element top is 0.16·fs above the ink.

The scaffold is one of the initial candidates; the agent loop (Nemotron + deterministic fixes) improves
whichever draft scores best. Coordinates are absolute numbers, so this is a measured starting point, not a
fluid layout — the README says so.
"""
from __future__ import annotations

import re

BPS = ("mobile", "tablet", "desktop")
PREFIX = {"mobile": "", "tablet": "md:", "desktop": "xl:"}
SIZES = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}
INK_NO_DESC, INK_DESC, TOP_OFFSET = 0.785, 0.982, 0.16


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower().lstrip("| ")


def _font_px(text: str, ink_w: float, ink_h: float, hint) -> int:
    """Median of independent estimates (ink height, ink width per character, the vision model's hint): OCR boxes
    can include stray glyphs (an input caret read as '|' made a 53 px-tall box → 66 px text)."""
    t = text.strip()
    desc = bool(re.search(r"[gjpqy,;]", t))
    est = [ink_h / (INK_DESC if desc else INK_NO_DESC)]
    if len(t) >= 3:
        est.append(ink_w / (len(t) * (0.483 if desc else 0.552)))
    if hint:
        est.append(float(hint))
    est.sort()
    return max(8, int(round(est[len(est) // 2] if len(est) % 2 else (est[len(est) // 2 - 1] + est[len(est) // 2]) / 2)))


def _weight(w) -> int:
    try:
        w = int(float(w))
    except (TypeError, ValueError):
        return 400
    return min((400, 500, 600, 700), key=lambda x: abs(x - w))


def _inside(inner, outer, slack=3):
    return (inner[0] >= outer[0] - slack and inner[1] >= outer[1] - slack and
            inner[0] + inner[2] <= outer[0] + outer[2] + slack and inner[1] + inner[3] <= outer[1] + outer[3] + slack)


class Item:
    def __init__(self, key, kind):
        self.key, self.kind = key, kind
        self.at: dict[str, dict] = {}       # bp -> {"box", ...style}
        self.children: list[Item] = []
        self.text = ""
        self.role = "other"


def _collect(spec: dict) -> list[Item]:
    items: dict[str, Item] = {}
    for bp in BPS:
        frame = spec["breakpoints"].get(bp)
        if not frame:
            continue
        seen: dict[str, int] = {}
        for t in frame["texts"]:
            if not t.get("box") or t.get("approx") and not t.get("inside_block"):
                continue
            k = _norm(t["text"])
            if not k:
                continue
            seen[k] = seen.get(k, 0) + 1
            key = f"t:{k}#{seen[k]}"
            it = items.setdefault(key, Item(key, "text"))
            # roles vary per frame (the same placeholder was "input-placeholder" on mobile, "label" on desktop): keep the
            # most specific one seen
            role = t.get("role", "other")
            if ROLE_RANK.get(role, 0) > ROLE_RANK.get(it.role, 0):
                it.role = role
            it.text = t["text"]
            x, y, w, h = t["box"]
            fs = int(t.get("size_px") or _font_px(t["text"], w, h, None))   # calibrated in perceive.merge
            if t.get("approx") and t.get("inside_block"):
                # OCR missed it (e.g. white on dark): real width from Inter metrics, centred in its block
                from .typography import metrics
                ib = t["inside_block"]
                tw = max(8, round(metrics(t["text"], _weight(t.get("weight") or 500))[1] * fs))
                th = round(0.75 * fs)
                x, y, w, h = ib[0] + (ib[2] - tw) // 2, ib[1] + (ib[3] - th) // 2, tw, th
            it.at[bp] = {"ink": [x, y, w, h], "fs": fs, "lines": int(t.get("lines") or 1), "color": t.get("color") or "#000000",
                         "underline": bool(t.get("underline")),
                         "weight": _weight(t.get("weight")), "approx": bool(t.get("approx")),
                         "tracking": float(t.get("tracking_em") or 0.0), "top_em": t.get("top_em")}
        ranks: dict[str, int] = {}
        for b in sorted(frame["blocks"], key=lambda b: (b["box"][1], b["box"][0])):
            if b["box"][2] * b["box"][3] < 120 and not b.get("rule"):
                continue
            label = _norm((b.get("contains_text") or [""])[0])
            if label:
                key = f"b:{label}"
            else:   # text-free blocks: match across breakpoints by colour class, then reading order within it
                f = b.get("fill") or "#000000"
                import math
                size = f"{round(math.log2(max(b['box'][2], 1)))}x{round(math.log2(max(b['box'][3], 1)))}"
                cls = ("".join(f"{int(f[i:i + 2], 16) // 32:x}" for i in (1, 3, 5)) + ("o" if b.get("border") else "")
                       + ("r" if b.get("rule") else "") + "@" + size)   # colour + size class (icons ≠ placeholders)
                ranks[cls] = ranks.get(cls, 0) + 1
                key = f"b:{cls}#{ranks[cls]}"
            it = items.setdefault(key, Item(key, "block"))
            it.at[bp] = {"box": list(b["box"]), "fill": b.get("fill"), "border": b.get("border"), "radius": b.get("radius"),
                         "shadow": bool(b.get("shadow"))}
    return list(items.values())


def _elem_box(it: Item, bp: str):
    a = it.at[bp]
    if it.kind == "block":
        return a["box"]
    x, y, w, h = a["ink"]
    fs = a["fs"]
    # element top (leading-none) = ink top − the string's own glyph top offset (Inter metrics), when known
    off = (a["top_em"] - 0.111) if a.get("top_em") is not None else TOP_OFFSET
    if a.get("lines", 1) == 1:
        return [round(x - 1.5), round(y - off * fs), round(w * 1.06 + 6), fs]
    if a.get("lines", 1) > 1:   # wrapped text: keep its measured width so it wraps the same way
        return [round(x - 1.5), round(y - TOP_OFFSET * fs), round(w * 1.02 + 2), round(h + 2 * TOP_OFFSET * fs)]
    return [round(x - 1.5), round(y - TOP_OFFSET * fs), round(w * 1.06 + 6), fs]


def _centre_in(box, outer, slack=3):
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    return outer[0] - slack <= cx <= outer[0] + outer[2] + slack and outer[1] - slack <= cy <= outer[1] + outer[3] + slack


def _tree(items: list[Item]) -> list[Item]:
    """Nest each item in the smallest block that contains its centre — by majority over the breakpoints where both
    exist (a block missing at one breakpoint must not orphan its label; full-box containment was too strict)."""
    blocks = [b for b in items if b.kind == "block"]
    roots = []
    for it in items:
        votes: dict[int, int] = {}
        for bp in it.at:
            box = it.at[bp]["ink"] if it.kind == "text" else it.at[bp]["box"]
            area = box[2] * box[3]
            holders = [b for b in blocks if b is not it and bp in b.at and _centre_in(box, b.at[bp]["box"])
                       and b.at[bp]["box"][2] * b.at[bp]["box"][3] > area * 1.05]
            if holders:
                h = min(holders, key=lambda b: b.at[bp]["box"][2] * b.at[bp]["box"][3])
                votes[id(h)] = votes.get(id(h), 0) + 1
            else:
                votes[0] = votes.get(0, 0) + 1
        best = max(votes, key=votes.get) if votes else 0
        holder = next((b for b in blocks if id(b) == best), None)
        (holder.children if holder is not None else roots).append(it)
    # a block can't contain its own ancestor
    return roots


def _synthesize_blocks(roots: list[Item]):
    """A block missing at a breakpoint whose children ARE there (e.g. a white outlined button OCR/measurement missed)
    gets a box derived from a child: the child's offset inside the block and the block's size at a breakpoint where
    both exist. Without this the children were laid out against another breakpoint's coordinates (x off by 400 px)."""
    def walk(its):
        for it in its:
            if it.kind == "block" and it.children:
                ref = next((bp for bp in BPS if bp in it.at and any(bp in ch.at for ch in it.children)), None)
                for bp in BPS:
                    if bp in it.at or ref is None:
                        continue
                    ch = next((c for c in it.children if bp in c.at and ref in c.at), None)
                    if ch is None:
                        continue
                    rb, cb_ref, cb = it.at[ref]["box"], _elem_box(ch, ref), _elem_box(ch, bp)
                    dx, dy = cb_ref[0] - rb[0], cb_ref[1] - rb[1]
                    it.at[bp] = {"box": [cb[0] - dx, cb[1] - dy, rb[2], rb[3]], "fill": it.at[ref].get("fill"),
                                 "border": it.at[ref].get("border"), "synth": True}
            walk(it.children)
    walk(roots)


def _rows(children: list[Item], bp: str, origin):
    present = [c for c in children if bp in c.at]
    boxes = {id(c): _elem_box(c, bp) for c in present}
    rows: list[list[Item]] = []
    for c in sorted(present, key=lambda c: boxes[id(c)][1]):
        y, h = boxes[id(c)][1], boxes[id(c)][3]
        for row in rows:
            r0 = min(boxes[id(r)][1] for r in row)
            r1 = max(boxes[id(r)][1] + boxes[id(r)][3] for r in row)
            if min(r1, y + h) - max(r0, y) >= 0.5 * min(h, r1 - r0):
                row.append(c)
                break
        else:
            rows.append([c])
    for row in rows:
        row.sort(key=lambda c: boxes[id(c)][0])
    return rows, boxes


def _resp(values: dict[str, str]) -> str:
    """{bp: class} → 'cls md:cls2 xl:cls3' emitting only changes (mobile-first)."""
    out, prev = [], None
    for bp in BPS:
        v = values.get(bp)
        if v is None:
            continue
        if v != prev:
            out.append(PREFIX[bp] + v if v else "")
            prev = v
    return " ".join(x for x in out if x)


def _px(prop: str, v: float) -> str:
    v = int(round(v))
    return f"{prop}-[{v}px]" if v >= 0 else f"-{prop}-[{-v}px]"


def _layout(children: list[Item], origin: dict[str, tuple], view_h: dict[str, int]):
    """Per child: order, mt, ml, line-break flag, visibility per breakpoint, inside a container whose content
    origin per breakpoint is origin[bp] = (x, y)."""
    plan = {id(c): {"order": {}, "mt": {}, "ml": {}, "brk": {}, "show": {}} for c in children}
    canon = list(children)
    for bp in BPS:
        rows, boxes = _rows(children, bp, origin.get(bp, (0, 0)))
        ox, oy = origin.get(bp, (0, 0))
        k, prev_bottom = 0, 0
        for r_i, row in enumerate(rows):
            line_bottom = prev_bottom
            cur_x = 0
            for c_i, c in enumerate(row):
                x, y, w, h = boxes[id(c)]
                x, y = x - ox, y - oy
                p = plan[id(c)]
                k += 1
                p["order"][bp] = 2 * k
                p["brk"][bp] = c_i == 0 and r_i > 0
                p["mt"][bp] = max(0, y - prev_bottom)
                p["ml"][bp] = max(0, x - cur_x)
                p["show"][bp] = True
                cur_x = x + w
                line_bottom = max(line_bottom, y + h)
            prev_bottom = line_bottom
        # children absent at this breakpoint
        for c in canon:
            if bp in c.at:
                continue
            p = plan[id(c)]
            ys = [_elem_box(c, o)[1] for o in c.at]
            on_screen_elsewhere = min(ys) < view_h[bp] if ys else False
            k += 1
            p["order"][bp] = 2 * k
            p["brk"][bp] = True
            p["ml"][bp] = 0
            if on_screen_elsewhere:
                p["show"][bp] = False        # e.g. a desktop-only panel
                p["mt"][bp] = 0
            else:
                p["show"][bp] = True         # below the fold here: push it past the viewport
                p["mt"][bp] = max(24, view_h[bp] - prev_bottom + 24)
                prev_bottom = view_h[bp] + 24
    return plan


ROLE_RANK = {"button": 9, "input-placeholder": 8, "link": 7, "nav": 6, "heading": 5, "subheading": 4, "label": 3,
             "body": 2, "caption": 2, "other": 0}
TAGS = {"heading": "h1", "subheading": "p", "body": "p", "caption": "p", "label": "span", "link": "a", "nav": "a",
        "button": "span", "input-placeholder": "span", "other": "span"}


def _emit(children: list[Item], origin, view_h, indent: int) -> list[str]:
    plan = _layout(children, origin, view_h)
    pad = "  " * indent
    out = []
    for c in children:
        p = plan[id(c)]
        # spacer: forces a new flex line where this item starts a row
        brk = {bp: ("basis-full h-0" if p["brk"].get(bp) else "hidden") for bp in BPS}
        out.append(f'{pad}<div aria-hidden="true" className="{_resp({bp: "block" if p["brk"].get(bp) else "hidden" for bp in BPS})} '
                   f'basis-full h-0 {_resp({bp: f"order-[{p["order"].get(bp, 0) - 1}]" for bp in BPS})}" />')
        common = [_resp({bp: f"order-[{p['order'].get(bp, 0)}]" for bp in BPS}),
                  _resp({bp: _px("mt", p["mt"].get(bp, 0)) for bp in BPS}),
                  _resp({bp: _px("ml", p["ml"].get(bp, 0)) for bp in BPS}),
                  "shrink-0"]
        vis = {bp: ("" if p["show"].get(bp, True) else "hidden") for bp in BPS}
        if any(v == "hidden" for v in vis.values()):
            disp = "flex" if c.kind == "block" else "block"
            common.append(_resp({bp: (disp if p["show"].get(bp, True) else "hidden") for bp in BPS}))
        if c.kind == "text":
            a = {bp: c.at.get(bp) or c.at[next(iter(c.at))] for bp in BPS}
            cls = common + [
                _resp({bp: f"text-[{a[bp]['fs']}px]" for bp in BPS}),
                _resp({bp: f"text-[{a[bp]['color']}]" for bp in BPS}),
                _resp({bp: {400: "font-normal", 500: "font-medium", 600: "font-semibold", 700: "font-bold"}[a[bp]["weight"]] for bp in BPS}),
                _resp({bp: (f"tracking-[{a[bp]['tracking']}em]" if a[bp].get("tracking") else "tracking-normal") for bp in BPS}),
                _resp({bp: f"w-[{_elem_box(c, bp)[2] if bp in c.at else _elem_box(c, next(iter(c.at)))[2]}px]" for bp in BPS}),
                "leading-none" if all(c.at.get(bp, {}).get("lines", 1) == 1 for bp in c.at) else "leading-tight",
                _resp({bp: ("underline" if a[bp].get("underline") else "no-underline") for bp in BPS}),
                "whitespace-nowrap" if all(c.at.get(bp, {}).get("lines", 1) == 1 for bp in c.at) else "",
            ]
            if c.role == "input-placeholder":
                # a real, typeable input whose placeholder is the design's text (not a styled div)
                ph = [x.replace("text-[#", "placeholder:text-[#") if x and "text-[#" in x else x for x in cls]
                ph = [" ".join((("placeholder:" + t[3:]) if t.startswith("md:text-[#") or t.startswith("xl:text-[#") else t)
                               .replace("placeholder:text-[#", "placeholder:text-[#") for t in x.split()) if x else x for x in ph]
                ph = [" ".join(_placeholder_variant(t) for t in x.split()) if x else x for x in ph]
                label = _attr(c.text)
                out.append(f'{pad}<input type="text" aria-label="{label}" placeholder="{label}" '
                           f'className="{" ".join(x for x in ph if x)} bg-transparent border-0 outline-none p-0 h-[1em]" />')
                continue
            tag = TAGS.get(c.role, "span")
            extra = ' href="#"' if tag == "a" else ""
            if MENU and c.key in MENU.get("links", ()):
                # hidden on mobile until the hamburger opens it; tablet/desktop unchanged
                vis = next((x for x in cls if x and x.startswith("hidden ")), "")
                rest = " ".join(x for x in cls if x and x != vis)
                vis_rest = vis[len("hidden "):]
                out.append(f'{pad}<{tag}{extra} className={{`${{menuOpen ? "block" : "hidden"}} {vis_rest} {rest}`}}>'
                           f'{_jsx_text(c.text)}</{tag}>')
                continue
            out.append(f'{pad}<{tag}{extra} className="{" ".join(x for x in cls if x)}">{_jsx_text(c.text)}</{tag}>')
        else:
            boxes = {bp: c.at.get(bp, c.at[next(iter(c.at))])["box"] for bp in BPS}
            fills = {bp: c.at.get(bp, c.at[next(iter(c.at))]).get("fill") for bp in BPS}
            borders = {bp: c.at.get(bp, c.at[next(iter(c.at))]).get("border") for bp in BPS}
            cls = common + ["flex flex-wrap content-start items-start",
                            _resp({bp: f"w-[{boxes[bp][2]}px]" for bp in BPS}),
                            _resp({bp: f"h-[{boxes[bp][3]}px]" for bp in BPS}),
                            _resp({bp: f"bg-[{fills[bp]}]" if fills[bp] else "bg-transparent" for bp in BPS}),
                            _resp({bp: f"border border-[{borders[bp]}]" if borders[bp] else "border-0" for bp in BPS}),
                            _resp({bp: (f"rounded-[{c.at.get(bp, c.at[next(iter(c.at))]).get('radius')}px]"
                                        if c.at.get(bp, c.at[next(iter(c.at))]).get("radius") else "rounded-none") for bp in BPS}),
                            _resp({bp: ("shadow-sm" if c.at.get(bp, c.at[next(iter(c.at))]).get("shadow") else "shadow-none") for bp in BPS})]
            tag = "button" if any(ch.role == "button" for ch in c.children) else "div"
            if tag == "button":
                cls.append("cursor-pointer text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2")
            inner_origin = {bp: tuple(boxes[bp][:2]) for bp in BPS}
            if MENU and c.key == MENU.get("trigger"):
                tag = "button"
                cls.append("cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2")
            btype = ' type="button"' if tag == "button" else ""
            if MENU and c.key == MENU.get("trigger"):
                btype += ' aria-label="Open menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((o) => !o)}'

            out.append(f'{pad}<{tag}{btype} className="{" ".join(x for x in cls if x)}">')
            # blocks get the same recursive X-Y cut as the page (a bordered row holding three cards)
            if len(c.children) >= 4:
                out += _emit_split(c.children, inner_origin, {bp: boxes[bp][2] for bp in BPS}, view_h, indent + 1, depth=1)
            else:
                out += _emit(c.children, inner_origin, view_h, indent + 1)
            out.append(f"{pad}</{tag}>")
    return out


def _placeholder_variant(t: str) -> str:
    """text colour → placeholder colour, keeping the breakpoint prefix (md:text-[#x] → md:placeholder:text-[#x])."""
    for pre in ("md:", "xl:", ""):
        if t.startswith(pre + "text-[#") or t.startswith(pre + "placeholder:text-[#"):
            return pre + "placeholder:" + t[len(pre):].replace("placeholder:", "")
    return t


def _attr(t: str) -> str:
    return t.replace("&", "&amp;").replace('"', "&quot;").replace("{", "").replace("}", "")


def _jsx_text(t: str) -> str:
    return t.replace("{", "&#123;").replace("}", "&#125;").replace("<", "&lt;").replace(">", "&gt;")


def _split(children: list[Item], bp: str):
    """A vertical gutter no element crosses, with ≥ 2 items on each side whose vertical spans overlap
    (side-by-side stacks: form + panel, sidebar + content). Returns (left_right_edge, right_left_edge, left, right)."""
    present = [c for c in children if bp in c.at]
    if len(present) < 4:
        return None
    boxes = {id(c): _elem_box(c, bp) for c in present}
    best = None
    for c in present:
        s0 = boxes[id(c)][0] + boxes[id(c)][2]
        left = [d for d in present if boxes[id(d)][0] + boxes[id(d)][2] <= s0]
        right = [d for d in present if d not in left]
        if len(left) < 2 or len(right) < 2:
            continue
        s1 = min(boxes[id(d)][0] for d in right)
        if s1 - s0 < 16:
            continue
        ly0, ly1 = min(boxes[id(d)][1] for d in left), max(boxes[id(d)][1] + boxes[id(d)][3] for d in left)
        ry0, ry1 = min(boxes[id(d)][1] for d in right), max(boxes[id(d)][1] + boxes[id(d)][3] for d in right)
        overlap = min(ly1, ry1) - max(ly0, ry0)
        if overlap < 0.5 * min(ly1 - ly0, ry1 - ry0):
            continue
        # only split when flat flex-wrap lines would FAIL: an item on one side spans ≥ 2 vertically stacked items on
        # the other (a form beside a tall panel). Side-by-side rows of small items (3 feature columns) lay out fine flat,
        # and splitting them broke a correct 3-column row in a live comparison.
        def spans_two(a_side, b_side):
            for a in a_side:
                ay0, ay1 = boxes[id(a)][1], boxes[id(a)][1] + boxes[id(a)][3]
                hit = sorted((boxes[id(b)][1], boxes[id(b)][1] + boxes[id(b)][3]) for b in b_side
                             if min(ay1, boxes[id(b)][1] + boxes[id(b)][3]) - max(ay0, boxes[id(b)][1]) > 0)
                if any(hit[k + 1][0] >= hit[k][1] - 2 for k in range(len(hit) - 1)):
                    return True
            return False
        if not (spans_two(left, right) or spans_two(right, left)):
            continue
        if best is None or s1 - s0 > best[1] - best[0]:
            best = (s0, s1, left, right)
    return best


def _bands(children: list[Item], bp: str) -> list[list[Item]] | None:
    """X-Y cut, horizontal step: split into bands wherever a vertical gap runs across all items at bp."""
    present = sorted([c for c in children if bp in c.at], key=lambda c: _elem_box(c, bp)[1])
    if len(present) < 3:
        return None
    bands, cur, bottom = [], [], None
    for c in present:
        y0, h = _elem_box(c, bp)[1], _elem_box(c, bp)[3]
        if cur and y0 > bottom:
            bands.append(cur)
            cur = []
        cur.append(c)
        bottom = y0 + h if bottom is None or not cur[:-1] else max(bottom, y0 + h)
    bands.append(cur)
    return bands if len(bands) >= 2 else None


def _bands_consistent(bands: list[list[Item]], tol: int = 4) -> bool:
    for bp in BPS:
        spans = []
        for band in bands:
            present = [c for c in band if bp in c.at]
            if present:
                spans.append((min(_elem_box(c, bp)[1] for c in present),
                              max(_elem_box(c, bp)[1] + _elem_box(c, bp)[3] for c in present)))
        if any(spans[k][1] > spans[k + 1][0] + tol for k in range(len(spans) - 1)):
            return False
    return True


SEGMENTS: list[dict] = []   # filled during compile: [{"id", "kind", "texts", "boxes"}] for the semantic pass
_SEG_STACK: list[str] = []


def _seg(kind: str, members: list[Item], depth: int = 0) -> str:
    sid = f"S{len(SEGMENTS) + 1}"
    texts = []
    def walk(its):
        for it in its:
            if it.kind == "text":
                texts.append(it.text[:40])
            walk(it.children)
    walk(members)
    boxes = {}
    for bp in BPS:
        bs = [_elem_box(c, bp) for c in members if bp in c.at]
        if bs:
            x0, y0 = min(b[0] for b in bs), min(b[1] for b in bs)
            boxes[bp] = [x0, y0, max(b[0] + b[2] for b in bs) - x0, max(b[1] + b[3] for b in bs) - y0]
    SEGMENTS.append({"id": sid, "kind": kind, "depth": depth, "texts": texts[:8], "n_texts": len(texts), "boxes": boxes,
                     "members": {id(m) for m in members}})
    return sid


def _link_segments():
    """Parent = the smallest other segment whose members include all of this segment's members."""
    for sg in SEGMENTS:
        cands = [o for o in SEGMENTS if o is not sg and sg["members"] <= o["members"] and len(o["members"]) > len(sg["members"])]
        sg["parent"] = min(cands, key=lambda o: len(o["members"]))["id"] if cands else None


def _emit_bands(bands: list[list[Item]], children: list[Item], ref: str, origin: dict, width: dict, view_h,
                indent: int, depth: int) -> list[str]:
    """Each band is a full-width wrapper stacked in flow; its contents are laid out relative to its own top."""
    # items absent at the reference breakpoint join the band of the item just before them in reading order
    member = {id(c): k for k, band in enumerate(bands) for c in band}
    order = sorted(children, key=lambda c: min(_elem_box(c, bp)[1] / SIZES[bp][1] for bp in c.at))
    last = 0
    for c in order:
        if id(c) in member:
            last = member[id(c)]
        else:
            member[id(c)] = last
    groups = [[c for c in children if member[id(c)] == k] for k in range(len(bands))]
    pad = "  " * indent
    out = [f'{pad}<div className="flex flex-col items-start {_resp({bp: f"w-[{width[bp]}px]" for bp in BPS})} shrink-0">']
    prev_bottom = {bp: origin[bp][1] for bp in BPS}
    for g in groups:
        g_origin = {bp: (origin[bp][0], prev_bottom[bp]) for bp in BPS}
        inner = _emit_split(g, g_origin, width, view_h, indent + 1, depth + 1, allow_bands=False)
        inner[0] = inner[0].replace("<div ", f'<div data-seg="{_seg("band", g, depth)}" ', 1)
        out += inner
        for bp in BPS:
            present = [c for c in g if bp in c.at]
            if present:
                prev_bottom[bp] = max(prev_bottom[bp], max(_elem_box(c, bp)[1] + _elem_box(c, bp)[3] for c in present))
    return out + [f"{pad}</div>"]


def _emit_split(children: list[Item], origin: dict, width: dict, view_h, indent: int, depth: int = 0,
                allow_bands: bool = True) -> list[str]:
    """Recursive X-Y cut: horizontal bands (header / hero / cards), then side-by-side columns inside a band (three
    cards; a form beside a panel). At breakpoints without a column split the columns stack."""
    pad = "  " * indent
    if allow_bands and depth < 4:
        ref_b = max(BPS, key=lambda bp: sum(1 for c in children if bp in c.at))
        bands = _bands(children, ref_b)
        if bands and not _bands_consistent(bands):
            bands = None   # bands must keep their vertical order at EVERY breakpoint (a desktop side panel stacks last on mobile)
        if bands:
            return _emit_bands(bands, children, ref_b, origin, width, view_h, indent, depth)
    splits = {bp: (_split(children, bp) if depth < 6 else None) for bp in BPS}
    ref = next((bp for bp in ("desktop", "tablet", "mobile") if splits[bp]), None)
    if ref is None:
        return ([f'{pad}<div className="flex flex-wrap content-start items-start {_resp({bp: f"w-[{width[bp]}px]" for bp in BPS})}">'] +
                _emit(children, origin, view_h, indent + 1) + [f"{pad}</div>"])
    s0, s1, left, right = splits[ref]
    W = {bp: SIZES[bp][0] for bp in BPS}
    for c in children:   # items absent at the reference breakpoint: side by relative x elsewhere
        if c not in left and c not in right:
            bp = next(iter(c.at))
            (right if (_elem_box(c, bp)[0] - origin[bp][0]) / max(width[bp], 1) >= (s1 - origin[ref][0]) / max(width[ref], 1) else left).append(c)
    left = [c for c in children if c in left]
    right = [c for c in children if c in right]
    side = {bp: bool(splits[bp]) and {id(c) for c in splits[bp][2]} <= {id(c) for c in left} for bp in BPS}
    l_origin, r_origin, lw, rw, r_ml = {}, {}, {}, {}, {}
    for bp in BPS:
        ox, oy = origin[bp]
        l_origin[bp] = (ox, oy)
        if side[bp]:
            a, b = splits[bp][0], splits[bp][1]
            lw[bp], rw[bp], r_ml[bp], r_origin[bp] = a - ox, ox + width[bp] - b, b - a, (b, oy)
        else:
            bottom = max((_elem_box(c, bp)[1] + _elem_box(c, bp)[3] for c in left if bp in c.at), default=oy)
            lw[bp], rw[bp], r_ml[bp], r_origin[bp] = width[bp], width[bp], 0, (ox, bottom)
    out = [f'{pad}<div className="flex {_resp({bp: "flex-row" if side[bp] else "flex-col" for bp in BPS})} items-start '
           f'{_resp({bp: f"w-[{width[bp]}px]" for bp in BPS})} shrink-0">']
    left_out = _emit_split(left, l_origin, lw, view_h, indent + 1, depth + 1)
    left_out[0] = left_out[0].replace("<div ", f'<div data-seg="{_seg("column", left, depth)}" ', 1)
    out += left_out
    inner = _emit_split(right, r_origin, rw, view_h, indent + 1, depth + 1)   # columns may band again
    inner[0] = inner[0].replace("<div ", f'<div data-seg="{_seg("column", right, depth)}" ', 1)
    # right column's offset from the left one (only where they sit side by side)
    inner[0] = inner[0].replace('className="', f'className="{_resp({bp: _px("ml", r_ml[bp]) for bp in BPS})} ', 1)
    out += inner + [f"{pad}</div>"]
    return out


def _emit_root(roots: list[Item], view_h) -> list[str]:
    W = {bp: SIZES[bp][0] for bp in BPS}
    return _emit_split(roots, {bp: (0, 0) for bp in BPS}, W, view_h, 3)


MENU: dict = {}   # {"trigger": item key, "links": {item keys}} when a mobile hamburger is detected


def _detect_menu(items: list[Item]) -> dict:
    """Links in the top area visible on tablet/desktop but hidden on mobile + a small icon near the top on mobile only
    (the ☰) → a working hamburger: the icon toggles those links on mobile."""
    links = [i for i in items if i.kind == "text" and i.role in ("link", "nav") and "mobile" not in i.at
             and ("tablet" in i.at or "desktop" in i.at) and min(_elem_box(i, b)[1] for b in i.at) < 120]
    icons = [i for i in items if i.kind == "block" and "mobile" in i.at and "desktop" not in i.at
             and i.at["mobile"]["box"][1] < 100 and max(i.at["mobile"]["box"][2:]) <= 48]
    if len(links) >= 2 and icons:
        trig = max(icons, key=lambda i: i.at["mobile"]["box"][0])   # rightmost: hamburgers sit top-right
        return {"trigger": trig.key, "links": {l.key for l in links}}
    return {}


def compile_scaffold(spec: dict) -> str:
    SEGMENTS.clear()
    items = _collect(spec)
    MENU.clear()
    MENU.update(_detect_menu(items))
    roots = _tree(items)
    _synthesize_blocks(roots)
    view_h = {bp: SIZES[bp][1] for bp in BPS}
    bgs = {bp: spec["breakpoints"].get(bp, {}).get("background", "#ffffff") for bp in BPS}
    body = _emit_root(roots, view_h)
    _link_segments()
    root_cls = f"flow-root min-h-screen font-sans {_resp({bp: f'bg-[{bgs[bp]}]' for bp in BPS})}"
    head = ('import { useState } from "react";\n\nexport default function App() {\n'
            '  const [menuOpen, setMenuOpen] = useState(false);\n  return (\n') if MENU else "export default function App() {\n  return (\n"
    return (head + f'    <div className="{root_cls}">\n'
            + "\n".join(body) +
            "\n    </div>\n  );\n}\n")
