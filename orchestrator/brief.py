"""Fix brief (Oct 20): what to do next, from a check's measurements — for people who build with AI tools.

1. facts(): numbered plain sentences (F1…Fn) from check.json — the diagnostics beside the score (orchestrator/
   diagnose.py), warnings (platform badges), width-sweep failures, and for an audit the text a phone loses. Text only:
   no image ever enters the brief.
2. Nemotron 3 Super (config.MODEL_BRIEF, thinking off) writes a short summary and a message to paste into the AI
   builder (or Tailwind hints for an App.jsx), each item citing the facts it relies on.
3. verify(): a check outside the model keeps an item only if it cites known facts, every number it gives (px, %) is
   one of its facts' numbers (within tolerance) and any UI text it quotes is in those facts. Everything else is
   dropped and counted.
4. If Nemotron fails or nothing survives, template() writes the brief from the facts (it passes the same verifier).
The score is never touched.
"""
from __future__ import annotations

import re

from . import config
from .tf_client import parse_json

MAX_SUMMARY, MAX_FIX, MAX_CHARS = 5, 8, 320
BPS = ("mobile", "tablet", "desktop")
_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(px|%)")
_QUOTE = re.compile(r"[“\"]([^”\"]{2,80})[”\"]")
_SQUOTE = re.compile(r"(?:^|[\s(])[‘']([^'’]{2,80}?)[’'](?=[\s,.;:)!?]|$)")   # 'x', not the ' in don't


def _q(s: str) -> str:
    return f"“{s}”"


def _nums(text: str) -> list[float]:
    return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text or "")]


# ------------------------------------------------------------------------------------------------ facts

def _warning_sentence(w: str) -> str:
    """'mobile: the X badge covers "Y" (a platform badge, not your layout)' → 'On mobile, the X badge covers "Y".'"""
    w = re.sub(r"\s*\(a platform badge, not your layout\)\s*$", "", w.strip())
    m = re.match(r"^(\d+ px|mobile|tablet|desktop):\s*(.+)$", w)
    if m:
        where = f"At {m.group(1)}" if m.group(1)[0].isdigit() else f"On {m.group(1)}"
        w = f"{where}, {m.group(2)}"
    return w if w.endswith(".") else w + "."


def facts(bundle: dict) -> list[dict]:
    """Numbered facts, most useful first: fonts, text size, spacing drift, text, warnings, widths, lost text."""
    rep = (bundle or {}).get("report") or {}
    diag = (bundle or {}).get("diagnostics") or {}
    out: list[dict] = []

    def add(kind, bp, text, nums=(), quote=None):
        out.append({"kind": kind, "bp": bp, "text": text, "nums": [round(n) for n in nums],
                    **({"quote": quote} if quote else {})})

    fonts = {(d.get("font") or {}).get("build"): d["font"] for d in diag.values() if isinstance(d, dict) and d.get("font")}
    for f in fonts.values():
        add("font", None, f"The build uses the {f['build']} font; the design uses {f['design']}.")
    for bp in BPS:
        d = diag.get(bp)
        if not isinstance(d, dict):
            continue
        r = d.get("text_size")
        if isinstance(r, (int, float)) and r > 0 and abs(1 - r) >= 0.08:
            pct, fix = round(abs(1 - r) * 100), round(abs(1 / r - 1) * 100)
            add("text_size", bp, f"On {bp}, text is about {pct}% {'smaller' if r < 1 else 'larger'} than in the design "
                                 f"(it needs to be about {fix}% {'larger' if r < 1 else 'smaller'}).", (pct, fix))
        dr = d.get("drift") or {}
        scale = dr.get("scale")
        last = next((b.get("dy") for b in reversed(dr.get("bands") or []) if isinstance(b, dict) and b.get("dy") is not None), None)
        if isinstance(scale, (int, float)) and scale > 0 and last is not None and abs(1 - scale) >= 0.05 and abs(last) >= 12:
            pct, fix = round(abs(1 - scale) * 100), round(abs(1 / scale - 1) * 100)
            tight = scale < 1
            add("drift", bp, f"On {bp}, vertical spacing is about {pct}% {'tighter' if tight else 'looser'} than in the design "
                             f"(it needs to {'grow' if tight else 'shrink'} about {fix}%): by the bottom of the screen, content "
                             f"sits {abs(last)} px {'higher' if last < 0 else 'lower'}.", (pct, fix, abs(last)))
    # any measurable drift (≥ 1.5 %) explains text that sits higher / lower on that size, even when it is too small to act on
    explained = {bp for bp in BPS if isinstance(diag.get(bp), dict) and isinstance((diag[bp].get("drift") or {}).get("scale"), (int, float))
                 and abs(1 - diag[bp]["drift"]["scale"]) >= 0.015}
    for bp in BPS:
        d = diag.get(bp)
        for t in (d.get("text") if isinstance(d, dict) else None) or []:
            q, st = t.get("text"), t.get("status")
            if not q:
                continue
            if st == "moved" and t.get("dy") is not None:
                add("moved", bp, f"On {bp}, {_q(q)} sits {abs(t['dy'])} px {'higher' if t['dy'] < 0 else 'lower'} than in the design.",
                    (abs(t["dy"]),), q)
            elif st == "below":
                add("below", bp, f"On {bp}, {_q(q)} is pushed below the first screen.", (), q)
            if st in ("moved", "below") and bp in explained:
                out[-1]["explained"] = True
            elif st == "missing":
                add("missing", bp, f"On {bp}, {_q(q)} is in the design but not in the build.", (), q)
            elif st == "unreadable":
                add("unreadable", bp, f"On {bp}, {_q(q)} is in place but covered or too faint to read.", (), q)
    for w in rep.get("warnings") or []:
        if isinstance(w, str) and w.strip():
            m = re.match(r"^(mobile|tablet|desktop):", w.strip())
            add("warning", m.group(1) if m else None, _warning_sentence(w), _nums(w))
            if "badge" in w.lower():
                out[-1]["badge"] = True
    widths = (rep.get("fluidity") or {}).get("widths") or {}
    for key, row in sorted(widths.items(), key=lambda kv: (not kv[0].isdigit(), int(kv[0]) if kv[0].isdigit() else 0)):
        if not isinstance(row, dict):
            continue
        where = f"At {key} px" if key.isdigit() else f"On {key}"
        nums = (int(key),) if key.isdigit() else ()
        size = key if key in BPS else None
        if (row.get("overflow") or 0) > 0:
            add("width", size, f"{where}, the page scrolls sideways by {row['overflow']} px.", nums + (row["overflow"],))
        elif (row.get("overlaps") or 0) > 0:
            add("width", size, f"{where}, {row['overlaps']} elements overlap.", nums)
        elif row.get("ok") is False:
            add("width", size, f"{where}, the layout fails the width check.", nums)
    for bp, texts in ((rep.get("vanished") or {}).items()):
        texts = [t for t in texts or [] if isinstance(t, str) and t.strip()][:8]
        if texts:
            add("vanished", bp, f"On {bp}, text shown on larger screens is gone: {', '.join(_q(t) for t in texts)}.")
    for i, f in enumerate(out, 1):
        f["id"] = f"F{i}"
    return [{"id": f.pop("id"), **f} for f in out]   # drift under 5 % is left out: too small to act on (council)


# ------------------------------------------------------------------------------------------------ verifier

_TOKEN = re.compile(r"(?<![\w.#])(\d+(?:\.\d+)?)\s*(px|%|percent|rem|em|pt|vh|vw)?(?![\w])")
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_SIZE = {"mobile": "mobile", "phone": "mobile", "phones": "mobile", "tablet": "tablet", "tablets": "tablet", "desktop": "desktop"}
_SCOPE = re.compile(r"\b(?:at|across|on|for) (?:all|every) (?:screen )?(?:sizes|screens|breakpoints|widths)\b|\beverywhere\b", re.I)
_OVERCLAIM = re.compile(r"\b(?:inaccessible|unusable|broken|critical|key|all|any|every|other|others|entire|whole|completely|"
                        r"severely|totally|causing|causes|because|making it|leading to|leads to|results? in|resulting in|"
                        r"violat\w*)\b", re.I)                                  # adjectives, scope and causal words (council)
_POSITIONING = re.compile(r"\b(?:absolute|absolutely|fixed|position\w*|z-index|translate\w*)\b|\b(?:top|left|right|bottom)\s*:", re.I)


def _unquoted(text: str) -> str:
    return _SQUOTE.sub(" ", _QUOTE.sub(" ", text))


def _tokens(text: str) -> list[tuple[float, str | None]]:
    return [(float(v), {"percent": "%"}.get(u, u) if u else None) for v, u in _TOKEN.findall(_unquoted(text))]


NUMBER, QUOTE, SIZE, OVERCLAIM = ("a number the measurements do not contain", "quotes text the measurements do not contain",
                                  "names a size its facts do not cover", "says more than the measurements (overclaim or cause)")


def _why(text: str, cited: list[dict]) -> str | None:
    """None if the facts back the text: every number is one of its facts' numbers in the same unit (± 1 under 10, else
    ± max(3, 10 %)), a bare number equals one, never rem/em/pt/vh/vw or a hex colour; every quote is in the facts; every
    size named is a cited size and "at all sizes" needs a whole-page fact; no overclaim, scope or causal words."""
    have = [t for f in cited for t in _tokens(f["text"])]
    if _HEX.search(_unquoted(text)):
        return NUMBER
    for v, u in _tokens(text):
        if u in ("rem", "em", "pt", "vh", "vw"):
            return NUMBER
        if u is None:
            if not any(v == m for m, _ in have):
                return NUMBER
        elif not any(mu == u and abs(v - m) <= (1.0 if m < 10 else max(3.0, 0.1 * m)) for m, mu in have):
            return NUMBER
    pool = " ".join(f["text"] for f in cited).lower()
    if not all(q.strip().lower() in pool for q in _QUOTE.findall(text) + _SQUOTE.findall(text)):
        return QUOTE
    whole = _whole(cited)
    for w in re.findall(r"\b(mobile|phones?|tablets?|desktop)\b", _unquoted(text).lower()):
        if not whole and not any(f["bp"] == _SIZE[w] for f in cited):
            return SIZE
    bare = _unquoted(text)
    if _SCOPE.search(bare):
        if not whole:
            return SIZE
        bare = _SCOPE.sub(" ", bare)
    return OVERCLAIM if _OVERCLAIM.search(bare) else None


def _whole(cited: list[dict]) -> bool:
    return any(f["bp"] is None and f["kind"] == "font" for f in cited) or {f["bp"] for f in cited} >= set(BPS)


def verify(raw, fact_list: list[dict]) -> dict:
    """Keep items that cite known facts and say nothing those facts don't back; list the rest with the reason.
    Instructions must say which size they apply to, never act on platform badges or lost text (written from the
    template instead), never position single elements, and never move text a spacing drift on its size explains."""
    known = {f["id"]: f for f in fact_list}
    drifting = {f["bp"] for f in fact_list if f["kind"] == "drift"}
    out, gone = {"summary": [], "fix": []}, []
    for src, dst, cap in (("summary", "summary", MAX_SUMMARY), ("fix_prompt", "fix", MAX_FIX)):
        items = raw.get(src) if isinstance(raw, dict) else None
        if not isinstance(items, list):
            continue
        seen = set()
        for it in items:
            text = (it.get("text") or "").strip() if isinstance(it, dict) else ""
            ids = [str(x).strip() for x in (it.get("facts") or [])] if isinstance(it, dict) and isinstance(it.get("facts"), list) else []
            if not text or len(text) > MAX_CHARS:
                why = "empty or too long"
            elif not ids:
                why = "cites no measured fact"
            elif not all(i in known for i in ids):
                why = "cites a fact that does not exist"
            else:
                cited = [known[i] for i in ids]
                why = _why(text, cited)
                if why is None and src == "fix_prompt":
                    sizes = {f["bp"] for f in cited}
                    named = {_SIZE[w] for w in re.findall(r"\b(mobile|phones?|tablets?|desktop)\b", _unquoted(text).lower())}
                    if any(f.get("badge") or f["kind"] == "vanished" for f in cited):
                        why = "acts on a platform badge or lost text (handled separately)"
                    elif any(f["kind"] in ("moved", "below") and (f["bp"] in drifting or f.get("explained")) for f in cited):
                        why = "moves text that the spacing drift already explains"
                    elif _POSITIONING.search(_unquoted(text)):
                        why = "positions a single element"
                    elif all(f["bp"] is None and f["kind"] == "font" for f in cited) and named and named != set(BPS):
                        why = "narrows a whole-page finding to one size"
                    elif not _whole(cited) and None not in sizes and not (named & sizes):
                        # pasted into a builder without a size, it would change every size
                        why = "does not say which size it applies to"
            if why:
                gone.append({"text": text[:MAX_CHARS], "why": why})
                continue
            if text.lower() in seen or len(out[dst]) >= cap:
                continue
            seen.add(text.lower())
            out[dst].append({"text": text, "facts": ids})
    return {**out, "dropped": len(gone), "dropped_items": gone[:20]}


# ------------------------------------------------------------------------------------------------ template

def _fix_for(f: dict, drift_bps: set) -> dict | None:
    """The template's instruction for one fact (None if it has none: badges are notes, drift-explained moves skipped)."""
    k, bp, i = f["kind"], f["bp"], [f["id"]]
    if k == "font":
        m = re.match(r"The build uses the (.+) font; the design uses (.+)\.$", f["text"])
        return {"text": f"Use the {m.group(2)} font everywhere instead of {m.group(1)}.", "facts": i} if m else None
    if k == "text_size":
        larger = "smaller than" in f["text"]
        return {"text": f"On {bp}, make the text about {f['nums'][1]}% {'larger' if larger else 'smaller'} so it matches the design.", "facts": i}
    if k == "drift":
        tight = "tighter" in f["text"]
        return {"text": f"On {bp}, {'increase' if tight else 'reduce'} the vertical spacing between sections and cards by about "
                        f"{f['nums'][1]}% so content sits where the design has it.", "facts": i}
    if k in ("moved", "below") and (bp in drift_bps or f.get("explained")):
        return None                          # the spacing fix covers it
    if k == "moved":
        return {"text": f"On {bp}, move {_q(f['quote'])} about {f['nums'][0]} px "
                        f"{'lower' if 'higher' in f['text'] else 'higher'}, where the design has it.", "facts": i}
    if k == "below":
        return {"text": f"On {bp}, bring {_q(f['quote'])} back onto the first screen, as in the design.", "facts": i}
    if k == "missing":
        return {"text": f"On {bp}, add {_q(f['quote'])}: it is in the design but not in the build.", "facts": i}
    if k == "unreadable":
        return {"text": f"On {bp}, make sure {_q(f['quote'])} is visible: something covers it or it is too faint.", "facts": i}
    if k == "warning" and not f.get("badge"):
        return {"text": f"Fix this: {f['text'][0].lower()}{f['text'][1:]}", "facts": i}
    if k == "width":
        return {"text": f"{f['text'][:-1]}: make each element fit the screen width.", "facts": i}
    if k == "vanished":
        return {"text": f"{f['text'][:-1]}. If that is not intended, show them or put them in a menu.", "facts": i}
    return None


def template(fact_list: list[dict]) -> dict:
    """A brief written from the facts alone (no model): the floor when Nemotron fails or nothing survives. Platform
    badges become notes, kept out of the message pasted into a builder."""
    drift_bps = {f["bp"] for f in fact_list if f["kind"] == "drift"}
    fix = [x for x in (_fix_for(f, drift_bps) for f in fact_list) if x]
    notes = [{"text": f"{f['text']} It is the platform's badge, not your layout: hide it if your plan allows, or leave space "
                      f"at the bottom so content can scroll clear of it.", "facts": [f["id"]]}
             for f in fact_list if f["kind"] == "warning" and f.get("badge")]
    summary = [{"text": f["text"], "facts": [f["id"]]} for f in fact_list[:MAX_SUMMARY]]
    return {"summary": summary, "fix": fix[:MAX_FIX], "notes": notes}


# ------------------------------------------------------------------------------------------------ Nemotron

SYSTEM = (
    "You turn measurements of a web build into a short fix brief for someone who builds with AI tools (Lovable, v0, "
    "Bolt) or edits the code. Use ONLY the numbered facts. Every item cites the ids of the facts it relies on. Use only "
    "numbers (px, %) that appear in the cited facts; never invent sizes, colours, elements or text. Quote UI text "
    "exactly as the facts quote it. summary: at most 4 short sentences on what differs and where. fix_prompt: at most 6 "
    "imperative instructions a builder can follow, phrased relative to the current build (e.g. 'increase the spacing by "
    "about 25%'), most important first: the font first, then text size, then spacing (on one size text size and "
    "spacing are linked). Leave platform badges and text lost on smaller screens out of fix_prompt: they are handled "
    "separately. Say only what the facts say: no words like key, critical, all, any, every, other, and no causes "
    "('causing', 'making it'). When a size has a spacing-drift fact, text that sits higher or lower on that size is a "
    "consequence of it: fix the spacing, never give separate move instructions for that text. Never suggest absolute "
    "positioning or fixed pixel offsets for single elements. Always include the font if there is a font fact. "
    "Start every instruction with the size it applies to ('On mobile, ...'), unless its fact covers all sizes. "
    "Reply with JSON only: "
    '{"summary": [{"text": "...", "facts": ["F1"]}], "fix_prompt": [{"text": "...", "facts": ["F2", "F3"]}]}'
)
CODE_NOTE = " The build is one React + Tailwind App.jsx: instructions may name Tailwind utilities."


def _kind(bundle: dict) -> str:
    if ((bundle or {}).get("report") or {}).get("mode") == "audit":
        return "audit"
    return "code" if ((bundle or {}).get("source") or {}).get("code") else "url"


INTRO = {
    "url": "Please update this page so it matches my design frames at every screen size:",
    "code": "Please edit App.jsx (React + Tailwind) so it matches my design frames at every screen size:",
    "audit": "Please fix these issues found when checking the page at every screen size:",
}


def _cover(fix: list[dict], fact_list: list[dict]) -> list[dict]:
    """Every actionable fact no kept instruction acts on gets the template's line, marked added: the brief stays
    complete even when Nemotron's line for it was dropped. Nemotron's kept lines come first."""
    drift_bps = {f["bp"] for f in fact_list if f["kind"] == "drift"}
    cited = {i for it in fix for i in it["facts"]}
    out = list(fix)
    for f in fact_list:
        if f["id"] not in cited and len(out) < MAX_FIX:
            line = _fix_for(f, drift_bps)
            if line:
                out.append({**line, "added": True})
    return out[:MAX_FIX]


def brief(bundle: dict, *, client=None, model: str | None = None) -> dict:
    """{"source": "nemotron" | "template" | "none", "intro", "summary", "fix", "dropped", "facts", ...}"""
    fact_list = facts(bundle)
    kind = _kind(bundle)
    base = {"intro": INTRO[kind], "facts": fact_list, "notes": template(fact_list)["notes"] if fact_list else []}
    if not fact_list:
        return {"source": "none", "summary": [], "fix": [], "added": 0, "dropped": 0, "dropped_items": [], **base}
    dropped, gone = 0, []
    if client is not None:
        model = model or config.MODEL_BRIEF
        user = (f"Build: {'an App.jsx' if kind == 'code' else 'a deployed page'}; "
                f"{'no design frames (an audit)' if kind == 'audit' else 'checked against its design frames'}.\nFacts:\n"
                + "\n".join(f"{f['id']} [{f['bp'] or 'all sizes'}] {f['text']}" for f in fact_list))
        try:
            r = client.chat(model, [{"role": "system", "content": SYSTEM + (CODE_NOTE if kind == "code" else "")},
                                    {"role": "user", "content": user}],
                            step="brief", thinking="off", max_tokens=1500, temperature=0.3)
            out = verify(parse_json(r.content), fact_list)
        except Exception:                      # Nemotron unavailable: the template still gives a brief
            out = {"summary": [], "fix": [], "dropped": 0, "dropped_items": []}
        dropped, gone = out["dropped"], out["dropped_items"]
        if out["summary"] or out["fix"]:
            fix = _cover(out["fix"], fact_list)
            return {"source": "nemotron", "model": model, "summary": out["summary"], "fix": fix,
                    "added": sum(1 for i in fix if i.get("added")), "dropped": dropped, "dropped_items": gone, **base}
    t = template(fact_list)
    return {"source": "template", "summary": t["summary"], "fix": t["fix"], "added": 0, "dropped": dropped,
            "dropped_items": gone if client is not None else [], **base}
