"""Gate B' group compiler (docs/INTERACTIONS.md): a verified interaction plan for sibling interactions → code.

Swap groups (tabs, billing toggles): the texts the example state swaps become slots — each slot's text is picked by
the selected member ({SLOT_k[sel]}); layout stays the compiled page's. Accordions: each member's answer is an element
cloned from the open answer's markup, mounted after its question's row while open. The plan (which elements are
members, what each shows) comes from Nemotron (orchestrator/planner.py); everything here is deterministic.
"""
from __future__ import annotations

import html
import re

# a text element: its inner content is text and responsive line breaks only (containers never match)
_ELEM = re.compile(r"<(?P<tag>[a-z][a-z0-9]*)\b(?P<attrs>[^<>]*?)>(?P<inner>(?:[^<]|<br\b[^<>]*/>)*?)</(?P=tag)>")


def _text_of(inner: str) -> str | None:
    """The visible text of an element's inner JSX (responsive <br>s and {" "} folded), or None when it holds markup
    other than line breaks (a container, not a text element)."""
    t = re.sub(r'\{" "\}', " ", inner)
    t = re.sub(r"<br\b[^<>]*/>", " ", t)
    if "<" in t or "{" in t:
        return None
    return " ".join(html.unescape(t).split())


def find_text(code: str, text: str) -> list[tuple[int, int]]:
    """Spans (start, end) of the inner content of every text element whose visible text is `text`, in order."""
    want = " ".join(text.split())
    return [(m.start("inner"), m.end("inner")) for m in _ELEM.finditer(code) if _text_of(m.group("inner")) == want]


def substitute(code: str, text: str, expr: str, nth: int = 0) -> str:
    """Replace the nth text element showing `text` with the JSX expression `expr` (its whole inner content)."""
    spans = find_text(code, text)
    if nth >= len(spans):
        raise KeyError(f"text element {text!r} #{nth} not in the page ({len(spans)} found)")
    s, e = spans[nth]
    return code[:s] + expr + code[e:]


class PlanError(ValueError):
    pass


def _add_props(code: str, trigger: str, props: str) -> str:
    m = re.search(r'<(\w+)[^<>]*data-trigger="%s"[^<>]*?(/?)>' % re.escape(trigger), code)
    if not m:
        raise PlanError(f'no element with data-trigger="{trigger}" in the page')
    tag = m.group(0)
    new = tag[:-2].rstrip() + f" {props} />" if m.group(2) == "/" else tag[:-1].rstrip() + f" {props}>"
    return code[:m.start()] + new + code[m.end():]


def compile_swap(page: str, plan: dict, name: str) -> str:
    """Swap group (plan kind tabs / toggle): members' triggers are marked data-trigger="<name><i>" in the page; the
    plan's slots (texts the selection replaces, `nth` occurrence among equal texts) take each member's slot texts."""
    import json
    from .writer import _imports
    members, slots = plan.get("members") or [], plan.get("slots") or []
    if len(members) < 2 or not slots:
        raise PlanError("a swap group needs 2+ members and 1+ slots")
    for mb in members:
        if len(mb.get("slots") or []) != len(slots):
            raise PlanError(f"member {mb.get('trigger')!r} has {len(mb.get('slots') or [])} slots, the plan has {len(slots)}")
    sel, setsel, up = f"{name}Sel", f"set{name[:1].upper()}{name[1:]}Sel", name.upper()
    code = page
    for k, sl in enumerate(slots):
        try:
            code = substitute(code, sl["text"], f"{{{up}_SLOT{k}[{sel}]}}", int(sl.get("nth") or 0))
        except KeyError as e:
            raise PlanError(str(e).strip('"')) from None
    init = plan.get("initial") if isinstance(plan.get("initial"), int) else 0
    code = _selected_look(code, name, len(members), init, sel)
    tabs = plan.get("kind") == "tabs"
    if tabs:
        code = _mark_parent(code, f'data-trigger="{name}0"', ' role="tablist"')
        code = _mark_container(code, [f"{{{up}_SLOT{k}[{sel}]}}" for k in range(len(slots))],
                               f' role="tabpanel" id="{name}-panel"')
    for i, _ in enumerate(members):
        a11y = (f'role="tab" aria-selected={{{sel} === {i}}} aria-controls="{name}-panel" tabIndex={{{sel} === {i} ? 0 : -1}} '
                f"onKeyDown={{{name}Key({i})}}") if tabs else f"aria-pressed={{{sel} === {i}}}"
        code = _add_props(code, f"{name}{i}", f"onClick={{() => {setsel}({i})}} {a11y}")
    hooks = [f"const [{sel}, {setsel}] = useState({init});"]
    if tabs:     # arrow keys move the selection and the focus (roving tabindex), Home / End jump
        n = len(members)
        hooks.append(f"const {name}Key = (i) => (e) => {{ const j = e.key === \"ArrowRight\" ? (i + 1) % {n} : "
                     f"e.key === \"ArrowLeft\" ? (i + {n - 1}) % {n} : e.key === \"Home\" ? 0 : e.key === \"End\" ? {n - 1} : -1; "
                     f"if (j < 0) return; e.preventDefault(); {setsel}(j); "
                     f"document.querySelector(`[data-trigger=\"{name}${{j}}\"]`)?.focus(); }};")
    hooks += [f"const {up}_SLOT{k} = [{', '.join(json.dumps(mb['slots'][k], ensure_ascii=False) for mb in members)}];"
              for k in range(len(slots))]
    start = code.index("export default function App() {") + len("export default function App() {")
    code = code[:start] + "\n" + "\n".join("  " + h for h in hooks) + code[start:]
    return _imports(code, {"useState"})


_VIS = re.compile(r"^(?:[\w-]+:)*(?:bg-|border|rounded|shadow)")
_TXT = re.compile(r"^(?:[\w-]+:)*(?:text-\[#|font-(?:thin|extralight|light|normal|medium|semibold|bold|extrabold|black)\b)")


def _opening(code: str, trigger: str) -> re.Match:
    m = re.search(r'<(\w+)[^<>]*data-trigger="%s"[^<>]*?/?>' % re.escape(trigger), code)
    if not m:
        raise PlanError(f'no element with data-trigger="{trigger}" in the page')
    return m


def _label(code: str, m: re.Match) -> re.Match | None:
    """The first text element directly inside a trigger that wraps its label (a pill around a <span>)."""
    close = code.find(f"</{m.group(1)}>", m.end())
    inner = code[m.end():close]
    k = re.search(r'<(?:span|p|a)\b[^<>]*className="([^"]*)"', inner)
    return k and (m.end() + k.start(1), m.end() + k.end(1), k.group(1))


def _selected_look(code: str, name: str, n: int, init: int, sel: str) -> str:
    """The selected member's look (pill background / border / radius / shadow, label colour and weight) follows the
    selection; layout classes stay. Read from the base frame's selected member and one unselected sibling."""
    def classes(i):
        m = _opening(code, f"{name}{i}")
        cm = re.search(r'className="([^"]*)"', m.group(0))
        lab = _label(code, m)
        toks = cm.group(1).split() if cm else []
        txt = [t for t in (lab[2].split() if lab else toks) if _TXT.match(t)]
        return [t for t in toks if _VIS.match(t)], txt
    other = next(i for i in range(n) if i != init)
    sel_vis, sel_txt = classes(init)
    uns_vis, uns_txt = classes(other)
    on, off = " ".join(sel_vis + sel_txt), " ".join(uns_vis + uns_txt)
    for i in range(n):
        m = _opening(code, f"{name}{i}")
        lab = _label(code, m)
        if lab:            # the label inherits the button's colour / weight
            code = code[:lab[0]] + " ".join(t for t in lab[2].split() if not _TXT.match(t)) + code[lab[1]:]
            m = _opening(code, f"{name}{i}")
        tag = m.group(0)
        cm = re.search(r'className="([^"]*)"', tag)
        static = " ".join(t for t in (cm.group(1).split() if cm else []) if not _VIS.match(t) and not _TXT.match(t))
        dyn = f'className={{`{static} ${{{sel} === {i} ? "{on}" : "{off}"}}`}}'
        new = tag.replace(cm.group(0), dyn) if cm else tag.replace(f'data-trigger="{name}{i}"', f'data-trigger="{name}{i}" {dyn}')
        code = code[:m.start()] + new + code[m.end():]
    return code


def _ind(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _mark_parent(code: str, needle: str, attrs: str) -> str:
    """Add attributes to the opening tag of the element enclosing the line containing `needle` (indentation)."""
    lines = code.split("\n")
    ti = next(i for i, l in enumerate(lines) if needle in l)
    pi = next((j for j in range(ti - 1, -1, -1) if lines[j].strip().startswith("<") and _ind(lines[j]) < _ind(lines[ti])), None)
    if pi is None:
        return code
    lines[pi] = re.sub(r"^(\s*<\w+)", lambda mm: mm.group(1) + attrs, lines[pi], count=1)
    return "\n".join(lines)


def _mark_container(code: str, needles: list[str], attrs: str) -> str:
    """Add attributes to the smallest element enclosing every line that contains one of `needles`."""
    lines = code.split("\n")
    hit = [i for i, l in enumerate(lines) if any(nd in l for nd in needles)]
    if not hit:
        return code
    lo, hi, m = hit[0], hit[-1], min(_ind(lines[i]) for i in hit)
    for j in range(lo - 1, -1, -1):
        l = lines[j]
        if not l.strip().startswith("<") or l.strip().startswith("</") or _ind(l) >= m:
            continue
        close = next((k for k in range(j + 1, len(lines)) if _ind(lines[k]) == _ind(l) and lines[k].strip().startswith("</")), None)
        if close is not None and close > hi:
            lines[j] = re.sub(r"^(\s*<\w+)", lambda mm: mm.group(1) + attrs, l, count=1)
            return "\n".join(lines)
        m = min(m, _ind(l))
    return code
