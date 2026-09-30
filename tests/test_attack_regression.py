"""Full-pipeline regression over every red-team attack (lint + render + pixel integrity + score).

Reads out/redteam/rescore.json from tools/rescore_attacks.py (local only; skips if absent).
Classes (by what the page visibly is, not by file name patterns):
  trick   — base page + hidden/visible stuffing (+dump*, +occl*, +strip): must gain ≤ 0.5 over its base;
  hack    — visible content is not the design: final match < 60;
  honest  — real pages, markup variants and imperfections: never disqualified; markup variants within 3 of close.
  (h_heading_br is NOT a markup-only variant: the <br> changes the mobile line break, a real visible difference.)
"""
import json
import re
from pathlib import Path

import pytest

F = Path(__file__).resolve().parents[1] / "out" / "redteam" / "rescore.json"
rows = json.loads(F.read_text()) if F.exists() else []
needs = pytest.mark.skipif(not rows, reason="run tools/rescore_attacks.py first")
TRICK = re.compile(r"\+(dump\w*|occlS?|strip)$")
REF = re.compile(r"\+spacer$")   # neutralised twins of +strip (reference only, never asserted)
HACK = re.compile(r"^(r1_)?(blank|close_lorem|h_(barcode|bg_lines|blobs\d+|dust\d|fakeresp_junk\d+|heading_only|random_text|textbars_\w+|textlines_thin|traced))$")
MARKUP = re.compile(r"^h_(gradient_heading|heading_em_span|heading_semibold|input_placeholder|sr_only_x\d|tracking_tight)$")


def base_of(r):
    return TRICK.sub("", r["name"])


def lookup(r, name):
    return next((x for x in rows if x["round"] == r["round"] and x["page"] == r["page"] and x["name"] == name), None)


@needs
def test_tricks_gain_nothing():
    bad = []
    for r in rows:
        if TRICK.search(r["name"]):
            b = lookup(r, base_of(r))
            if b is None:
                continue
            ref = b["match"]
            twin = lookup(r, r["name"].replace("+strip", "+spacer")) if r["name"].endswith("+strip") else None
            if twin is not None:   # the strip also acts as a spacer; compare against its neutralised twin too
                ref = max(ref, twin["match"])
            if r["match"] > ref + 0.5:
                bad.append((r["round"], r["page"], r["name"], r["match"], ref))
    assert not bad, bad


@needs
def test_standalone_hacks_below_60():
    bad = [(r["round"], r["page"], r["name"], r["match"]) for r in rows if HACK.match(r["name"]) and r["match"] >= 60]
    assert not bad, bad


@needs
def test_honest_never_disqualified():
    bad = [(r["round"], r["page"], r["name"], r["why"]) for r in rows
           if not TRICK.search(r["name"]) and not REF.search(r["name"]) and not HACK.match(r["name"])
           and r["why"] and r["raw"] is not None]
    assert not bad, bad


@needs
def test_markup_variants_not_penalised():
    bad = []
    for r in rows:
        if MARKUP.match(r["name"]):
            c = lookup(r, "close")
            if c is not None and r["match"] < c["match"] - 3:
                bad.append((r["page"], r["name"], r["match"], c["match"]))
    assert not bad, bad


@needs
@pytest.mark.parametrize("page", ["netflix-signin", "calcom-signup"])
def test_ladder_monotonic_full_pipeline(page):
    m = {r["name"]: r["match"] for r in rows if r["page"] == page and r["round"] == "r1"}
    assert m["rough"] < m["decent"] < m["close"], m
