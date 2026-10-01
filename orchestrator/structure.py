"""Structure planner: Nemotron reads the measured elements and decides how the page is GROUPED.

Geometry alone can't tell three pricing cards from three loose columns of text, or a nav from a row of links.
Nemotron returns a nested grouping (header / nav / hero / section / cards / card / form / footer / column …) with a
semantic tag per group; the scaffold compiler turns each group into a real wrapper element and keeps using the
measurements for every number. The plan is validated (unknown / duplicated ids dropped) before use.
"""
from __future__ import annotations

import json

from . import config
from .tf_client import TFClient, parse_json

BPS = ("mobile", "tablet", "desktop")
KINDS = ("header", "nav", "hero", "section", "cards", "card", "form", "footer", "column", "list", "row", "group")
TAGS = ("header", "nav", "main", "section", "footer", "aside", "form", "ul", "li", "article", "div")

SYSTEM = """You are a senior front-end engineer planning the DOM structure of a responsive page from measurements.
You get every measured element of a design (texts and filled/bordered boxes) with an id and its box [x, y, w, h] at
three breakpoints (mobile 390 px, tablet 768 px, desktop 1280 px; "-" = not in that frame).
Group the elements the way a good engineer would structure the page: header, nav, hero, sections, a row of cards and
each card, forms, footer columns, sidebars. A box element that visually encloses other elements (a card background,
a button, an input) should be a member of the same group as what it encloses.
Rules:
- Every group's members must be visually contiguous at every breakpoint (a card's texts stay together).
- Groups may contain groups (e.g. "cards" contains three "card" groups). Use ids "G1", "G2", …
- Each element id appears in at most one group. Elements you don't group stay at the top level.
- Prefer few, meaningful groups; don't wrap single elements.
Reply with JSON only:
{"groups": [{"id": "G1", "kind": "header|nav|hero|section|cards|card|form|footer|column|list|row|group",
             "tag": "header|nav|main|section|footer|aside|form|ul|li|article|div", "members": ["E3", "E4", "G2"]}]}"""


def element_table(items) -> tuple[str, dict]:
    """Compact table of scaffold items with stable ids E1…; returns (text, {Eid: item})."""
    ids, rows = {}, []
    for k, it in enumerate(sorted(items, key=lambda i: min(_y(i, bp) for bp in i.at)), 1):
        eid = f"E{k}"
        ids[eid] = it
        boxes = []
        for bp in BPS:
            a = it.at.get(bp)
            if not a:
                boxes.append("-")
                continue
            b = a.get("ink") or a.get("box")
            boxes.append(f"[{','.join(str(int(v)) for v in b)}]")
        what = (f'text {it.role} "{it.text[:50]}"' if it.kind == "text" else
                f"box fill {next((a.get('fill') for a in it.at.values()), '?')}" +
                (" border" if any(a.get("border") for a in it.at.values()) else "") +
                (" (rule)" if any((a.get("box") or [0, 0, 0, 9])[3] <= 3 for a in it.at.values()) else ""))
        rows.append(f"{eid} | {what} | " + " | ".join(boxes))
    return "id | element | mobile | tablet | desktop\n" + "\n".join(rows), ids


def _y(it, bp):
    a = it.at[bp]
    return (a.get("ink") or a.get("box"))[1]


def validate(plan: dict, ids: dict) -> list[dict]:
    """Keep well-formed groups; drop unknown ids, members claimed twice, cycles, and single-member groups."""
    groups = [g for g in (plan or {}).get("groups", []) if isinstance(g, dict) and isinstance(g.get("members"), list)]
    gids = {str(g.get("id")) for g in groups}
    seen, out = set(), []
    for g in groups:
        mem = []
        for m in g["members"]:
            m = str(m)
            if (m in ids or m in gids) and m not in seen and m != str(g.get("id")):
                mem.append(m)
                seen.add(m)
        if len(mem) >= 2:
            out.append({"id": str(g["id"]), "kind": g.get("kind") if g.get("kind") in KINDS else "group",
                        "tag": g.get("tag") if g.get("tag") in TAGS else "div", "members": mem})
    # drop references to groups that didn't survive
    alive = {g["id"] for g in out}
    for g in out:
        g["members"] = [m for m in g["members"] if not m.startswith("G") or m in alive]
    # cycle guard: a group may not (transitively) contain itself
    child = {g["id"]: [m for m in g["members"] if m.startswith("G")] for g in out}
    def reaches(a, b, depth=0):
        return depth < 20 and any(c == b or reaches(c, b, depth + 1) for c in child.get(a, []))
    return [g for g in out if not reaches(g["id"], g["id"])]


def plan_structure(client: TFClient, items, *, model: str | None = None) -> tuple[list[dict], dict]:
    table, ids = element_table(items)
    r = client.chat(model or config.MODEL_PLANNER, [{"role": "system", "content": SYSTEM},
                                                    {"role": "user", "content": "Measured elements:\n" + table}],
                    step="structure plan", thinking="off", max_tokens=4000, temperature=0.2)
    plan = parse_json(r.content)
    return validate(plan if isinstance(plan, dict) else {}, ids), ids


SEMANTIC_SYSTEM = """You name the regions of a web page so its HTML is semantic. You get the page's layout segments (found
by cutting the page into horizontal bands and side-by-side columns) as an indented tree — a child is inside its
parent — with its desktop position and the texts inside. A child inherits its parent's role: links inside a footer are
part of the footer (don't tag them), the three columns inside a pricing section are cards (article), not footers. Choose an HTML element for each segment that is clearly one of these; leave the rest out (they stay div):
header (site header / top bar with logo and nav), nav (a list of navigation links), main (the primary content area),
section (a thematic block such as a hero, a pricing grid, a feature list), article (one self-contained card), aside
(a side panel), footer (site footer). Use each of header/main/footer at most once and at most 6 tags in total —
tag only clear regions. Reply with JSON only:
{"tags": {"S1": "header", "S4": "section"}}"""


def semantic_tags(client: TFClient, segments: list[dict], *, model: str | None = None) -> dict:
    # an indented tree (children under parents), meaningful regions only (≥ 2 texts); a flat list made Nemotron tag
    # a pricing column as <footer> because it couldn't see the nesting
    keep = {sg["id"] for sg in segments if sg["n_texts"] >= 2}
    by_parent: dict = {}
    for sg in segments:
        if sg["id"] in keep:
            p = sg.get("parent")
            while p and p not in keep:
                p = next((o.get("parent") for o in segments if o["id"] == p), None)
            by_parent.setdefault(p, []).append(sg)
    rows = []
    def emit(pid, depth):
        for sg in sorted(by_parent.get(pid, []), key=lambda g: (g["boxes"].get("desktop") or next(iter(g["boxes"].values())))[1]):
            b = sg["boxes"].get("desktop") or next(iter(sg["boxes"].values()))
            rows.append("  " * depth + f'{sg["id"]}: {sg["kind"]} at desktop y={int(b[1])}..{int(b[1] + b[3])} '
                        f'x={int(b[0])}..{int(b[0] + b[2])}, {sg["n_texts"]} texts: ' + " | ".join(t.replace("\n", " ") for t in sg["texts"][:5]))
            emit(sg["id"], depth + 1)
    emit(None, 0)
    r = client.chat(model or config.MODEL_PLANNER, [{"role": "system", "content": SEMANTIC_SYSTEM},
                                                    {"role": "user", "content": "Segment tree (indented = inside):\n" + "\n".join(rows[:40])}],
                    step="structure plan", thinking="low", max_tokens=2000, temperature=0.2)
    d = parse_json(r.content) or parse_json(r.reasoning) or {}
    tags = d.get("tags", {}) if isinstance(d, dict) else {}
    ok = {"header", "nav", "main", "section", "article", "aside", "footer"}
    out, used = {}, set()
    for sid, tag in tags.items():
        if tag in ok and any(sg["id"] == sid for sg in segments) and not (tag in ("header", "main", "footer") and tag in used):
            out[sid] = tag
            used.add(tag)
    return out


def apply_semantics(code: str, tags: dict) -> tuple[str, int]:
    """Retag segment wrappers (data-seg) via the deterministic set_tag tool."""
    import re
    from . import jsx_edit
    tagged, _ = jsx_edit.tag(code)
    ops = []
    for m in re.finditer(r'<div data-pc="(\d+)" data-seg="(S\d+)"', tagged):
        if m.group(2) in tags:
            ops.append({"op": "set_tag", "id": int(m.group(1)), "tag": tags[m.group(2)]})
    new, n, _ = jsx_edit.structural(tagged, ops)
    return new, n
