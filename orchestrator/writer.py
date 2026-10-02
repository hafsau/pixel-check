"""Stage 4 (docs/INTERACTIONS.md): the interaction writer.

Nemotron writes the behaviour in four sections (prompt in WRITER_SYSTEM):
  ### HOOKS          React state + effects inside App (e.g. useState for open, an Escape key listener)
  ### TRIGGER_PROPS  props added to the trigger element (onClick, aria-expanded, aria-controls, aria-label)
  ### TRIGGER_OPEN   optional: what the trigger shows while open (hamburger → X), JSX
  ### OVERLAY        JSX placed at the end of the page that mounts the compiled panel component when open
assemble() places them deterministically into the compiled page; everything else stays byte-identical, so the
static layout's score cannot regress. Verified by the generated acceptance tests (orchestrator/acceptance.py).
"""
from __future__ import annotations

import re

SECTIONS = ("HOOKS", "TRIGGER_PROPS", "TRIGGER_OPEN", "OVERLAY")
REQUIRED = ("HOOKS", "TRIGGER_PROPS", "OVERLAY")
HOOK_NAMES = ("useState", "useEffect", "useRef", "useCallback")


class WriterFormatError(ValueError):
    pass


def parse_sections(text: str) -> dict:
    parts = re.split(r"^\s*#{2,4}\s*(HOOKS|TRIGGER_PROPS|TRIGGER_OPEN|OVERLAY)\s*$", text or "", flags=re.M)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        body = parts[i + 1]
        fence = re.search(r"```[a-zA-Z]*\n(.*?)```", body, re.S)
        body = fence.group(1) if fence else body
        out[parts[i]] = body.strip()
    missing = [s for s in REQUIRED if not out.get(s)]
    if missing:
        raise WriterFormatError(f"missing section(s): {', '.join(missing)}")
    return out


def _imports(code: str, used: set[str]) -> str:
    m = re.match(r'import \{([^}]*)\} from "react";\n*', code)
    have = {x.strip() for x in m.group(1).split(",")} if m else set()
    names = [h for h in HOOK_NAMES if h in used or h in have]
    if not names:
        return code
    line = f'import {{ {", ".join(names)} }} from "react";\n\n'
    return line + (code[m.end():] if m else code)


def assemble(base: str, panel_jsx: str | None, sections: dict, name: str) -> str:
    hooks, props = sections["HOOKS"], sections["TRIGGER_PROPS"]
    open_look, overlay = sections.get("TRIGGER_OPEN", ""), sections["OVERLAY"]
    code = base
    m = re.search(r'<(\w+)[^<>]*data-trigger="%s"[^<>]*?(/?)>' % re.escape(name), code)
    if not m:
        raise WriterFormatError(f'no element with data-trigger="{name}" in the page')
    tag, selfclose = m.group(1), m.group(2) == "/"
    opening = m.group(0)
    if open_look and 'className="' in opening and not re.search(r'className="[^"]*\brelative\b', opening):
        opening_rel = opening.replace('className="', 'className="relative ', 1)   # positioning context for the open look
        code = code[:m.start()] + opening_rel + code[m.end():]
        m = re.search(re.escape(opening_rel), code)
        opening = opening_rel
    new_open = opening[:-2].rstrip() + f" {props} />" if selfclose else opening[:-1].rstrip() + f" {props}>"
    if open_look:
        sv = re.search(r"const\s*\[\s*(\w+)\s*,\s*set\w+\s*\]\s*=\s*useState", hooks)
        if not sv:
            raise WriterFormatError("TRIGGER_OPEN needs a state variable declared in HOOKS (const [open, setOpen] = useState(...))")
        var = sv.group(1)
        if selfclose:
            new_open = new_open[:-2].rstrip() + f">{{{var} ? (<>{open_look}</>) : null}}</{tag}>"
            code = code[:m.start()] + new_open + code[m.end():]
        else:
            close = code.find(f"</{tag}>", m.end())
            if close < 0:
                raise WriterFormatError(f"trigger <{tag}> is not closed")
            children = code[m.end():close]
            pad = re.search(r"\n(\s*)$", code[:m.start()])
            ind = (pad.group(1) if pad else "") + "  "
            body = f"\n{ind}{{{var} ? (<>{open_look}</>) : (<>{children.rstrip()}\n{ind}</>)}}\n{ind[:-2]}"
            code = code[:m.start()] + new_open + body + code[close:]
    else:
        code = code[:m.start()] + new_open + code[m.end():]
    if panel_jsx and panel_jsx.split("(")[0] not in code:
        code = code.replace("export default function App() {", panel_jsx.rstrip() + "\n\nexport default function App() {", 1)
    start = code.index("export default function App() {") + len("export default function App() {")
    code = code[:start] + "\n" + "\n".join("  " + l if l.strip() else l for l in hooks.splitlines()) + code[start:]
    end = code.rindex("\n    </div>\n  );\n}")
    code = code[:end] + "\n" + "\n".join("      " + l for l in overlay.splitlines()) + code[end:]
    used = {h for h in HOOK_NAMES if re.search(r"\b%s\b" % h, hooks + props + overlay + open_look)}
    return _imports(code, used)


WRITER_SYSTEM = """You write the interaction code for a React + Tailwind page that was compiled from design frames.
The static page already exists; you add ONLY the behaviour that opens and closes one panel. Breakpoints are mobile
(< 768 px, no prefix), tablet (md:, 768–1279 px) and desktop (xl:, ≥ 1280 px).

Rules:
- React hooks only (useState, useEffect); no imports, no libraries, no <svg>/<img>/<canvas>, no url(), no inline style.
- Tailwind classes only (arbitrary values like top-[100px] or bg-[#0b0b0b]/[0.9] are fine).
- Clicking the trigger toggles the panel; aria-expanded on the trigger reflects the state; aria-controls points at
  the panel's id; pressing Escape closes it; the trigger stays a <button> (keyboard Enter already clicks it).
- When open, mount the given panel component inside a `fixed` container positioned EXACTLY at the measured panel box
  for each breakpoint (use responsive prefixes when the box or kind differs between breakpoints), with the measured
  background colour, and `overflow-y-auto`.
- If a backdrop is measured for a breakpoint, render it when open as a separate fixed layer BEHIND the panel at the
  measured box with the measured colour and opacity, only at that breakpoint (hidden elsewhere).
- If the trigger's open look is measured (box relative to the trigger, colour, shape), draw it with plain divs —
  shape "x" = two thin (2 px) bars of the measured colour rotated ±45°, centred in that box (the trigger is a
  positioning context, so absolute children are placed inside it); otherwise leave TRIGGER_OPEN empty.

Reply with exactly these sections and nothing else:
### HOOKS
(statements placed at the top of the App component)
### TRIGGER_PROPS
(JSX props added to the trigger element)
### TRIGGER_OPEN
(JSX shown inside the trigger while open, or empty)
### OVERLAY
(one JSX expression placed at the end of the page, e.g. {open && (<>...</>)})"""


def _facts_text(f: dict, name: str) -> str:
    rows = [f"Trigger element (opening tag): {f['trigger_tag']}",
            f'Trigger selector: [data-trigger="{name}"]',
            ("Panel component to mount (already defined): " + (
                f"<{f['panel_component']} />" if isinstance(f["panel_component"], str) else
                "one per breakpoint, each shown only at its breakpoint — " +
                ", ".join(f"{bp}: <{n} />" for bp, n in f["panel_component"].items()))),
            f"Trigger hidden at (the design has no panel there): {', '.join(f.get('hidden_at') or []) or 'none'}"]
    if f.get("trigger_open_component"):
        rows.append(f"Trigger open look (compiled, already defined): <{f['trigger_open_component']} /> — use it as "
                    "TRIGGER_OPEN as is")
    for bp in ("mobile", "tablet", "desktop"):
        if bp not in (f.get("panel") or {}):
            continue
        bd = (f.get("backdrop") or {}).get(bp)
        rows.append(f"- {bp}: kind {f['kind'][bp]}, panel box [x, y, w, h] = {f['panel'][bp]}, background "
                    f"{(f.get('background') or {}).get(bp)}, backdrop "
                    + (f"colour {bd['color']} opacity {bd['opacity']} box {bd['box']}" if bd else "none")
                    + (f", trigger open look (boxes relative to the trigger) {f['trigger_open'][bp]}"
                       if (f.get("trigger_open") or {}).get(bp) else ""))
    return "\n".join(rows)


def write_interaction(client, facts: dict, name: str, *, previous: dict | None = None,
                      failures: list[str] | None = None, model: str | None = None) -> tuple[dict, str]:
    """Nemotron writes the four sections from measured facts. previous + failures: revise after failing tests.
    One retry with a format reminder; a second malformed reply raises WriterFormatError."""
    from . import config
    user = "Measured facts:\n" + _facts_text(facts, name)
    if previous:
        user += ("\n\nYour previous code:\n" + "\n".join(f"### {k}\n{v}" for k, v in previous.items())
                 + "\n\nThe generated tests ran in the sandbox and FAILED:\n- " + "\n- ".join(failures or [])
                 + "\n\nFix the code so every test passes. Reply with all four sections again.")
    msgs = [{"role": "system", "content": WRITER_SYSTEM}, {"role": "user", "content": user}]
    last = ""
    for attempt in range(2):
        # revisions explore (identical code came back three times at 0.2 with the same failures)
        think = config.WRITER_REVISION_THINKING if previous else "off"
        r = client.chat(model or config.MODEL_WRITER, msgs, step="interaction writer", thinking=think,
                        max_tokens=3000 if think == "off" else 6000, temperature=0.6 if previous else 0.2)
        last = r.content or ""
        try:
            return parse_sections(last), last
        except WriterFormatError as e:
            msgs = msgs + [{"role": "assistant", "content": last},
                           {"role": "user", "content": f"Your reply was not in the required format ({e}). Reply with "
                                                       "exactly: ### HOOKS, ### TRIGGER_PROPS, ### TRIGGER_OPEN, ### OVERLAY."}]
    raise WriterFormatError(f"writer reply unparseable twice: {last[:200]!r}")
