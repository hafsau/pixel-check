"""Stage 3 (docs/INTERACTIONS.md): compile the content an interaction reveals into a JSX panel component.

Input: the base spec and the state frames ({bp: frame} — a menu captured open at mobile and tablet). Per breakpoint
states.state_diff gives what appeared and the panel box; the appeared texts/blocks, shifted so the panel's top-left
is the origin, are laid out by the fluid compiler (same classes as the page). Persisted content (the header that
stays) is not part of the panel. The interaction writer (Nemotron, stage 4) mounts and wires the component.
"""
from __future__ import annotations

import re
from collections import Counter

from .fluid import compile_fluid

SIZES = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}
from .states import backdrop, classify, dim_region, panel_of, state_diff, trigger_look


def _shift(item: dict, dx: float, dy: float) -> dict:
    out = dict(item)
    b = item["box"]
    out["box"] = [b[0] - dx, b[1] - dy, b[2], b[3]]
    if item.get("line_boxes"):
        out["line_boxes"] = [[l[0] - dx, l[1] - dy, l[2], l[3]] for l in item["line_boxes"]]
    if item.get("inside_block"):
        ib = item["inside_block"]
        out["inside_block"] = [ib[0] - dx, ib[1] - dy, ib[2], ib[3]]
    return out


def compile_panel(base_spec: dict, states: dict, name: str = "Panel", triggers: dict | None = None,
                  images: dict | None = None) -> dict:
    """triggers: {bp: trigger box} — changes inside it (hamburger → X) are returned as trigger_changes, not panel.
    → {"jsx": component source | None, "kind": overlay|drawer|inline|none, "panel": {bp: box}, "diff": {bp: diff},
       "trigger_changes": {bp: {...}}}"""
    triggers = triggers or {}
    diffs = {bp: state_diff(base_spec["breakpoints"][bp], f, triggers.get(bp))
             for bp, f in states.items() if bp in base_spec["breakpoints"]}
    tchg = {bp: d["trigger_changes"] for bp, d in diffs.items()}
    back, look = {}, {}
    for bp, d in diffs.items():     # images: {bp: (base png, state png)} → a dimming layer behind the panel
        back[bp] = None
        if images and bp in images:
            import numpy as np
            from PIL import Image
            b_img, s_img = (np.asarray(Image.open(p).convert("RGB")) for p in images[bp])
            ex = [triggers[bp]] if triggers.get(bp) else ()
            dr = dim_region(b_img, s_img, exclude=ex)
            if dr is not None:      # the dimmed page behind a drawer is not panel content (perception reads it as new)
                m = dr["mask"]
                def dimmed(it):
                    x, y, w, h = it["box"]
                    cx, cy = int(min(m.shape[1] - 1, max(0, x + w / 2))), int(min(m.shape[0] - 1, max(0, y + h / 2)))
                    return bool(m[cy, cx])
                d["appeared"] = {"texts": [t for t in d["appeared"]["texts"] if not dimmed(t)],
                                 "blocks": [b for b in d["appeared"]["blocks"] if not dimmed(b)]}
                W, H = (states[bp].get("size") or [b_img.shape[1], b_img.shape[0]])
                d["panel"] = panel_of(d["appeared"]["texts"], d["appeared"]["blocks"])
                if d["panel"] and dr.get("undimmed"):
                    u, q = dr["undimmed"], d["panel"]
                    x0, y0 = min(u[0], q[0]), min(u[1], q[1])
                    d["panel"] = [x0, y0, max(u[0] + u[2], q[0] + q[2]) - x0, max(u[1] + u[3], q[1] + q[3]) - y0]
                covered = bool(d["panel"]) and any(t["box"][1] + t["box"][3] / 2 > d["panel"][1]
                                                   for t in d["disappeared"]["texts"])
                d["kind"] = classify(d["panel"], W, H, covered)
            if d["panel"]:
                back[bp] = backdrop(b_img, s_img, d["panel"], exclude=ex)
            if triggers.get(bp):
                look[bp] = trigger_look(b_img, s_img, triggers[bp])

    live = {bp: d for bp, d in diffs.items() if d["kind"] != "none"}
    if not live:
        return {"jsx": None, "kind": "none", "panel": {}, "diff": diffs, "trigger_changes": tchg, "backdrop": back, "trigger_look": look}
    kind = Counter(d["kind"] for d in live.values()).most_common(1)[0][0]
    for bp, d in live.items():   # an overlay spans the viewport (perception only sees its content's extent)
        if d["kind"] == "overlay":
            W, H = states[bp].get("size") or SIZES[bp]
            d["panel"] = [0, d["panel"][1], W, H - d["panel"][1]]
    panel = {bp: d["panel"] for bp, d in live.items()}
    frames = {}
    for bp, d in live.items():
        px, py = panel[bp][0], panel[bp][1]
        st = states[bp]
        frames[bp] = {"size": st.get("size"), "background": st.get("background", "#ffffff"),
                      "texts": [_shift(t, px, py) for t in d["appeared"]["texts"]],
                      "blocks": [_shift(b, px, py) for b in d["appeared"]["blocks"]]}
    # one shared, fluid panel when the breakpoints show the same kind with the same content; otherwise one panel per
    # breakpoint, each mounted only where it applies (lambda: overlay on mobile, drawer on tablet — compiled together,
    # perception noise at tablet scrambled the mobile row order). Panels exist only while open; the page stays one DOM.
    norm = lambda d: {" ".join(t["text"].split()).lower() for t in d["appeared"]["texts"]}
    sets = [norm(d) for d in live.values()]
    same = len({d["kind"] for d in live.values()}) == 1 and all(
        len(a & b) >= 0.8 * max(len(a), len(b), 1) for a in sets for b in sets)
    # components take className onto their root (the writer mounted <MenuPanelMobile className="md:hidden" />)
    comp = lambda n, body: (f"function {n}({{ className = \"\" }}) {{\n  return (\n    <div className={{`w-full ${{className}}`}}>\n"
                            f"{body}\n    </div>\n  );\n}}\n")
    if same:
        jsx = comp(name, compile_fluid({"breakpoints": frames}, auto_menu=False, fragment=True))
        components = {bp: name for bp in live}
    else:
        parts, components = [], {}
        for bp in live:
            n = name + bp.capitalize()
            # laid out at the breakpoint width closest to the panel's width (a 400 px drawer as a phone page, a
            # full-width tablet overlay as a tablet page); one frame → no md:/xl: variants
            fit = min(SIZES, key=lambda k: abs(SIZES[k][0] - panel[bp][2]))
            f = dict(frames[bp], size=list(SIZES[fit]))
            body = compile_fluid({"breakpoints": {fit: f}}, auto_menu=False, fragment=True)
            body = re.sub(r'(?<=[\s"])(?:md|xl):[^\s"]+\s?', "", body)   # one frame: no breakpoint variants
            parts.append(comp(n, body))
            components[bp] = n
        # one wrapper the writer mounts: each breakpoint's panel shown only at its breakpoint (mechanical knowledge —
        # the writer kept getting the per-breakpoint mounting wrong)
        show = {"mobile": "md:hidden", "tablet": "hidden md:block xl:hidden", "desktop": "hidden xl:block"}
        inner = "\n".join(f'      <div className="{show[bp]}"><{n} /></div>' for bp, n in components.items())
        parts.append(f"function {name}({{ className = \"\" }}) {{\n  return (\n    <div className={{`w-full ${{className}}`}}>\n"
                     f"{inner}\n    </div>\n  );\n}}\n")
        components = {bp: name for bp in components}
        jsx = "\n".join(parts)
    tname = name[:-len("Panel")] + "TriggerOpen" if name.endswith("Panel") else name + "TriggerOpen"
    tjsx = next((j for j in (compile_trigger_look(l, tname) for l in look.values()) if j), None)
    if tjsx:
        jsx = jsx + "\n" + tjsx
    return {"jsx": jsx, "kind": kind, "panel": panel, "diff": diffs, "trigger_changes": tchg, "backdrop": back,
            "trigger_look": look, "components": components, "trigger_component": tname if tjsx else None}


def compile_trigger_look(look: dict | None, name: str) -> str | None:
    """The trigger's open look (states.trigger_look, read from the images) as a component placed inside the trigger:
    shape "x" = two 2 px bars of the measured colour, rotated ±45°, crossing at the centre of the measured box.
    Measurable, so compiled — the writer only decides when to show it."""
    if not look or look.get("shape") != "x":
        return None
    x, y, w, h = look["box"]
    c = look["fill"]
    bar = round((w * w + h * h) ** 0.5)
    left = round(x + w / 2 - bar / 2)
    top = round(y + h / 2 - 1)
    b = f"absolute left-[{left}px] top-[{top}px] w-[{bar}px] h-[2px] bg-[{c}]"
    return (f"function {name}() {{\n  return (\n    <span aria-hidden=\"true\" className=\"absolute left-[{x}px] top-[{y}px] "
            f"w-[{w}px] h-[{h}px] pointer-events-none\">\n      <span className=\"{b.replace(f'left-[{left}px] top-[{top}px]', f'left-[{left - x}px] top-[{top - y}px]')} rotate-45\" />\n"
            f"      <span className=\"{b.replace(f'left-[{left}px] top-[{top}px]', f'left-[{left - x}px] top-[{top - y}px]')} -rotate-45\" />\n"
            f"    </span>\n  );\n}}\n")
