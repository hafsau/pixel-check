"""Code-writing / editing model calls. These models receive text only (spec + measurements), never image bytes."""
from __future__ import annotations

import re

from . import config
from .perceive import spec_for_prompt
from .tf_client import TFClient

SYSTEM = """You are an expert front-end engineer. You write ONE responsive React component, App.jsx, styled only
with Tailwind CSS v3 utility classes, that reproduces a design at three viewports from a precise text spec.

Hard rules (violations score 0):
- One file. `export default function App()`. Only import from "react" (if at all). No other imports.
- No <img>, <svg>, <canvas>, <video>, <iframe>, <object>, <picture>, <style>, <link>; no url(), data:, background images,
  dangerouslySetInnerHTML, fetch, matchMedia/innerWidth/resize listeners. Image placeholders are plain <div>s with a
  solid background colour. Icons are small solid <div>s or omitted.
- ONE DOM tree for all viewports. Do NOT build separate mobile/tablet/desktop copies toggled with hidden/md:block;
  re-flow the same elements with responsive classes (flex/grid direction, columns, widths, gap, text size, order).
  Hiding a genuinely desktop-only element (e.g. a side panel) with `hidden xl:block` is fine.
- position:absolute/fixed on at most a few decorative elements; layout uses flex/grid.
Breakpoints (Tailwind defaults, mobile-first): no prefix = mobile (390 px wide), `md:` = tablet (768 px), `xl:` = desktop
(1280 px). The 3 frames are 390×844, 768×1024, 1280×800 and are captured at the top of the page (no scrolling).
Fonts: `font-sans` is Inter (weights 400/500/600/700), `font-mono` is IBM Plex Mono. Use exact colours with arbitrary
values (bg-[#e50914], text-[#737373]) and exact sizes (text-[13px], w-[440px], mt-[18px]) when the spec gives them.
The page root must set the page background colour and min-h-screen.

Reading the spec:
- Each frame is the TOP of the page at that viewport, cropped to the viewport height. Content that appears in the taller
  frames but is "not in frame" in a shorter one is normally BELOW THE FOLD there: keep it in the DOM and make sure the
  content above it is tall enough (use the measured y positions / min-h) that it starts below that viewport's height.
- Never vertically centre a block that also contains below-the-fold content (it would push the top content off-screen).
  Place things with the measured y positions (top padding/margins) instead.
- Blocks are the measured boxes of real elements (an input, a button, a card, a panel). Build each as the element
  itself with that size and colour — do not add separate decorative overlay divs for them.
- Boxes are [x, y, width, height] px, exact to ±3 px unless marked ~ (estimated). Sizes are font sizes in px; `on` is the
  colour directly behind the text.
Layout contract (so the page can be corrected precisely by measurement afterwards):
- Vertical rhythm: stack blocks in normal flow and set each block's distance from the block above with margin-top
  per breakpoint (mt-[Npx] md:mt-[Npx] xl:mt-[Npx]), using the measured y gaps. Do NOT use vertical centring
  (items-center/justify-center on a column, place-content-center), mt-auto, space-y-*, or gap for vertical stacking.
- Horizontal: containers with max-w/w + mx-auto or padding for the content column; flex-row / grid grid-cols-N for
  things side by side; these may change per breakpoint (e.g. md:grid-cols-2).
- Put a stable wrapper element around every visual row (heading, input, button, footer…) so it can be moved as a unit.
- Give the page root `flow-root` (and min-h-screen + the page background): without it the first block's margin-top
  collapses through the root and the page background starts below the top of the viewport.
Output: first the complete App.jsx in one ```jsx code block, then at most 5 short bullet notes."""

CODE_RE = re.compile(r"```(?:jsx|tsx|javascript|js)?\s*\n(.*?)```", re.S)


def extract_code(text: str) -> str | None:
    blocks = CODE_RE.findall(text or "")
    if not blocks:
        return None
    code = max(blocks, key=len).strip()
    return code if "export default" in code else None


def write_initial(client: TFClient, spec: dict, *, thinking: str = config.CODER_THINKING,
                  temperature: float = config.CODER_TEMPERATURE, lessons: str = "", model: str | None = None) -> tuple[str | None, str]:
    user = "Build App.jsx for this design.\n\n" + spec_for_prompt(spec)
    if lessons:
        user += ("\n\nA previous attempt made these mistakes; avoid them (rules learned from measuring it):\n" + lessons)
    r = client.chat(model or config.MODEL_CODER, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                    step="code initial", thinking=thinking, max_tokens=16000, temperature=temperature, top_p=0.95)
    return extract_code(r.content), r.content


def repair(client: TFClient, code: str, error: str) -> tuple[str | None, str]:
    """One cheap fix-up call for build/parse errors (a broken file otherwise scores 0)."""
    user = ("This App.jsx fails to build:\n```\n" + error[:1500] + "\n```\n\n```jsx\n" + code + "\n```\n"
            "Fix ONLY the error; change nothing else. Return the complete App.jsx.")
    r = client.chat(config.MODEL_CODER, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                    step="code repair", thinking="off", max_tokens=16000, temperature=0.2)
    return extract_code(r.content), r.content


def revise(client: TFClient, spec: dict, code: str, strategy: str, feedback: str, *, step: str = "code revise") -> tuple[str | None, str]:
    user = ("Current App.jsx:\n```jsx\n" + code + "\n```\n\n"
            "Measured result against the design (render → design; every row is a real, measured error):\n" + feedback + "\n\n"
            "Fix ALL listed position, size and missing-element errors, prioritising the worst breakpoint, without breaking "
            "the breakpoints that are already right. Use this approach:\n" + strategy + "\n\n"
            "Design spec for reference:\n" + spec_for_prompt(spec) + "\n\n"
            "Change only what is needed for these fixes; keep every other line identical. Return the complete revised App.jsx.")
    r = client.chat(config.MODEL_CODER, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                    step=step, thinking=config.CODER_THINKING, max_tokens=16000, temperature=config.REVISE_TEMPERATURE, top_p=0.95)
    return extract_code(r.content), r.content


EDIT_SCHEMA = {
    "type": "object",
    "properties": {"edits": {"type": "array", "maxItems": 40, "items": {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "bp": {"type": "string", "enum": ["mobile", "tablet", "desktop", "all"]},
                       "add": {"type": "string"}, "remove": {"type": "string"}, "why": {"type": "string"}},
        "required": ["id", "bp", "add", "remove", "why"], "additionalProperties": False}}},
    "required": ["edits"], "additionalProperties": False,
}

EDIT_SYSTEM = """You fix a responsive React + Tailwind page by editing Tailwind classes ONLY — you cannot move, add or
delete elements. Every element carries data-pc="N"; refer to it by that id.
Each edit targets ONE breakpoint via "bp": "mobile" (390 px), "tablet" (768 px) or "desktop" (1280 px). Give plain,
UNPREFIXED classes (e.g. "mt-[40px] text-[32px]"); the tool adds the right md:/xl: prefix, replaces the old value of
the same property at that breakpoint, and automatically pins the other breakpoints to their current values — so a
tablet fix cannot break mobile or desktop. Use "bp": "all" only for a change that must apply everywhere.
Elements rendered inside .map() share one id: an edit changes all copies. You rarely need "remove" (adding a class
already replaces the old value of that property at that breakpoint); leave it "".
What to fix — ONLY the listed measurements, nothing else (no colour, rounding or font changes unless a listed error asks):
- STRUCTURE notes: change the PARENT container of those items (find it in the code), e.g. "grid grid-cols-2 gap-x-[..]"
  or "flex-row"/"flex-col" at that breakpoint. Do not fake a grid with per-item margins.
- ROWS "step … (Δ +Npx)": the row's top must move by Δ relative to the row above. Change the space above that row's
  FIRST element (its margin-top, or the previous element's margin-bottom / a spacer's height) by exactly Δ, starting from
  its CURRENT value at that breakpoint (read it from the classes). Rows below move with it — do not also move them.
- "x … (Δ)": change the horizontal offset of that row/container (padding/margin/width of its container).
- "font a→b px" / "width a→b (wrapping)": set text-[b px] or the container width.
Reply with JSON only."""


def class_edits(client: TFClient, tagged_code: str, feedback: str, strategy: str, *, model: str | None = None,
                temperature: float = 0.4) -> tuple[list[dict], str]:
    user = ("Page (elements tagged with data-pc ids):\n```jsx\n" + tagged_code + "\n```\n\n"
            "Measured errors (render → design):\n" + feedback + "\n\nFocus: " + strategy +
            "\n\nReturn JSON {\"edits\": [{\"id\": N, \"bp\": \"tablet\", \"add\": \"classes\", \"remove\": \"\", \"why\": \"...\"}]}"
            " that fixes as many measured errors as possible without breaking breakpoints that are already right.")
    r = client.chat(model or config.MODEL_EDITOR, [{"role": "system", "content": EDIT_SYSTEM}, {"role": "user", "content": user}],
                    step="class edits", schema=EDIT_SCHEMA, thinking="off", max_tokens=4000, temperature=temperature)
    d = r.data if isinstance(r.data, dict) else None
    return (d or {}).get("edits") or [], r.content


TOOLS_SCHEMA = {
    "type": "object",
    "properties": {"calls": {"type": "array", "maxItems": 12, "items": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["set_layout", "wrap", "move", "insert", "remove", "set_tag"]},
            "id": {"type": "integer"}, "ids": {"type": "array", "items": {"type": "integer"}},
            "bp": {"type": "string", "enum": ["mobile", "tablet", "desktop", "all"]},
            "layout": {"type": "string", "enum": ["grid", "flex-row", "flex-col", "block"]},
            "cols": {"type": "integer"}, "gap_x": {"type": "integer"}, "gap_y": {"type": "integer"},
            "before": {"type": "integer"}, "after": {"type": "integer"}, "into": {"type": "integer"},
            "jsx": {"type": "string"}, "classes": {"type": "string"}, "tag": {"type": "string"},
            "why": {"type": "string"}},
        "required": ["op", "why"]}}},
    "required": ["calls"],
}

TOOLS_SYSTEM = """You are the structural engineer in a responsive design-to-code agent. A React + Tailwind page already
matches its design closely; what remains are STRUCTURAL problems that measurements found: elements arranged differently
(stacked vs side by side, grids), missing visual elements (divider rules, icon boxes, borders), extra elements, wrong
semantics. Fix them with TOOL CALLS — you never rewrite the file. Elements carry data-pc="N" ids.

Tools (JSON objects in "calls"):
- set_layout {id, bp, layout: grid|flex-row|flex-col|block, cols?, gap_x?, gap_y?}: make container N lay out its children
  that way at breakpoint bp (mobile 390 / tablet 768 = md: / desktop 1280 = xl:; "all" for every size).
- wrap {ids: [sibling ids, in order], classes}: put consecutive siblings into a new <div className=classes> (e.g. to
  group items that the design shows as a grid: classes "grid grid-cols-2 gap-x-[24px] gap-y-[16px]", with md:/xl: prefixes
  if only some breakpoints need it).
- move {id, before|after: id}: reorder.
- insert {after|before|into: id, jsx}: add TEXT-FREE elements only (e.g. '<div className="h-px w-full bg-[#1a1a1a]" />'
  for a divider, '<div className="h-4 w-4 bg-[#d4d4d8]" />' for an icon box). Any text in jsx is rejected.
- remove {id}: delete an element the design doesn't have.
- set_tag {id, tag}: semantic tag (button, a, h1, nav, header, footer…), no visual change.
Rules: only address the listed STRUCTURE / MISSING / EXTRA findings; use exact colours and px from them; prefer the fewest
calls; every call needs a short "why". Reply with JSON only: {"calls": [...]}"""


def structural_calls(client: TFClient, tagged_code: str, findings: str, *, model: str | None = None,
                     temperature: float = 0.3) -> tuple[list[dict], str]:
    user = ("Page (elements tagged with data-pc ids):\n```jsx\n" + tagged_code + "\n```\n\nMeasured findings:\n" + findings +
            "\n\nReturn the tool calls as JSON {\"calls\": [...]}.")
    # No json_schema here: with this schema (many optional fields) Token Factory's constrained decoding made Nemotron
    # return {"calls": []} every time (7 tokens); free JSON gives real calls, normalised below.
    r = client.chat(model or config.MODEL_EDITOR, [{"role": "system", "content": TOOLS_SYSTEM}, {"role": "user", "content": user}],
                    step="structural tools", thinking="off", max_tokens=4000, temperature=temperature)
    from .tf_client import parse_json
    d = parse_json(r.content)
    calls = d.get("calls") if isinstance(d, dict) else d if isinstance(d, list) else []
    return [c for c in (normalise_call(x) for x in calls or []) if c], r.content


OPS = ("set_layout", "wrap", "move", "insert", "remove", "set_tag")


def normalise_call(c) -> dict | None:
    """Accept {"op": "wrap", ...} and {"wrap": {...}, "why": ...} shapes."""
    if not isinstance(c, dict):
        return None
    if c.get("op") in OPS:
        return c
    for op in OPS:
        if isinstance(c.get(op), dict):
            return {"op": op, **c[op], "why": c.get("why", "")}
    return None
