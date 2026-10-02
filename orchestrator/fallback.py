"""Deterministic interaction template (Gate B baseline, council Oct 2): the writer's sections filled straight from the
measured facts — no model. overlay / drawer: fixed layers at the measured boxes per breakpoint (backdrop behind the
panel where measured); inline: the panel in the page flow after the trigger's row with the measured gap. Nemotron's
interaction writer is measured against this, and it is the fallback when the writer fails."""
from __future__ import annotations

BPS = ("mobile", "tablet", "desktop")
PRE = {"mobile": "", "tablet": "md:", "desktop": "xl:"}


def _shown_only(bps: set) -> str:
    """Visibility classes: displayed exactly at the given breakpoints."""
    out, prev = [], True          # elements display by default
    for bp in BPS:
        on = bp in bps
        if on != prev or (bp == "mobile" and not on):
            out.append(f"{PRE[bp]}{'block' if on else 'hidden'}")
        prev = on
    return " ".join(out)


def _per_bp(values: dict, fmt) -> str:
    """Responsive classes: one per breakpoint where the value changes (mobile first)."""
    out, prev = [], None
    for bp in BPS:
        if bp in values and values[bp] != prev:
            out.append(PRE[bp] + fmt(values[bp]))
            prev = values[bp]
    return " ".join(out)


def template_sections(f: dict, name: str) -> dict:
    pid = f"{name}-panel"
    comp = f["panel_component"] if isinstance(f["panel_component"], str) else next(iter(f["panel_component"].values()))
    var, setv = f"{name}Open", f"set{name[:1].upper()}{name[1:]}Open"
    s = {"HOOKS": (f"const [{var}, {setv}] = useState(false);\n"
                   "useEffect(() => {\n"
                   f"  const onKey = (e) => {{ if (e.key === \"Escape\") {setv}(false); }};\n"
                   "  window.addEventListener(\"keydown\", onKey);\n"
                   "  return () => window.removeEventListener(\"keydown\", onKey);\n"
                   "}, []);"),
         "TRIGGER_PROPS": f'onClick={{() => {setv}((o) => !o)}} aria-expanded={{{var}}} aria-controls="{pid}"',
         "TRIGGER_OPEN": f"<{f['trigger_open_component']} />" if f.get("trigger_open_component") else ""}
    panel, kind = f["panel"], f["kind"]
    inline = {bp for bp in panel if kind.get(bp) == "inline"}
    fixed = {bp for bp in panel if bp not in inline}
    layers = []
    for bp in BPS:                 # backdrops first: painted behind the panel
        bd = (f.get("backdrop") or {}).get(bp)
        if bd and bp in fixed:
            x, y, w, h = bd["box"]
            layers.append(f'<div aria-hidden="true" className="fixed {_shown_only({bp})} left-[{x}px] top-[{y}px] '
                          f'w-[{w}px] h-[{h}px] bg-[{bd["color"]}]/[{round(bd["opacity"], 2)}]'
                          + (f' backdrop-blur-[{bd["blur"]}px]' if bd.get("blur") else "") + '" />')
    if fixed:
        bgs = f.get("background") or {}
        pos = " ".join(f"{PRE[bp]}left-[{panel[bp][0]}px] {PRE[bp]}top-[{panel[bp][1]}px] {PRE[bp]}w-[{panel[bp][2]}px] "
                       f"{PRE[bp]}h-[{panel[bp][3]}px] {PRE[bp]}bg-[{bgs.get(bp) or '#ffffff'}]"
                       for bp in BPS if bp in fixed)
        cls = " ".join(c for c in ("fixed z-50 overflow-y-auto", _shown_only(fixed) if fixed != set(BPS) else "", pos) if c)
        layers.append(f'<div id="{pid}" className="{cls}"><{comp} /></div>')
        s["OVERLAY"] = f"{{{var} && (<>\n" + "\n".join(layers) + "\n</>)}"
    if inline:
        gap = {bp: max(0, int((f.get("inline_gap") or {}).get(bp) or 0)) for bp in inline}
        vis = _shown_only(inline) if inline != set(BPS) else ""
        cls = " ".join(c for c in (_per_bp(gap, lambda v: f"mt-[{v}px]"), vis) if c)
        iid = pid if not fixed else f"{pid}-inline"
        s["INLINE"] = f'{{{var} && (<div id="{iid}" className="{cls}"><{comp} /></div>)}}'
    return s
