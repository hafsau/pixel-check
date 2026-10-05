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
    aria = (lambda i: f'role="tab" aria-selected={{{sel} === {i}}}') if plan.get("kind") == "tabs" else \
           (lambda i: f"aria-pressed={{{sel} === {i}}}")
    for i, _ in enumerate(members):
        code = _add_props(code, f"{name}{i}", f"onClick={{() => {setsel}({i})}} {aria(i)}")
    init = plan.get("initial") if isinstance(plan.get("initial"), int) else 0
    hooks = [f"const [{sel}, {setsel}] = useState({init});"]
    hooks += [f"const {up}_SLOT{k} = [{', '.join(json.dumps(mb['slots'][k], ensure_ascii=False) for mb in members)}];"
              for k in range(len(slots))]
    start = code.index("export default function App() {") + len("export default function App() {")
    code = code[:start] + "\n" + "\n".join("  " + h for h in hooks) + code[start:]
    return _imports(code, {"useState"})
