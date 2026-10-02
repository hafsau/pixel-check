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

from .scaffold import (BPS, MENU, PREFIX, SEGMENTS, SIZES, TAGS, Item, _attr, _bands, _bands_consistent, _collect,
                       _detect_menu, _elem_box, _jsx_text, _link_segments, _placeholder_variant, _px, _resp, _seg,
                       _tree)

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
    """Shown at bp: present there, or absent but below its fold — unless another frame that lacks it clearly hides it
    (content shown in one frame only and hidden where it would fit is frame-specific content: lambda's mobile-only
    column descriptions landed exactly at desktop's fold and were drawn there)."""
    if bp in c.at:
        return True
    return all(_shown_raw(c, b) for b in BPS if b not in c.at)


def _shown_raw(c: Item, bp: str) -> bool:
    """Absent from a frame = below that frame's fold (render it, after everything visible) unless an element
    that comes after it elsewhere IS visible in this frame (then the design omits it here: hide it)."""
    if bp in c.at:
        return True
    ref = next(iter(c.at))
    y = _box(c, ref)[1]
    if any(bp in d.at and ref in d.at and _box(d, ref)[1] > y + 4 for d in STATE["all"]):
        return False
    # nothing after it is visible here; but would it have landed inside this frame? Place it below the nearest
    # element above it that both frames show: inside the viewport → the design hides it here (lambda's desktop-only
    # column descriptions on tablet); below the viewport → it is just below this frame's fold
    above = [d for d in STATE["all"] if bp in d.at and ref in d.at and _box(d, ref)[1] + _box(d, ref)[3] <= y + 2]
    if not above:   # nothing above it: it would sit at the top of this frame — on screen, so the design hides it
        return y + 0.5 * _box(c, ref)[3] > VH[bp]
    d = max(above, key=lambda d: _box(d, ref)[1] + _box(d, ref)[3])
    est = _box(d, bp)[1] + _box(d, bp)[3] + (y - (_box(d, ref)[1] + _box(d, ref)[3]))
    return est + 0.5 * _box(c, ref)[3] > VH[bp]


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
        y, h = _box(c, bp)[1], _box(c, bp)[3]
        # a row it shares a line with where it is shown (vercel's tablet hamburger beside the logo, 1 px apart in y)
        same = [k for k, row in enumerate(rows) if any(
            bp in r.at and min(_box(r, bp)[1] + _box(r, bp)[3], y + h) - max(_box(r, bp)[1], y) >= 0.5 * min(h, _box(r, bp)[3])
            for r in row)]
        if same:
            rows[same[0]].append(c)
            continue
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
    # consecutive rows that share a line in ANOTHER frame belong in one row wrapper (it becomes a column where the
    # design stacks them): lambda's two hero buttons stack on mobile, sit side by side on tablet/desktop
    merged = [rows[0]] if rows else []
    for row in rows[1:]:
        prev = merged[-1]
        # small rows only (2 + 2 items), all shown where they share the line — chaining merges collapsed vercel's
        # whole feature list into one row because desktop-only items of other columns shared its lines
        small = len(prev) <= 2 and len(row) <= 2
        if small and any(_same_line(prev, row, bp) and all(bp in c.at or not _shown(c, bp) for c in prev + row) for bp in BPS):
            prev.extend(row)
        else:
            merged.append(row)
    return merged


def _same_line(a: list[Item], b: list[Item], bp: str) -> bool:
    pa, pb = [c for c in a if bp in c.at], [c for c in b if bp in c.at]
    if not pa or not pb:
        return False
    ua, ub = _union(pa, bp), _union(pb, bp)
    ov = min(ua[1] + ua[3], ub[1] + ub[3]) - max(ua[1], ub[1])
    disjoint_x = ua[0] + ua[2] <= ub[0] + 2 or ub[0] + ub[2] <= ua[0] + 2
    return disjoint_x and ov >= 0.5 * min(ua[3], ub[3])


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
        # toggled by the hamburger where the design hides it; always shown from the first frame that shows it
        first = next((b for b in BPS if b in c.at), None)
        always = f"{PREFIX[first]}block" if first and first != "mobile" else ""
        return [f'{pad}<{tag}{href} className={{`${{menuOpen ? "block" : "hidden"}} {always} {body}`}}>{_jsx_text(c.text)}</{tag}>']
    return [f'{pad}<{tag}{href} className="{_j([_disp(vis, "block"), body])}">{_jsx_text(c.text)}</{tag}>']


def _borders(at: dict) -> str:
    """One class per side + colour (a multi-token "border border-[#x]" would leak its colour to other breakpoints).
    border_l: a column divider measured as a vertical rule left of a card."""
    if not any(at[bp].get(k) for bp in BPS for k in ("border", "border_l", "border_t", "border_b")):
        return "border-0"
    per = {}
    for bp in BPS:
        a = at[bp]
        full = a.get("border")
        side = {s: full or a.get(f"border_{s}") for s in "tlb"}
        colour = full or side["l"] or side["t"] or side["b"]
        per[bp] = {"t": "border-t" if side["t"] else "border-t-0", "r": "border-r" if full else "border-r-0",
                   "b": "border-b" if side["b"] else "border-b-0", "l": "border-l" if side["l"] else "border-l-0",
                   "c": f"border-[{colour}]" if colour else "border-transparent"}
    return _rc(per)


def _one_line(c: Item) -> bool:
    """A control (button / input / badge) holds ONE line of content and is not much taller than it; a region with a
    label above a heading (lambda's "01" over its column title) is a container, not a control."""
    for bp in c.at:
        kids = [ch for ch in c.children if bp in ch.at]
        if not kids:
            continue
        bs = [_box(ch, bp) for ch in kids]
        top, bot = max(b[1] for b in bs), min(b[1] + b[3] for b in bs)
        if bot - top < 0.3 * min(b[3] for b in bs):
            return False
        if c.at[bp]["box"][3] > 2.5 * max(b[3] for b in bs) + 24:
            return False
    return True


def _block(c: Item, indent: int, cont_w: dict, vis: dict, pos: str) -> list[str]:
    pad = "  " * indent
    at = {bp: c.at.get(bp) or c.at[next(iter(c.at))] for bp in BPS}
    box = {bp: at[bp]["box"] for bp in BPS}
    full = {bp: box[bp][2] >= 0.92 * cont_w[bp] for bp in BPS}
    width = _resp({bp: ("w-full" if full[bp] else f"w-[{box[bp][2]}px] max-w-full") for bp in BPS})
    style = [_resp({bp: f"bg-[{at[bp]['fill']}]" if at[bp].get("fill") else "bg-transparent" for bp in BPS}),
             _borders(at),
             _resp({bp: f"rounded-[{at[bp]['radius']}px]" if at[bp].get("radius") else "rounded-none" for bp in BPS}),
             _resp({bp: "shadow-sm" if at[bp].get("shadow") else "shadow-none" for bp in BPS})]
    texts = [ch for ch in c.children if ch.kind == "text"]
    if getattr(c, "grid", None):
        return _grid(c, indent, width, style, vis, pos)
    if MENU and c.key == MENU.get("trigger"):
        return [f'{pad}<button type="button" aria-label="Open menu" aria-expanded={{menuOpen}} onClick={{() => setMenuOpen((o) => !o)}} '
                f'className="{_j([_disp(vis, "block"), width, _resp({bp: f"h-[{box[bp][3]}px]" for bp in BPS}), *style, "shrink-0 cursor-pointer", pos])}" />']
    if not c.children:   # rule / icon / image placeholder
        h = _resp({bp: f"h-[{max(1, box[bp][3])}px]" for bp in BPS})
        return [f'{pad}<div aria-hidden="true" className="{_j([_disp(vis, "block"), width, h, *style, "shrink-0", pos])}" />']
    if texts and len(c.children) <= 3 and not any(ch.kind == "block" and ch.children for ch in c.children) and _one_line(c):
        # control (button / input / badge): measured height, label centred or inset like the design
        first = texts[0]
        # the label group (icon + text) is what is centred or inset, not the text alone
        fb = {bp: _union(c.children, bp) for bp in BPS}
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


def _grid(c: Item, indent: int, width: str, style: list, vis: dict, pos: str) -> list[str]:
    """A planned card grid: CSS grid with the column count each frame shows; every card fills its cell."""
    pad = "  " * indent
    cards = sorted([ch for ch in c.children if getattr(ch, "card", None) is not None], key=lambda ch: ch.card)
    cols, gx, gy = {}, {}, {}
    for bp in BPS:
        bs = [ch.at[bp]["box"] for ch in cards if bp in ch.at]
        n = 1
        if bs:
            row0 = [b for b in bs if b[1] < min(x[1] for x in bs) + 0.5 * min(x[3] for x in bs)]
            n = max(1, len(row0))
        cols[bp] = f"grid-cols-{n}"
        srt = sorted(bs, key=lambda b: (b[1], b[0]))
        hg = [srt[k + 1][0] - (srt[k][0] + srt[k][2]) for k in range(len(srt) - 1) if abs(srt[k + 1][1] - srt[k][1]) < 20]
        vg = [srt[k + 1][1] - (srt[k][1] + srt[k][3]) for k in range(len(srt) - 1) if srt[k + 1][1] >= srt[k][1] + srt[k][3] - 8]
        gx[bp] = _px("gap-x", max(0, min(hg))) if hg else "gap-x-0"
        gy[bp] = _px("gap-y", max(0, min(vg))) if vg else "gap-y-0"
    disp = _disp(vis, "grid") or "grid"
    out = [f'{pad}<div data-seg="{_seg("cards", cards, 1)}" className="{_j([disp, _resp(cols), _resp(gx), _resp(gy), width, *style, "shrink-0 items-stretch", pos])}">']
    for card in cards:
        cw = {bp: (card.at.get(bp) or card.at[next(iter(card.at))])["box"][2] for bp in BPS}
        out += _block(card, indent + 1, cw, {bp: _shown(card, bp) for bp in BPS}, "")
    return out + [f"{pad}</div>"]


def _apply_cards(items: list[Item], groups: list[list[list[str]]]) -> list[Item]:
    """Execute a planned card grouping: each card becomes a block around its members (styled, per frame, by the
    measured box that holds most of that card and little else, transparent where the frame shows the card as a
    plain column); the grid becomes a block around the cards (styled by a measured box that holds several cards,
    e.g. desktop's bordered wrapper). Measured boxes that were a card's or the grid's outline in a frame are absorbed
    for that frame; vertical rules between columns become a card's left border. Geometry decides boxes and column
    counts; the plan only decides which elements belong together."""
    by_key = {c.key: c for c in items}
    out = list(items)
    for g_i, cards in enumerate(groups):
        mem = [[by_key[k] for k in card if k in by_key] for card in cards]
        mem = [m for m in mem if m]
        if len(mem) < 2:
            continue
        # verify the plan against geometry: a member box that encloses most of ANOTHER card's members (and little of
        # its own) is that card's outline (the planner put Pro's mobile outline into Hobby, Oct 1)
        for j in range(len(mem)):
            for b in [m for m in mem[j] if m.kind == "block"]:
                for bp in b.at:
                    k, frac, n_in = _enclosure(b, bp, mem)
                    if k is not None and k != j and frac[k] >= 0.6 and n_in[j] <= 0.3 * n_in[k]:
                        mem[j].remove(b)
                        mem[k].append(b)
                        STATE.setdefault("plan_fixes", []).append(f"{b.key}: card {j} -> {k}")
                        break
        member_ids = {id(m) for card in mem for m in card}
        style = [dict() for _ in mem]
        grid_style = {}
        for b in [c for c in out if c.kind == "block"]:
            for bp in list(b.at):
                bx = b.at[bp]["box"]
                if bx[3] <= 3:
                    continue
                k, frac, n_in = _enclosure(b, bp, mem)
                if k is None:
                    continue
                if frac[k] >= 0.6 and all(n <= 0.3 * n_in[k] for i, n in enumerate(n_in) if i != k):
                    # the card's outline in this frame (also when the planner listed it as a member)
                    if b in mem[k] or id(b) not in member_ids:
                        if bp not in style[k] or bx[2] * bx[3] < style[k][bp]["box"][2] * style[k][bp]["box"][3]:
                            style[k][bp] = dict(b.at[bp])
                        del b.at[bp]
                elif id(b) not in member_ids and sum(1 for f in frac if f >= 0.5) >= 2:
                    if bp not in grid_style or bx[2] * bx[3] > grid_style[bp]["box"][2] * grid_style[bp]["box"][3]:
                        grid_style[bp] = dict(b.at[bp])
                    del b.at[bp]
        mem = [[m for m in card if m.at] for card in mem]
        out = [c for c in out if c.at]
        card_items = []
        for i, card in enumerate(mem):
            it = Item(f"card:{g_i}:{i}", "block")
            it.card = i
            for bp in BPS:
                u = _union(card, bp)
                if not u:
                    continue
                # padding: from the measured outline in this frame, else in another frame that shows one
                src = bp if bp in style[i] else next((o for o in BPS if o in style[i] and _union(card, o)), None)
                if src:
                    sb, su = style[i][src]["box"], _union(card, src)
                    pl, pt = max(0, su[0] - sb[0]), max(0, su[1] - sb[1])
                    p_b = min(max(0, sb[1] + sb[3] - su[1] - su[3]), max(pl, pt))
                else:
                    pl = pt = p_b = 24
                own = style[i].get(bp, {})
                if own:   # the measured outline in this frame; only its bottom may run to the fold, so bound it
                    ob = own["box"]
                    box = [ob[0], ob[1], ob[2], min(ob[3], u[1] + u[3] + p_b - ob[1])]
                else:
                    box = [u[0] - pl, u[1] - pt, u[2] + 2 * pl, u[3] + pt + p_b]
                it.at[bp] = {"box": box, "fill": own.get("fill"),
                             "border": own.get("border"), "radius": own.get("radius"), "shadow": own.get("shadow", False)}
            card_items.append(it)
        for bp in BPS:     # stacked cards must not overlap (a measured card box can run to the fold)
            bs = sorted([c for c in card_items if bp in c.at], key=lambda c: c.at[bp]["box"][1])
            for a, b in zip(bs, bs[1:]):
                ab, bb = a.at[bp]["box"], b.at[bp]["box"]
                if bb[1] >= ab[1] + 0.5 * ab[3] and ab[1] + ab[3] > bb[1]:
                    ab[3] = bb[1] - ab[1]
        for r in [c for c in out if c.kind == "block" and id(c) not in member_ids]:   # column dividers
            for bp in list(r.at):
                rb = r.at[bp]["box"]
                if rb[2] > 3 or rb[3] < 40:
                    continue
                near = [c for c in card_items if bp in c.at and abs(c.at[bp]["box"][0] - rb[0]) <= 24
                        and c.at[bp]["box"][1] - 40 <= rb[1] <= c.at[bp]["box"][1] + c.at[bp]["box"][3]]
                if near:
                    near[0].at[bp]["border_l"] = r.at[bp].get("fill") or r.at[bp].get("border")
                    del r.at[bp]
        out = [c for c in out if c.at]
        grid = Item(f"grid:{g_i}", "block")
        grid.grid = True
        for bp in BPS:
            u = _union(card_items, bp)
            if not u:
                continue
            gs = grid_style.get(bp)
            box = gs["box"] if gs and _inside_box(u, gs["box"], 12) else u
            grid.at[bp] = {"box": list(box), "fill": gs.get("fill") if gs else None, "border": gs.get("border") if gs else None,
                           "radius": gs.get("radius") if gs else None, "shadow": gs.get("shadow", False) if gs else False}
        out += card_items + [grid]
    return out


def _enclosure(b: Item, bp: str, mem: list[list[Item]]):
    """Which card a box outlines at bp → (card index | None, fraction of each card's visible members inside, counts).
    An outline is clearly bigger than what it encloses (a badge pill around "Pro" is not the Pro card)."""
    bx = b.at[bp]["box"]
    others = [[m for m in card if m is not b and bp in m.at] for card in mem]
    ins = [[m for m in o if _centre(_box(m, bp), bx)] for o in others]
    n_in = [len(x) for x in ins]
    if not any(n_in):
        return None, [], n_in
    u = _union([m for x in ins for m in x], bp)
    if sum(n_in) <= 2 and bx[3] < 1.8 * u[3] and bx[2] * bx[3] < 2 * u[2] * u[3]:
        return None, [], n_in
    frac = [n / len(o) if o else 0 for n, o in zip(n_in, others)]
    return max(range(len(mem)), key=lambda i: (n_in[i], frac[i])), frac, n_in


def _centre(box, outer, slack=3):
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    return outer[0] - slack <= cx <= outer[0] + outer[2] + slack and outer[1] - slack <= cy <= outer[1] + outer[3] + slack


def _inside_box(a, b, slack=3):
    return a[0] >= b[0] - slack and a[1] >= b[1] - slack and a[0] + a[2] <= b[0] + b[2] + slack and a[1] + a[3] <= b[1] + b[3] + slack


def prepare(spec: dict) -> list[Item]:
    """Measured items as the fluid compiler sees them (the intent planner names these)."""
    from .match import rematch_textfree
    return rematch_textfree(_merge_variants(_collect(spec, anchored=True)))


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


def _band_sig(band: list[Item]) -> str:
    """Stable band identity for intents: its first text in reading order (band indices shift when a card plan
    regroups elements)."""
    flat = []
    def walk(its):
        for it in its:
            flat.append(it)
            walk(it.children)
    walk(band)
    texts = [c for c in flat if c.kind == "text"]
    if not texts:
        return "band:" + ",".join(sorted(c.key for c in band))[:80]
    first = min(texts, key=lambda c: min(_box(c, bp)[1] / VH[bp] for bp in c.at))
    return first.key


def _container(u, bp, intent):
    """Content container of a band at bp from the measured gutters → (classes, content frame x, content frame w).
    The design width is reproduced either way; the choice only matters between / beyond the frames.
    intent (desktop only, from the planner): "full" = stretch edge to edge beyond 1280; "centred" = the 1280 column
    stays centred (the band keeps its own gutters inside it)."""
    lg, rg = u[0], W[bp] - (u[0] + u[2])
    centred = abs(lg - rg) <= max(12, 0.04 * W[bp])
    c = lambda maxw, mx, pl, pr: {"maxw": maxw, "mx": mx, "pl": _px("pl", pl), "pr": _px("pr", pr)}
    if centred and u[2] < 0.8 * W[bp] and min(lg, rg) > 24:   # narrow centred column: its width is a maximum
        p = 16
        return c(f"max-w-[{u[2] + 2 * p}px]", "mx-auto", p, p), lg, u[2]
    if intent == "centred":
        if centred:
            g = max(0, min(lg, rg))
            return c(f"max-w-[{W[bp]}px]", "mx-auto", g, g), g, W[bp] - 2 * g
        pr = max(16, min(rg, lg))
        return c(f"max-w-[{W[bp]}px]", "mx-auto", lg, pr), lg, W[bp] - lg - pr
    if intent == "full" or not centred and u[2] >= 0.85 * W[bp]:
        return c("max-w-none", "mx-0", lg, max(0, rg)), lg, W[bp] - lg - max(0, rg)
    if centred:
        g = max(0, min(lg, rg))
        if bp != BPS[-1]:        # page-width below the widest frame: stretch (the next breakpoint takes over)
            return c("max-w-none", "mx-0", g, g), g, W[bp] - 2 * g
        return c(f"max-w-[{W[bp]}px]", "mx-auto", g, g), g, W[bp] - 2 * g
    pr = max(16, min(rg, lg))    # left-anchored
    return c("max-w-none", "mx-0", lg, pr), lg, W[bp] - lg - pr


def _split(children: list[Item], bp: str):
    """Side-by-side stacks (v1's X-Y cut, relaxed): a vertical gutter no element crosses, items on both sides
    overlapping vertically, and one side's item spanning ≥ 2 stacked items on the other. v1 required ≥ 2 items on
    each side, which missed the sidebar case (calcom's desktop panel is ONE box beside a stacked form).
    Returns (left_right_edge, right_left_edge, left, right)."""
    present = [c for c in children if bp in c.at]
    if len(present) < 3:
        return None
    boxes = {id(c): _box(c, bp) for c in present}
    best = None
    for c in present:
        s0 = boxes[id(c)][0] + boxes[id(c)][2]
        left = [d for d in present if boxes[id(d)][0] + boxes[id(d)][2] <= s0]
        right = [d for d in present if d not in left]
        if not left or not right:
            continue
        s1 = min(boxes[id(d)][0] for d in right)
        if any(boxes[id(d)][0] < s0 for d in right) or s1 - s0 < 16:
            continue
        ly0, ly1 = min(boxes[id(d)][1] for d in left), max(boxes[id(d)][1] + boxes[id(d)][3] for d in left)
        ry0, ry1 = min(boxes[id(d)][1] for d in right), max(boxes[id(d)][1] + boxes[id(d)][3] for d in right)
        if min(ly1, ry1) - max(ly0, ry0) < 0.5 * min(ly1 - ly0, ry1 - ry0):
            continue
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


def _decorations(items: list[Item]) -> list[Item]:
    """Background patterns (lennysjobs' hero: ~100 scattered pill shapes behind the heading and search box) are not
    layout: laid out in flow they wrecked the page. A text-free leaf box that PARTLY overlaps other content in most
    of its frames is decoration, and so is the rest of a large same-style group (≥ 8) where most members are.
    Dropped (the band keeps its background colour); the count is recorded in STATE["decorations"]."""
    from .match import _style
    others = [c for c in items if c.kind == "text" or c.kind == "block"]

    def holds(c):   # contains another element's centre in some frame → a container (hero background), not decoration
        return any(o is not c and bp in o.at and _centre(_box(o, bp), c.at[bp]["box"], 0)
                   and _box(o, bp)[2] * _box(o, bp)[3] < c.at[bp]["box"][2] * c.at[bp]["box"][3]
                   for bp in c.at for o in others)
    leaves = [c for c in items if c.kind == "block" and not holds(c)]

    def partial(c, bp):
        a = c.at[bp]["box"]
        for o in others:
            if o is c or bp not in o.at:
                continue
            b = _box(o, bp)
            ix = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
            iy = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
            if ix <= 2 or iy <= 2:
                continue
            a_in_b = a[0] >= b[0] - 2 and a[1] >= b[1] - 2 and a[0] + a[2] <= b[0] + b[2] + 2 and a[1] + a[3] <= b[1] + b[3] + 2
            b_in_a = b[0] >= a[0] - 2 and b[1] >= a[1] - 2 and b[0] + b[2] <= a[0] + a[2] + 2 and b[1] + b[3] <= a[1] + a[3] + 2
            if not a_in_b and not b_in_a:
                return True
        return False

    deco = {id(c) for c in leaves if sum(partial(c, bp) for bp in c.at) * 2 > len(c.at)}
    import math
    groups: dict = {}
    for c in leaves:   # style + size class: grey image placeholders, icons and tiles share a colour
        bp = next(iter(c.at))
        groups.setdefault((_style(c.at[bp]), round(math.log2(max(c.at[bp]["box"][3], 1)))), []).append(c)
    texts = [o for o in items if o.kind == "text"]

    def lonely(c):   # no text right next to it in any frame (an icon sits beside its label; a pattern pill doesn't)
        for bp in c.at:
            a = c.at[bp]["box"]
            for t in texts:
                if bp in t.at:
                    b = _box(t, bp)
                    gap = max(0, b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2])) + max(0, b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]))
                    if gap <= 12:
                        return False
        return True
    for g in groups.values():
        if len(g) >= 8 and sum(id(c) in deco for c in g) * 2 >= len(g):
            deco |= {id(c) for c in g}
        elif len(g) >= 10 and sum(lonely(c) for c in g) * 2 > len(g):
            # a pattern lies BEHIND content: text sits inside the area the lonely shapes cover
            lone = [c for c in g if lonely(c)]
            behind = False
            for bp in BPS:
                u = _union([c for c in lone if bp in c.at], bp)
                if u and any(bp in t.at and _centre(_box(t, bp), u, 0) for t in texts):
                    behind = True
            if behind:
                deco |= {id(c) for c in lone}
    STATE["decorations_dropped"] = len(deco)
    return [c for c in items if id(c) not in deco]


def _frames(items: list[Item]) -> list[Item]:
    """Thin rules forming ≥ 3 sides of a rectangle (a bordered box whose 4th side is cut by the viewport, or that
    measurement returned as separate segments) → ONE bordered block; its contents then nest inside it. As loose
    rules, a 459 px vertical line broke rows and columns (calcom desktop panel, Oct 1)."""
    def is_rule(c):
        return c.kind == "block" and not c.children and all(min(a["box"][2], a["box"][3]) <= 3 for a in c.at.values())
    rules = [c for c in items if is_rule(c)]
    used, out = set(), []
    for v in rules:
        if id(v) in used:
            continue
        bps = list(v.at)
        if not all(v.at[bp]["box"][3] > v.at[bp]["box"][2] and v.at[bp]["box"][3] >= 24 for bp in bps):
            continue
        # horizontal rules meeting this vertical rule's ends in every frame it is shown in
        def meets(h, end):
            if set(h.at) != set(bps) or id(h) in used or h is v:
                return False
            for bp in bps:
                vb, hb = v.at[bp]["box"], h.at[bp]["box"]
                if hb[2] <= hb[3]:
                    return False
                y = vb[1] if end == "top" else vb[1] + vb[3]
                near_x = abs(hb[0] - vb[0]) <= 4 or abs(hb[0] + hb[2] - (vb[0] + vb[2])) <= 4
                if abs(hb[1] - y) > 4 and abs(hb[1] + hb[3] - y) > 4 or not near_x:
                    return False
            return True
        top = next((h for h in rules if meets(h, "top")), None)
        bot = next((h for h in rules if meets(h, "bottom")), None)
        if not (top and bot):
            continue
        f = Item("frame:" + v.key, "block")
        for bp in bps:
            vb, tb, bb = v.at[bp]["box"], top.at[bp]["box"], bot.at[bp]["box"]
            x0, x1 = min(vb[0], tb[0], bb[0]), max(vb[0] + vb[2], tb[0] + tb[2], bb[0] + bb[2])
            y0, y1 = tb[1], bb[1] + bb[3]
            f.at[bp] = {"box": [x0, y0, x1 - x0, y1 - y0], "fill": None, "border": v.at[bp].get("fill"),
                        "radius": None, "shadow": False}
        used |= {id(v), id(top), id(bot)}
        out.append(f)
    return [c for c in items if id(c) not in used] + out


def _rule_regions(items: list[Item]) -> list[Item]:
    """A tall thin vertical rule with content to its right is that region's left border (lambda's 01/02/03 columns:
    each column is drawn with a 1 px left line). As a loose item it was laid out as content and pushed every column
    down a step. → a transparent block with border-left spanning the rule's height up to the next rule."""
    vert = [c for c in items if c.kind == "block" and not c.children
            and all(a["box"][2] <= 3 and a["box"][3] >= 40 for a in c.at.values())]
    if not vert:
        return items
    out = [c for c in items if c not in vert]
    for v in vert:
        reg = Item("region:" + v.key, "block")
        for bp, a in v.at.items():
            x0, y0, _, h = a["box"]
            # a box already starting at the line and spanning its height: the line is that box's left border
            host = next((c for c in out if c.kind == "block" and bp in c.at and abs(c.at[bp]["box"][0] - x0) <= 4
                         and abs(c.at[bp]["box"][1] - y0) <= 8 and abs(c.at[bp]["box"][3] - h) <= 12), None)
            if host is not None:
                host.at[bp]["border_l"] = a.get("fill")
                continue
            others = sorted(o.at[bp]["box"][0] for o in vert if o is not v and bp in o.at
                            and o.at[bp]["box"][0] > x0 + 8 and abs(o.at[bp]["box"][1] - y0) < h)
            inside = [c for c in out if bp in c.at and _box(c, bp)[0] >= x0 and (not others or _box(c, bp)[0] < others[0])
                      and y0 - 4 <= _box(c, bp)[1] and _box(c, bp)[1] + _box(c, bp)[3] <= y0 + h + 4]
            if not inside:
                continue
            x1 = others[0] - 1 if others else max(_box(c, bp)[0] + _box(c, bp)[2] for c in inside) + (inside and 8)
            reg.at[bp] = {"box": [x0, y0, max(8, x1 - x0), h], "fill": None, "border": None, "border_l": a.get("fill"),
                          "radius": None, "shadow": False}
        if reg.at:
            out.append(reg)
        elif not any("border_l" in c.at.get(bp, {}) for c in out for bp in v.at):
            out.append(v)
    return out


def _edge_rules(items: list[Item]) -> list[Item]:
    """A thin horizontal rule lying on a box's top or bottom edge is that box's border (perception measured
    vercel's wrapper top border as a separate full-width line; crossing every column gutter, it blocked the column
    split and the three plans' feature lists chained into one row)."""
    rules = [c for c in items if c.kind == "block" and all(a["box"][3] <= 3 and a["box"][2] >= 24 for a in c.at.values())]
    boxes = [c for c in items if c.kind == "block" and c not in rules]
    gone = set()
    for r in rules:
        hosted = 0
        for bp, a in r.at.items():
            x, y, w, _ = a["box"]
            for b in boxes:
                if bp not in b.at:
                    continue
                bx = b.at[bp]["box"]
                inside_x = x >= bx[0] - 4 and x + w <= bx[0] + bx[2] + 4 and w >= 0.85 * bx[2]
                if inside_x and abs(y - bx[1]) <= 3:
                    b.at[bp]["border_t"] = a.get("fill"); hosted += 1; break
                if inside_x and abs(y - (bx[1] + bx[3])) <= 3:
                    b.at[bp]["border_b"] = a.get("fill"); hosted += 1; break
        if hosted == len(r.at):
            gone.add(id(r))
    return [c for c in items if id(c) not in gone]


def _tree2(items: list[Item]) -> list[Item]:
    """Containment tree. v1 (scaffold._tree) voted per breakpoint with "no holder" as a candidate, so a container
    painted in one frame only (calcom's desktop panel) lost its children to the root 2:1 even though they sit inside
    it wherever it is shown. Here a holder's vote counts only where the holder exists; the root wins only when no
    holder contains the item in any frame. The holder in frames without a painted box becomes a transparent region
    (_synth)."""
    blocks = [b for b in items if b.kind == "block"]
    roots = []
    for it in items:
        votes: dict[int, float] = {}
        for bp in it.at:
            box = _box(it, bp)
            area = box[2] * box[3]
            holders = [b for b in blocks if b is not it and bp in b.at and _centre(box, b.at[bp]["box"])
                       and b.at[bp]["box"][2] * b.at[bp]["box"][3] > area * 1.01   # frames hug content (4 % larger)
                       and box[2] <= b.at[bp]["box"][2] + 4 and box[3] <= b.at[bp]["box"][3] + 4]
            if holders:
                h = min(holders, key=lambda b: b.at[bp]["box"][2] * b.at[bp]["box"][3])
                votes[id(h)] = votes.get(id(h), 0) + 1
        if not votes:
            roots.append(it)
            continue
        # a holder that is present but does NOT contain the item in some frame loses that frame's support
        def support(h):
            hb = next(b for b in blocks if id(b) == h)
            against = sum(1 for bp in it.at if bp in hb.at and not _centre(_box(it, bp), hb.at[bp]["box"]))
            return votes[h] - against
        best = max(votes, key=lambda h: (support(h), votes[h]))
        if support(best) <= 0:
            roots.append(it)
            continue
        holder = next(b for b in blocks if id(b) == best)
        holder.children.append(it)
    # cycle guard: an item must not end up inside its own descendant
    def cyc(node, seen):
        for ch in list(node.children):
            if id(ch) in seen:
                node.children.remove(ch)
                roots.append(ch)
            else:
                cyc(ch, seen | {id(ch)})
    for r in list(roots):
        cyc(r, {id(r)})
    return roots


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
                    # a transparent region hugs its contents: inherited padding is invisible but skewed the measured
                    # gutters (calcom tablet: 16 / 63 instead of 64 / 64 → content drifted at 1024 px)
                    u = _union(kids, bp)
                    x0, y0 = u[0], u[1]
                    x1, pb = u[0] + u[2], 0
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
    items = prepare(spec)
    intents = intents or {}
    if intents.get("cards"):
        items = _apply_cards(items, intents["cards"])
    MENU.clear()
    MENU.update(_detect_menu(items))
    roots = _lift_siblings(_tree2(_rule_regions(_edge_rules(_frames(_decorations(items))))))
    _synth(roots)
    flat = []
    def walk(its):
        for it in its:
            flat.append(it)
            walk(it.children)
    walk(roots)
    keep = {k: STATE[k] for k in ("plan_fixes", "decorations_dropped") if k in STATE}
    STATE.clear()
    STATE.update({"all": flat, "intents": intents, "bands": [], **keep})

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
        sig = _band_sig(band)
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
            intent = STATE["intents"].get("bands", {}).get(sig, {}).get(bp)
            cont[bp], x, w = _container(u, bp, intent)
            frames[bp] = [x, u[1], w, u[3]]
        bg_fill = _resp({bp: (f"bg-[{bg.at[bp]['fill']}]" if bg and bp in bg.at and bg.at[bp].get("fill") else "bg-transparent") for bp in BPS})
        min_h = _resp({bp: (f"min-h-[{bb[bp][3]}px]" if bg and bb[bp] else "min-h-0") for bp in BPS})
        sid = _seg("band", band, 0)
        STATE["bands"].append({"band": k, "sig": sig, "texts": [t for t in SEGMENTS[-1]["texts"][:4]],
                               "boxes": {bp: ub[bp] for bp in BPS if ub[bp]}, "container": {bp: cont[bp]["maxw"] for bp in BPS}})
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
