"""Gate B' interaction planner (docs/INTERACTIONS.md): Nemotron generalises ONE example state to the sibling
interactions of a page and reads the designer's notes for what each sibling shows — information the frames do not
contain. Input: an outline of the base frame (texts with ids), the example (trigger, texts that appeared /
disappeared), the notes verbatim. Output: a JSON plan referring to outline ids, validated before any code exists;
code is compiled deterministically from it (orchestrator/groups.py).
"""
from __future__ import annotations

import json
import re

KINDS = ("tabs", "toggle", "accordion")

PLAN_SYSTEM = """You plan the interactions of one group of sibling controls on a web page compiled from design frames.
You get: an OUTLINE of the page's texts (id, text, role, box [x, y, w, h], style), ONE EXAMPLE (the designer clicked
one control; the texts that disappeared and appeared), and the designer's NOTES. The example shows how ONE member of
the group behaves; find the other members (controls of the same kind and style, usually in one row or column) and
say what each one shows, using the notes for content the frames do not show. Never invent content: copy text from
the outline (for the member shown in the base frame) or from the example (for the example member) or from the notes.

Kinds: "tabs" (one selected at a time; the selection swaps texts in place), "toggle" (2 options swapping values in
place, e.g. billing period), "accordion" (each member opens its own answer below it; "exclusive" if only one can be
open). For tabs / toggle, "slots" = outline ids of the texts the selection replaces (in the base frame, in reading
order), and each member's "content" lists its text for each slot, same order. For an accordion, "slots" is [] and
"content" is the member's answer paragraphs.

Reply with JSON only:
{"kind": "tabs" | "toggle" | "accordion", "exclusive": true | false,
 "initial": <index in members of the member selected/open in the base frame, or null>,
 "slots": [<outline id>, ...],
 "members": [{"trigger": <outline id of the member's control>, "content": ["...", ...]}, ...]}"""


class PlanError(ValueError):
    pass


def _norm(s: str) -> str:
    return " ".join((s or "").split()).lower()


def build_outline(frame: dict, trigger_box=None) -> list[dict]:
    """The base frame's texts in reading order with ids; the one under the example trigger is marked."""
    texts = sorted([t for t in frame.get("texts", []) if t.get("box") and (t.get("text") or "").strip()],
                   key=lambda t: (t["box"][1], t["box"][0]))
    out = []
    for i, t in enumerate(texts):
        x, y, w, h = t["box"]
        ex = bool(trigger_box) and (trigger_box[0] <= x + w / 2 <= trigger_box[0] + trigger_box[2] and
                                    trigger_box[1] <= y + h / 2 <= trigger_box[1] + trigger_box[3])
        out.append({"id": i, "text": " ".join(t["text"].split()), "role": t.get("role") or "body", "box": list(t["box"]),
                    "style": f"{round(t.get('size_px') or 0)}px {t.get('weight') or 400} {t.get('color') or '?'}",
                    "example_trigger": ex})
    return out


def _user_prompt(outline: list[dict], example: dict, notes: str) -> str:
    rows = [f"[{o['id']}] \"{o['text']}\" role={o['role']} box={o['box']} style={o['style']}"
            + ("  <- EXAMPLE TRIGGER" if o["example_trigger"] else "") for o in outline]
    return ("OUTLINE (base frame):\n" + "\n".join(rows)
            + "\n\nEXAMPLE: the designer clicked the EXAMPLE TRIGGER.\nDisappeared: " + json.dumps(example.get("disappeared") or [])
            + "\nAppeared: " + json.dumps(example.get("appeared") or [])
            + "\n\nNOTES:\n" + (notes or "(none)"))


def _parse(text: str) -> dict:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text or "", re.S)
    body = fence.group(1) if fence else None
    if body is None:
        a, b = (text or "").find("{"), (text or "").rfind("}")
        body = text[a:b + 1] if a >= 0 and b > a else ""
    try:
        v = json.loads(body)
    except json.JSONDecodeError as e:
        raise PlanError(f"reply is not JSON ({e.msg})") from None
    if not isinstance(v, dict):
        raise PlanError("reply is not a JSON object")
    return v


def validate(plan: dict, outline: list[dict], example: dict) -> list[str]:
    errs = []
    ids = {o["id"]: o for o in outline}
    kind = plan.get("kind")
    if kind not in KINDS:
        errs.append(f"kind must be one of {', '.join(KINDS)} (got {kind!r})")
    members = plan.get("members") or []
    if len(members) < 2:
        errs.append("a group needs 2+ members")
    trig = [m.get("trigger") for m in members]
    for t in trig:
        if t not in ids:
            errs.append(f"member trigger: no outline id {t}")
    if len(set(trig)) != len(trig):
        errs.append("a trigger id is used twice")
    ex_ids = [o["id"] for o in outline if o["example_trigger"]]
    if ex_ids and not set(ex_ids) & set(trig):
        errs.append(f"the example trigger (id {ex_ids[0]}) must be a member")
    slots = plan.get("slots") or []
    if kind in ("tabs", "toggle"):
        if not slots:
            errs.append("tabs / toggle need slots")
        for s in slots:
            if s not in ids:
                errs.append(f"slot: no outline id {s}")
        for m in members:
            if len(m.get("content") or []) != len(slots):
                errs.append(f"member {m.get('trigger')}: content has {len(m.get('content') or [])} entries, slots {len(slots)}")
        if not errs:
            appeared = {_norm(t) for t in example.get("appeared") or []}
            for m in members:
                if m["trigger"] in ex_ids and not {_norm(c) for c in m["content"]} <= appeared | {_norm(ids[s]["text"]) for s in slots}:
                    errs.append("the example member's content must be the example's appeared texts")
            init = plan.get("initial")
            if isinstance(init, int) and 0 <= init < len(members):
                if [_norm(c) for c in members[init]["content"]] != [_norm(ids[s]["text"]) for s in slots]:
                    errs.append("the initial member's content must be the base frame's slot texts")
    elif kind == "accordion":
        for m in members:
            if not m.get("content"):
                errs.append(f"member {m.get('trigger')}: content (answer) is empty")
    return errs


def plan_group(client, base_frame: dict, example: dict, notes: str, model: str | None = None) -> tuple[dict, dict]:
    """→ (validated plan, {"revisions", "usd", "raw"}). One revision with the validation errors; then PlanError."""
    from . import config
    outline = build_outline(base_frame, example.get("trigger"))
    msgs = [{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": _user_prompt(outline, example, notes)}]
    usd, raw = 0.0, []
    for attempt in range(2):
        r = client.chat(model or config.MODEL_WRITER, msgs, step="interaction planner", thinking="off",
                        max_tokens=3000, temperature=0.2 if attempt == 0 else 0.5)
        usd += getattr(r, "usd", 0) or 0
        raw.append(r.content or "")
        try:
            plan = _parse(r.content)
            errs = validate(plan, outline, example)
        except PlanError as e:
            plan, errs = None, [str(e)]
        if not errs:
            return plan, {"revisions": attempt, "usd": usd, "raw": raw, "outline": outline}
        msgs = msgs + [{"role": "assistant", "content": r.content or ""},
                       {"role": "user", "content": "The plan is invalid:\n- " + "\n- ".join(errs) + "\nReply with the corrected JSON only."}]
    raise PlanError("plan invalid after one revision: " + "; ".join(errs))


def to_swap_plan(plan: dict, outline: list[dict]) -> dict:
    """Outline ids → texts + occurrence index among equal texts (reading order), as groups.compile_swap takes."""
    ids = {o["id"]: o for o in outline}

    def nth(i):
        t = _norm(ids[i]["text"])
        return sum(1 for o in outline if o["id"] < i and _norm(o["text"]) == t)
    return {"kind": plan["kind"], "initial": plan.get("initial"),
            "slots": [{"text": ids[s]["text"], "nth": nth(s)} for s in plan.get("slots") or []],
            "members": [{"trigger": ids[m["trigger"]]["text"], "trigger_id": m["trigger"], "slots": list(m["content"])}
                        for m in plan["members"]]}
