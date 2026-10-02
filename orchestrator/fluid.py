"""Scaffold v2 — fluid compiler: measured spec → responsive React + Tailwind that flows between breakpoints.

Why v2 (council review, Oct 1): v1 reproduced the three frames but was pinned — fixed widths, a root pinned to
390/768/1280, per-breakpoint order + margin offsets, content hidden or pushed with magic margins below the fold.
v2 keeps v1's measurement and analysis (items, containment, X-Y cut) and changes how layout is expressed:
  - bands are full-width sections; their content sits in a container that is centred (mx-auto + max-w + gutter)
    or left-anchored with padding, per breakpoint, from the measured gutters;
  - rows are wrappers stacked with margins; inside a row items sit in a wrapping flex row (justify-between /
    center / end / start from the measured edges) or a column where the design stacks them;
  - side-by-side columns are CSS grid with fractional tracks per breakpoint (one track where the design stacks);
  - the fold: nothing is hidden or pushed because it is below a frame's fold — the content above a footer that is
    below the fold in some frame gets a per-breakpoint min-height so the footer starts where that frame ends;
    an item is hidden at a breakpoint only when the design omits it mid-page there;
  - text has no fixed width (wrapping text keeps its measured line length as a max-width); blocks spanning
    their container are w-full; content blocks use min-height.
Decisions a frame can't show (centred container vs full-bleed, ...) can be overridden by Nemotron's
responsive-intent plan (`intents`, see orchestrator/intent.py).
"""
from __future__ import annotations

from .scaffold import (BPS, MENU, SEGMENTS, SIZES, TAGS, Item, _attr, _bands, _bands_consistent, _collect,
                       _detect_menu, _elem_box, _jsx_text, _link_segments, _placeholder_variant, _px, _resp, _seg,
                       _split, _tree)

W = {bp: SIZES[bp][0] for bp in BPS}
VH = {bp: SIZES[bp][1] for bp in BPS}
WEIGHT = {400: "font-normal", 500: "font-medium", 600: "font-semibold", 700: "font-bold"}
STACK = {"disp": "flex", "dir": "flex-col", "wrap": "flex-nowrap", "justify": "justify-start", "pl": "pl-0", "pr": "pr-0"}
STATE: dict = {}   # per compile: {"all": [items], "intents": {...}}


def _box(c: Item, bp: str):
    """Layout box: blocks = measured box; text = its ink width (natural width of the rendered string) on the
    element's line box (top/height from v1's calibrated element box)."""
    if c.kind == "block":
        return c.at[bp]["box"]
    e = _elem_box(c, bp)
    ink = c.at[bp]["ink"]
    if c.at[bp].get("lines", 1) > 1:
        return [e[0], e[1], e[2], e[3]]
    return [round(ink[0] - 1), e[1], round(ink[2] + 2), e[3]]


def _union(items, bp):
    bs = [_box(c, bp) for c in items if bp in c.at]
    if not bs:
        return None
    x0, y0 = min(b[0] for b in bs), min(b[1] for b in bs)
    return [x0, y0, max(b[0] + b[2] for b in bs) - x0, max(b[1] + b[3] for b in bs) - y0]


def _is_menu_link(c):
    return bool(MENU) and c.key in MENU.get("links", ())


def _shown(c: Item, bp: str) -> bool:
    """Absent from a frame = below that frame's fold (render it, after everything visible) unless an element
    that comes after it elsewhere IS visible in this frame (then the design omits it here: hide it)."""
    if bp in c.at:
        return True
    ref = next(iter(c.at))
    y = _box(c, ref)[1]
    return not any(bp in d.at and ref in d.at and _box(d, ref)[1] > y + 4 for d in STATE["all"])


# ---------------------------------------------------------------------------------------------------------------
# rows

def _row_groups(items) -> list[list[Item]]:
    """Rows by vertical overlap at the breakpoint where most items are present; items absent there join the row of
    the item nearest above them where they are present."""
    ref = max(BPS, key=lambda bp: sum(1 for c in items if bp in c.at))
    rows: list[list[Item]] = []
    for c in sorted([c for c in items if ref in c.at], key=lambda c: _box(c, ref)[1]):
        y, h = _box(c, ref)[1], _box(c, ref)[3]
        for row in rows:
            r0 = min(_box(r, ref)[1] for r in row)
            r1 = max(_box(r, ref)[1] + _box(r, ref)[3] for r in row)
            if min(r1, y + h) - max(r0, y) >= 0.5 * min(h, r1 - r0):
                row.append(c)
                break
        else:
            rows.append([c])
    for c in items:
        if ref in c.at:
            continue
        bp = next(iter(c.at))
        y = _box(c, bp)[1]
        above = [(k, r) for k, row in enumerate(rows) for r in row if bp in r.at and _box(r, bp)[1] <= y + 2]
        if above:
            k = max(above, key=lambda kr: _box(kr[1], bp)[1])[0]
            same = [r for r in rows[k] if bp in r.at]
            r0 = min(_box(r, bp)[1] for r in same)
            r1 = max(_box(r, bp)[1] + _box(r, bp)[3] for r in same)
            if min(r1, y + _box(c, bp)[3]) - max(r0, y) > 0:
                rows[k].append(c)                        # on the same line there
            else:
                rows.insert(k + 1, [c])
        else:
            rows.insert(0, [c])
    return rows


def _row_mode(p: list[Item], bp: str, frame) -> tuple[dict, dict]:
    """Row container classes at bp + per-item (mt, ml, self) for the present items p (sorted by x)."""
    fx, fy, fw, _ = frame
    boxes = [_box(c, bp) for c in p]
    top = min(b[1] for b in boxes)
    same_line = all(min(boxes[k][1] + boxes[k][3], boxes[k + 1][1] + boxes[k + 1][3]) - max(boxes[k][1], boxes[k + 1][1]) > 0
                    and boxes[k + 1][0] >= boxes[k][0] + boxes[k][2] - 4 for k in range(len(p) - 1))
    per = {}
    if not same_line:
        # stacked: a column in reading order; each item's own horizontal placement
        prev = top
        for k in sorted(range(len(p)), key=lambda k: boxes[k][1]):
            x, y, w, h = boxes[k]
            centred = abs((x - fx) - (fx + fw - x - w)) <= max(8, 0.02 * fw) and w < 0.9 * fw
            # never a negative offset: overlapping boxes can't be stacked honestly (that would be pixel tracing)
            per[id(p[k])] = (max(0, y - prev), None if centred else max(0, x - fx), "self-center" if centred else "self-start")
            prev = max(prev, y + h)
        return {"disp": "flex", "dir": "flex-col", "wrap": "flex-nowrap", "justify": "justify-start", "pl": "pl-0", "pr": "pr-0"}, per
    l = boxes[0][0] - fx
    r = fx + fw - (boxes[-1][0] + boxes[-1][2])
    gaps = [boxes[k + 1][0] - (boxes[k][0] + boxes[k][2]) for k in range(len(p) - 1)]
    for k, c in enumerate(p):
        per[id(c)] = [boxes[k][1] - top, max(0, gaps[k - 1]) if k else 0, ""]
    mode = {"disp": "flex", "dir": "flex-row", "wrap": "flex-wrap", "justify": "justify-start", "pl": "pl-0", "pr": "pr-0"}
    if len(p) == 1 and abs(l - r) <= max(8, 0.02 * fw) and boxes[0][2] < 0.95 * fw:
        mode["justify"] = "justify-center"
    elif len(p) >= 2 and l <= 32 and r <= 32 and max(gaps) > 40:
        g = sorted(gaps, reverse=True)
        mode.update(pl=_px("pl", max(0, l)), pr=_px("pr", max(0, r)))
        if len(g) >= 2 and g[0] < 2 * g[1] and max(gaps) - min(gaps) <= 0.25 * max(gaps):
            mode["justify"] = "justify-between"          # evenly spread (footer columns)
            for c in p:
                per[id(c)][1] = 0
        else:                                            # two groups (logo + links | actions): push the right group
            k = gaps.index(g[0]) + 1
            per[id(p[k])][1] = "auto"
    elif len(p) >= 2 and abs(l - r) <= max(8, 0.02 * fw):
        mode["justify"] = "justify-center"
    elif r < l and r <= 32:
        mode.update(justify="justify-end", pr=_px("pr", max(0, r)))
    else:
        per[id(p[0])][1] = max(0, l)
    return mode, {k: tuple(v) for k, v in per.items()}


# ---------------------------------------------------------------------------------------------------------------
# elements

def _disp(vis: dict, shown_as: str) -> str:
    return "" if all(vis.values()) else _resp({bp: (shown_as if vis[bp] else "hidden") for bp in BPS})


def _j(xs) -> str:
    return " ".join(x for x in xs if x)


def _rc(per_bp: dict) -> str:
    """{bp: {property: class}} → responsive classes, one _resp per property (a multi-token value would only get the
    breakpoint prefix on its first token)."""
    keys = []
    for d in per_bp.values():
        keys += [k for k in d if k not in keys]
    return _j(_resp({bp: per_bp[bp].get(k, "") for bp in BPS}) for k in keys)


def _text(c: Item, indent: int, vis: dict, pos: str) -> list[str]:
    pad = "  " * indent
    a = {bp: c.at.get(bp) or c.at[next(iter(c.at))] for bp in BPS}
    multi = {bp: a[bp].get("lines", 1) > 1 for bp in BPS}
    cls = [_resp({bp: f"text-[{a[bp]['fs']}px]" for bp in BPS}),
           _resp({bp: f"text-[{a[bp]['color']}]" for bp in BPS}),
           _resp({bp: WEIGHT.get(a[bp]["weight"], "font-normal") for bp in BPS}),
           _resp({bp: (f"tracking-[{a[bp]['tracking']}em]" if a[bp].get("tracking") else "tracking-normal") for bp in BPS}),
           _resp({bp: ((f"leading-[{a[bp]['leading']}]" if a[bp].get("leading") else "leading-tight") if multi[bp] else "leading-none") for bp in BPS}),
           _resp({bp: {"center": "text-center", "right": "text-right"}.get(a[bp].get("align"), "text-left") for bp in BPS}),
           _resp({bp: ("underline" if a[bp].get("underline") else "no-underline") for bp in BPS}),
           # wrapping text keeps its measured line length as a MAXIMUM (it still narrows on smaller screens)
           _resp({bp: (f"max-w-[{_elem_box(c, bp if bp in c.at else next(iter(c.at)))[2]}px]" if multi[bp] else "max-w-full") for bp in BPS}),
           "min-w-0", pos]
    if all(not multi[bp] for bp in BPS) and len(c.text) <= 32:
        cls.append("whitespace-nowrap")
    if c.role == "input-placeholder":
        ph = " ".join(_placeholder_variant(t) for x in cls if x for t in x.split())
        label = _attr(c.text)
        return [f'{pad}<input type="text" aria-label="{label}" placeholder="{label}" '
                f'className="{_j([_disp(vis, "block"), ph, "w-full bg-transparent border-0 outline-none p-0 h-[1.2em]"])}" />']
    tag = TAGS.get(c.role, "span")
    if tag == "span" and any(multi.values()):
        tag = "p"
    href = ' href="#"' if tag == "a" else ""
    body = _j(cls)
    if _is_menu_link(c):
        return [f'{pad}<{tag}{href} className={{`${{menuOpen ? "block" : "hidden"}} md:block {body}`}}>{_jsx_text(c.text)}</{tag}>']
    return [f'{pad}<{tag}{href} className="{_j([_disp(vis, "block"), body])}">{_jsx_text(c.text)}</{tag}>']


def _block(c: Item, indent: int, cont_w: dict, vis: dict, pos: str) -> list[str]:
    pad = "  " * indent
    at = {bp: c.at.get(bp) or c.at[next(iter(c.at))] for bp in BPS}
    box = {bp: at[bp]["box"] for bp in BPS}
    full = {bp: box[bp][2] >= 0.92 * cont_w[bp] for bp in BPS}
    width = _resp({bp: ("w-full" if full[bp] else f"w-[{box[bp][2]}px] max-w-full") for bp in BPS})
    style = [_resp({bp: f"bg-[{at[bp]['fill']}]" if at[bp].get("fill") else "bg-transparent" for bp in BPS}),
             _resp({bp: f"border border-[{at[bp]['border']}]" if at[bp].get("border") else "border-0" for bp in BPS}),
             _resp({bp: f"rounded-[{at[bp]['radius']}px]" if at[bp].get("radius") else "rounded-none" for bp in BPS}),
             _resp({bp: "shadow-sm" if at[bp].get("shadow") else "shadow-none" for bp in BPS})]
    texts = [ch for ch in c.children if ch.kind == "text"]
    if MENU and c.key == MENU.get("trigger"):
        return [f'{pad}<button type="button" aria-label="Open menu" aria-expanded={{menuOpen}} onClick={{() => setMenuOpen((o) => !o)}} '
                f'className="{_j([_disp(vis, "block"), width, _resp({bp: f"h-[{box[bp][3]}px]" for bp in BPS}), *style, "shrink-0 cursor-pointer", pos])}" />']
    if not c.children:   # rule / icon / image placeholder
        h = _resp({bp: f"h-[{max(1, box[bp][3])}px]" for bp in BPS})
        return [f'{pad}<div aria-hidden="true" className="{_j([_disp(vis, "block"), width, h, *style, "shrink-0", pos])}" />']
    if texts and len(c.children) <= 3 and not any(ch.kind == "block" and ch.children for ch in c.children):
        # control (button / input / badge): measured height, label centred or inset like the design
        first = texts[0]
        fb = {bp: (_box(first, bp) if bp in first.at else None) for bp in BPS}
        centred = {bp: fb[bp] is not None and abs((fb[bp][0] + fb[bp][2] / 2) - (box[bp][0] + box[bp][2] / 2)) <= 8 for bp in BPS}
        inset = _rc({bp: ({"j": "justify-center", "px": "px-[12px]"} if centred[bp] or fb[bp] is None else
                          {"j": "justify-start", "px": _px("px", max(0, fb[bp][0] - box[bp][0]))}) for bp in BPS})
        is_btn = first.role == "button"
        tag = "button" if is_btn else ("label" if first.role == "input-placeholder" else "div")
        attrs = ' type="button"' if is_btn else ""
        disp = _disp(vis, "flex") or "flex"
        out = [f'{pad}<{tag}{attrs} className="{_j([disp, width, _resp({bp: f"h-[{box[bp][3]}px]" for bp in BPS}), *style, "items-center gap-[8px] shrink-0", inset, "cursor-pointer text-left" if is_btn else "", pos])}">']
        for ch in sorted(c.children, key=lambda ch: _box(ch, next(iter(ch.at)))[0]):
            ch_vis = {bp: _shown(ch, bp) for bp in BPS}
            out += (_text(ch, indent + 1, ch_vis, "") if ch.kind == "text" else
                    _block(ch, indent + 1, {bp: box[bp][2] for bp in BPS}, ch_vis, ""))
        return out + [f"{pad}</{tag}>"]
    # container (card / panel): min-height; children laid out inside its own box
    out = [f'{pad}<div className="{_j([_disp(vis, "block"), width, _resp({bp: f"min-h-[{box[bp][3]}px]" for bp in BPS}), *style, "shrink-0 flow-root", pos])}">']
    out += _layout(c.children, {bp: list(box[bp]) for bp in BPS}, indent + 1)
    return out + [f"{pad}</div>"]


# ---------------------------------------------------------------------------------------------------------------
# layout of items inside a frame (frame[bp] = [x, y, w, h] of the content area, design coordinates)

def _layout(items: list[Item], frame: dict, indent: int, depth: int = 0) -> list[str]:
    pad = "  " * indent
    if not items:
        return []
    splits = {bp: (_split(items, bp) if depth < 4 else None) for bp in BPS}
    ref = next((bp for bp in ("desktop", "tablet", "mobile") if splits[bp]), None)
    if ref is not None:
        return _columns(items, frame, splits, ref, indent, depth)
    out = []
    prev_bottom = {bp: frame[bp][1] for bp in BPS}
    for row in _row_groups(items):
        row.sort(key=lambda c: _box(c, next((bp for bp in ("desktop", "tablet", "mobile") if bp in c.at)))[0])
        rcls, mt, per = {}, {}, {}
        for bp in BPS:
            p = sorted([c for c in row if bp in c.at], key=lambda c: _box(c, bp)[0])
            if p:
                rcls[bp], per[bp] = _row_mode(p, bp, frame[bp])
                top = min(_box(c, bp)[1] for c in p)
                mt[bp] = max(0, top - prev_bottom[bp])
                prev_bottom[bp] = max(prev_bottom[bp], max(_box(c, bp)[1] + _box(c, bp)[3] for c in p))
            elif any(_shown(c, bp) or (_is_menu_link(c) and bp == "mobile") for c in row):
                rcls[bp], per[bp], mt[bp] = dict(STACK), {}, 0     # below the fold / menu: plain stack
            else:
                rcls[bp], per[bp], mt[bp] = dict(STACK, disp="hidden"), {}, 0
        out.append(f'{pad}<div className="{_rc(rcls)} items-start {_resp({bp: _px("mt", mt[bp]) for bp in BPS})} w-full">')
        # DOM order = x order at the widest frame; where a stacked frame reads in another order, use order-
        need_order = {}
        for bp in BPS:
            p = [c for c in row if bp in c.at]
            ys = sorted(p, key=lambda c: (_box(c, bp)[1], _box(c, bp)[0]))
            if rcls[bp]["dir"] == "flex-col" and rcls[bp]["disp"] != "hidden" and [id(c) for c in ys] != [id(c) for c in p]:
                need_order[bp] = {id(c): k for k, c in enumerate(ys)}
        for c in row:
            v = {bp: per[bp].get(id(c)) for bp in BPS}
            pos = [_resp({bp: _px("mt", v[bp][0]) if v[bp] else "mt-0" for bp in BPS}),
                   _resp({bp: ("ml-auto" if v[bp] and v[bp][1] == "auto" else _px("ml", v[bp][1]) if v[bp] and v[bp][1] is not None else "ml-0") for bp in BPS}),
                   _resp({bp: (v[bp][2] if v[bp] and v[bp][2] else "self-auto") for bp in BPS})]
            if need_order:
                pos.append(_resp({bp: f"order-[{need_order[bp].get(id(c), 0)}]" if bp in need_order else "order-none" for bp in BPS}))
            vis = {bp: _shown(c, bp) for bp in BPS}
            out += (_text(c, indent + 1, vis, _j(pos)) if c.kind == "text" else
                    _block(c, indent + 1, {bp: frame[bp][2] for bp in BPS}, vis, _j(pos)))
        out.append(f"{pad}</div>")
    return out


def _columns(items, frame, splits, ref, indent, depth) -> list[str]:
    """Side-by-side stacks → grid with fractional tracks where the design shows them side by side, one track where
    it stacks them."""
    pad = "  " * indent
    s0, s1, left, right = splits[ref]
    left, right = list(left), list(right)
    for c in items:    # items absent at the reference breakpoint: side by relative x elsewhere
        if c not in left and c not in right:
            bp = next(iter(c.at))
            rel = (_box(c, bp)[0] - frame[bp][0]) / max(frame[bp][2], 1)
            (right if rel >= (s1 - frame[ref][0]) / max(frame[ref][2], 1) else left).append(c)
    left = [c for c in items if c in left]
    right = [c for c in items if c in right]
    side = {bp: bool(splits[bp]) and {id(c) for c in splits[bp][2]} <= {id(c) for c in left} for bp in BPS}
    cols, gx, fl, fr, mt = {}, {}, {}, {}, {}
    for bp in BPS:
        fx, fy, fw, fh = frame[bp]
        lu, ru = _union(left, bp), _union(right, bp)
        top = min([u[1] for u in (lu, ru) if u] or [fy])
        mt[bp] = max(0, top - fy)
        if side[bp] and lu and ru:
            a, b = splits[bp][0], splits[bp][1]
            cols[bp] = f"grid-cols-[minmax(0,{max(a - fx, 1)}fr)_minmax(0,{max(fx + fw - b, 1)}fr)]"
            gx[bp] = _px("gap-x", b - a)
            fl[bp], fr[bp] = [fx, top, a - fx, fh], [b, top, fx + fw - b, fh]
        else:
            cols[bp], gx[bp] = "grid-cols-1", "gap-x-0"
            fl[bp] = [fx, top, fw, fh]
            fr[bp] = [fx, (lu[1] + lu[3]) if lu else top, fw, fh]
    out = [f'{pad}<div className="grid {_resp(cols)} {_resp(gx)} gap-y-0 {_resp({bp: _px("mt", mt[bp]) for bp in BPS})} w-full items-start">']
    for group, fr_ in ((left, fl), (right, fr)):
        out.append(f'{pad}  <div data-seg="{_seg("column", group, depth)}" className="min-w-0 flow-root">')
        out += _layout(group, fr_, indent + 2, depth + 1)
        out.append(f"{pad}  </div>")
    return out + [f"{pad}</div>"]


# ---------------------------------------------------------------------------------------------------------------
# bands, fold, root

def _band_bg(band: list[Item]):
    """A member block spanning (almost) the whole viewport with content inside = the band's full-bleed background."""
    for c in band:
        if c.kind == "block" and c.children and all(c.at[bp]["box"][2] >= 0.97 * W[bp] for bp in c.at):
            return c
    return None


def _container(u, bp, intent):
    """Content container of a band at bp from the measured gutters: (classes, content frame x, content frame w)."""
    lg, rg = u[0], W[bp] - (u[0] + u[2])
    centred = abs(lg - rg) <= max(12, 0.04 * W[bp])
    c = lambda maxw, mx, pl, pr: {"maxw": maxw, "mx": mx, "pl": _px("pl", pl), "pr": _px("pr", pr)}
    if intent == "full" or (intent is None and not centred and u[2] >= 0.85 * W[bp]):
        return c("max-w-none", "mx-0", lg, max(0, rg)), lg, W[bp] - lg - max(0, rg)
    if intent == "centred" or centred:
        g = max(0, min(lg, rg))
        if u[2] < 0.8 * W[bp] and g > 24:             # narrow centred column: its width is a maximum
            p = 16
            return c(f"max-w-[{u[2] + 2 * p}px]", "mx-auto", p, p), lg, u[2]
        return c(f"max-w-[{W[bp]}px]", "mx-auto", g, g), g, W[bp] - 2 * g
    pr = max(16, min(rg, lg))                        # left-anchored
    return c("max-w-none", "mx-0", lg, pr), lg, W[bp] - lg - pr


def _lift_siblings(its: list[Item]) -> list[Item]:
    """A card can't hold a card of the same style and (nearly) its width: measurement ran the first card's box to
    the fold (its bottom border is below it), so the next card nested inside it. Lift it out as the next sibling."""
    out = []
    for it in its:
        out.append(it)
        if it.kind != "block":
            continue
        it.children = _lift_siblings(it.children)
        keep = []
        for ch in it.children:
            same = ch.kind == "block" and ch.children and any(
                bp in it.at and it.at[bp].get("border") and it.at[bp].get("border") == ch.at[bp].get("border")
                and ch.at[bp]["box"][2] >= 0.9 * it.at[bp]["box"][2] for bp in ch.at)
            (out if same else keep).append(ch)
        it.children = keep
    return out


def _synth(roots: list[Item]):
    """Boxes for blocks missing from a frame whose children are there, children first. A container (≥ 2 children
    there) becomes a transparent region around them, padded like the frames that show it (desktop's bordered wrapper
    around three columns is not a box on mobile, where each card is its own box; the per-card regions on desktop are
    plain columns). A single label (a button OCR read but measurement missed) keeps v1's synthesis (same size, fill)."""
    def walk(its):
        for it in its:
            walk(it.children)
            if it.kind != "block" or not it.children:
                continue
            ref = next((bp for bp in BPS if bp in it.at and _union(it.children, bp)), None)
            for bp in BPS:
                if bp in it.at or ref is None:
                    continue
                kids = [ch for ch in it.children if bp in ch.at]
                if len(kids) >= 2:
                    rb, ru, u = it.at[ref]["box"], _union(it.children, ref), _union(kids, bp)
                    pl, pt = max(0, ru[0] - rb[0]), max(0, ru[1] - rb[1])
                    pr, pb = max(0, rb[0] + rb[2] - ru[0] - ru[2]), max(0, rb[1] + rb[3] - ru[1] - ru[3])
                    x0, y0 = max(0, u[0] - pl), max(0, u[1] - pt)
                    x1 = min(W[bp], u[0] + u[2] + pr)
                    it.at[bp] = {"box": [x0, y0, x1 - x0, u[1] + u[3] + pb - y0], "fill": None, "border": None,
                                 "radius": None, "shadow": False, "synth": "region"}
                elif kids:
                    ch = kids[0]
                    if ref not in ch.at:
                        continue
                    rb, cr, cb = it.at[ref]["box"], _box(ch, ref), _box(ch, bp)
                    it.at[bp] = {"box": [cb[0] - (cr[0] - rb[0]), cb[1] - (cr[1] - rb[1]), rb[2], rb[3]],
                                 "fill": it.at[ref].get("fill"), "border": it.at[ref].get("border"),
                                 "radius": it.at[ref].get("radius"), "synth": True}
    walk(roots)


def _merge_variants(items: list[Item]) -> list[Item]:
    """The same text read slightly differently per frame (you're / you’re, a dropped word) became separate items
    with disjoint frames: one element duplicated, which also broke the fold logic. Merge near-identical texts."""
    import difflib
    texts = [c for c in items if c.kind == "text"]
    gone = set()
    for i, a in enumerate(texts):
        if id(a) in gone:
            continue
        for b in texts[i + 1:]:
            if id(b) in gone or set(a.at) & set(b.at) or min(len(a.text), len(b.text)) < 12:
                continue
            if difflib.SequenceMatcher(None, a.text.lower(), b.text.lower()).ratio() >= 0.9:
                a.at.update(b.at)
                gone.add(id(b))
    return [c for c in items if id(c) not in gone]


def compile_fluid(spec: dict, intents: dict | None = None) -> str:
    SEGMENTS.clear()
    items = _merge_variants(_collect(spec, anchored=True))
    MENU.clear()
    MENU.update(_detect_menu(items))
    roots = _lift_siblings(_tree(items))
    _synth(roots)
    flat = []
    def walk(its):
        for it in its:
            flat.append(it)
            walk(it.children)
    walk(roots)
    STATE.clear()
    STATE.update({"all": flat, "intents": intents or {}})

    ref = max(BPS, key=lambda bp: sum(1 for c in roots if bp in c.at))
    bands = _bands(roots, ref)
    if not bands or not _bands_consistent(bands):
        bands = [roots]
    member = {id(c): k for k, b in enumerate(bands) for c in b}
    last = 0
    for c in sorted(roots, key=lambda c: min(_box(c, bp)[1] / VH[bp] for bp in c.at)):
        last = member.setdefault(id(c), last)
    bands = [b for b in ([c for c in roots if member[id(c)] == k] for k in range(len(bands))) if b]
    # trailing bands absent from a frame are below that frame's fold
    tail_start = len(bands)
    for k in range(len(bands) - 1, 0, -1):
        if any(not any(bp in c.at for c in bands[k]) for bp in BPS):
            tail_start = k
        else:
            break
    body, tail = bands[:tail_start], bands[tail_start:]
    prev_bottom = {bp: 0 for bp in BPS}

    def emit_band(k, band, indent):
        pad = "  " * indent
        bg = _band_bg(band)
        content = [c for c in band if c is not bg] + (bg.children if bg else [])
        ub = {bp: _union(content, bp) for bp in BPS}
        bb = {bp: (bg.at[bp]["box"] if bg and bp in bg.at else ub[bp]) for bp in BPS}
        mt = {bp: (max(0, bb[bp][1] - prev_bottom[bp]) if bb[bp] else 0) for bp in BPS}
        pt = {bp: (max(0, ub[bp][1] - bb[bp][1]) if bg and ub[bp] and bb[bp] else 0) for bp in BPS}
        cont, frames = {}, {}
        for bp in BPS:
            if ub[bp]:
                u = ub[bp]
            else:            # not in this frame: the nearest frame's gutters, scaled
                o = next(o for o in BPS if ub[o])
                s = W[bp] / W[o]
                u = [round(ub[o][0] * s), ub[o][1], round(ub[o][2] * s), ub[o][3]]
            intent = STATE["intents"].get("bands", {}).get(str(k), {}).get(bp)
            cont[bp], x, w = _container(u, bp, intent)
            frames[bp] = [x, u[1], w, u[3]]
        bg_fill = _resp({bp: (f"bg-[{bg.at[bp]['fill']}]" if bg and bp in bg.at and bg.at[bp].get("fill") else "bg-transparent") for bp in BPS})
        min_h = _resp({bp: (f"min-h-[{bb[bp][3]}px]" if bg and bb[bp] else "min-h-0") for bp in BPS})
        sid = _seg("band", band, 0)
        lines = [f'{pad}<div data-seg="{sid}" className="flow-root w-full {bg_fill} {min_h} {_resp({bp: _px("mt", mt[bp]) for bp in BPS})} '
                 f'{_resp({bp: _px("pt", pt[bp]) for bp in BPS})}">',
                 f'{pad}  <div className="w-full {_rc(cont)}">']
        lines += _layout(content, frames, indent + 2)
        lines += [f"{pad}  </div>", f"{pad}</div>"]
        for bp in BPS:
            if bb[bp]:
                prev_bottom[bp] = bb[bp][1] + bb[bp][3]
        return lines

    out = []
    if tail:
        tail_top = {bp: min((_box(c, bp)[1] for b in tail for c in b if bp in c.at), default=None) for bp in BPS}
        mh = _resp({bp: (f"min-h-[{tail_top[bp]}px]" if tail_top[bp] is not None else "min-h-screen") for bp in BPS})
        out.append(f'      <div className="flex flex-col w-full {mh}">')
        for k, b in enumerate(body):
            out += emit_band(k, b, 4)
        out.append("      </div>")
        for bp in BPS:
            prev_bottom[bp] = tail_top[bp] if tail_top[bp] is not None else 0
        for k, b in enumerate(tail, len(body)):
            out += emit_band(k, b, 3)
    else:
        for k, b in enumerate(body):
            out += emit_band(k, b, 3)
    _link_segments()
    bgs = {bp: spec["breakpoints"].get(bp, {}).get("background", "#ffffff") for bp in BPS}
    root_cls = f"flow-root min-h-screen w-full font-sans {_resp({bp: f'bg-[{bgs[bp]}]' for bp in BPS})}"
    head = ('import { useState } from "react";\n\nexport default function App() {\n'
            '  const [menuOpen, setMenuOpen] = useState(false);\n  return (\n') if MENU else "export default function App() {\n  return (\n"
    return head + f'    <div className="{root_cls}">\n' + "\n".join(out) + "\n    </div>\n  );\n}\n"
