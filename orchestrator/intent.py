"""Responsive-intent planner: Nemotron decides what three frames can't show; the fluid compiler executes it.

Measurement gives every number, but some structure is a judgement across frames:
- repeated components: which elements form each card of a pricing / feature / product grid. Desktop may show three
  columns inside one bordered wrapper while mobile shows three separately outlined cards; geometry alone paired the
  wrong boxes (Oct 1, vercel-pricing). Nemotron names the cards; geometry still decides boxes, styles and column
  counts per frame (orchestrator/fluid._apply_cards).
- page container: wider than the desktop frame, does a band stay a centred column or stretch edge to edge?

Every plan is validated (unknown / duplicate ids dropped) and then VERIFIED, not trusted: each decision is adopted
only if the compiled page scores no worse at the design widths and passes at least as many in-between-width checks
(tools/intent_eval.py, loop seeding). Adoption is logged so the ablation can report what Nemotron changed.
"""
from __future__ import annotations

from . import config, fluid
from .structure import element_table
from .tf_client import TFClient, parse_json

SYSTEM = """You plan the responsive structure of a web page from measurements of three design frames: mobile (390 px
wide), tablet (768 px) and desktop (1280 px). You get every measured element with an id and its box [x, y, w, h] in
each frame ("-" = not visible in that frame, e.g. below the fold), and the page's horizontal bands.

Decide two things:
1. Repeated components. Find groups of 2 or more sibling components with the same internal structure: pricing
   cards, feature cards, product tiles, testimonials, team members, footer link columns. For each group list its
   cards in reading order, and for each card the ids of ALL elements that belong to it: its texts, its icons and
   buttons, its own outline box if it has one. The same card may sit side by side on desktop and stacked on
   mobile — follow the texts, not the positions. Never put a box that encloses several cards into a card.
   Don't invent groups: a heading with a paragraph is not a card grid. Leave "cards" empty if there is none.
2. Page container, for screens WIDER than the desktop frame: for each band, "centred" (content stays a centred
   column of the desktop width — typical for text, forms, card grids) or "full" (stretches edge to edge — typical
   for a top bar with logo left and actions right, or full-bleed media).

Reply with JSON only:
{"cards": [{"name": "pricing plans", "cards": [["E12", "E13", "E14"], ["E20", "E21"]]}],
 "bands": {"0": "full", "1": "centred"}}"""


def band_table(spec: dict) -> str:
    fluid.compile_fluid(spec)   # deterministic dry run: band membership as the compiler sees it
    rows = []
    for b in fluid.STATE.get("bands", []):
        d = b["boxes"].get("desktop") or next(iter(b["boxes"].values()), None)
        where = f"desktop x={int(d[0])}..{int(d[0] + d[2])} y={int(d[1])}..{int(d[1] + d[3])}" if d else "-"
        rows.append(f'band {b["band"]}: {where}; texts: ' + " | ".join(t.replace("\n", " ") for t in b["texts"]))
    return "\n".join(rows)


def validate(plan: dict, ids: dict, n_bands: int = 0) -> dict:
    """Keep well-formed decisions only: known ids, each id in one card, ≥ 2 cards of ≥ 1 element per group."""
    out = {"cards": [], "bands": {}}
    seen = set()
    for g in (plan or {}).get("cards") or []:
        cards = g.get("cards") if isinstance(g, dict) else g
        if not isinstance(cards, list):
            continue
        keys = []
        for card in cards:
            if not isinstance(card, list):
                continue
            ks = []
            for e in card:
                e = str(e)
                if e in ids and e not in seen:
                    seen.add(e)
                    ks.append(ids[e].key)
            if ks:
                keys.append(ks)
        if len(keys) >= 2:
            why = _overlapping(keys, ids)
            if why:
                out.setdefault("dropped", []).append(f"{g.get('name') if isinstance(g, dict) else 'group'}: {why}")
            else:
                out["cards"].append(keys)
    sigs = {str(b["band"]): b["sig"] for b in fluid.STATE.get("bands", [])}
    for k, v in ((plan or {}).get("bands") or {}).items():
        if str(k) in sigs and v in ("centred", "full"):
            out["bands"][sigs[str(k)]] = {"desktop": v}
    return out


def _overlapping(keys: list[list[str]], ids: dict) -> str | None:
    """A repeated component: cards of similar size (text count within 2.5×) whose texts are disjoint regions in every
    frame. Oct 1: the planner sliced netflix's footer into "3 texts on mobile" + "8 below the fold" (not cards); an
    outline box listed with the wrong card is fine (fluid._apply_cards re-homes it), so only texts are compared."""
    items = {it.key: it for it in ids.values()}
    texts = [[items[k] for k in card if items[k].kind == "text"] for card in keys]
    n = [len(t) for t in texts]
    if min(n) == 0 or max(n) > 2.5 * min(n):
        return f"cards differ in size ({n} texts): not a repeated component"
    for bp in fluid.BPS:
        us = [fluid._union(t, bp) for t in texts]
        for i in range(len(us)):
            for j in range(i + 1, len(us)):
                a, b = us[i], us[j]
                if not a or not b:
                    continue
                ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
                iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
                if ix * iy > 0.2 * min(a[2] * a[3], b[2] * b[3]):
                    return f"cards {i} and {j} overlap at {bp}"
    return None


def plan_intents(client: TFClient, spec: dict, *, model: str | None = None) -> tuple[dict, dict]:
    """→ (validated intents for compile_fluid, raw record for the trace)."""
    table, ids = element_table(fluid.prepare(spec))
    bands = band_table(spec)
    r = client.chat(model or config.MODEL_INTENT,
                    [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": "Measured elements:\n" + table + "\n\nBands:\n" + bands}],
                    step="intent plan", thinking="off", max_tokens=4000, temperature=0.2)
    plan = parse_json(r.content) or parse_json(r.reasoning) or {}
    intents = validate(plan if isinstance(plan, dict) else {}, ids, len(fluid.STATE.get("bands", [])))
    return intents, {"raw": plan, "usd": r.usd, "in": r.input_tokens, "out": r.output_tokens, "model": r.model}


def revalidate(spec: dict, raw: dict) -> dict:
    """Re-validate a cached raw plan against the current compiler (ids and band signatures are recomputed)."""
    _, ids = element_table(fluid.prepare(spec))
    band_table(spec)
    return validate(raw if isinstance(raw, dict) else {}, ids)
