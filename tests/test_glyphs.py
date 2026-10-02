"""Short thin rules crossing at their centres are ONE glyph (a "+" icon), rendered as a small box with two centred
bars — as two loose rules the layout split them into a "⊥" (lambda's menu rows, Oct 2). Written before the
implementation (TDD)."""
import re

from orchestrator.fluid import compile_fluid

SIZES = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}


def spec(blocks, texts=()):
    return {"breakpoints": {bp: {"size": list(SIZES[bp]), "background": "#0b0b0b",
                                 "texts": [{"text": t, "box": list(b), "size_px": 14, "color": "#ffffff", "role": "nav",
                                            "weight": 400, "lines": 1, "measured": True} for t, b in texts],
                                 "blocks": [dict(b, rule=True) for b in blocks]} for bp in ["mobile"]}}


PLUS = [{"box": [356, 187, 12, 2], "fill": "#e7e6d9"}, {"box": [361, 182, 2, 12], "fill": "#e7e6d9"}]


def test_plus_becomes_one_glyph_with_centred_bars():
    code = compile_fluid(spec(PLUS, [("PRODUCTS", (21, 182, 78, 12))]))
    m = re.search(r'<div aria-hidden="true" data-glyph="plus" className="([^"]*)">(.*?)</div>\s*$', code, re.S | re.M)
    assert m, code
    box_cls = m.group(1)
    assert "relative" in box_cls and "w-[12px]" in box_cls and "h-[12px]" in box_cls
    inner = code[code.index('data-glyph="plus"'):].split("</div>")[0] + "</div>" + code[code.index('data-glyph="plus"'):].split("</div>")[1]
    assert inner.count("absolute") == 2 and "h-[2px]" in inner and "w-[2px]" in inner


def test_glyph_sits_on_the_row_line():
    code = compile_fluid(spec(PLUS, [("PRODUCTS", (21, 182, 78, 12))]))
    row = code[:code.index('data-glyph="plus"')].rsplit('<div className="', 1)[1]
    assert "flex-row" in row, "label and plus share one row"


def test_non_crossing_rules_stay_rules():
    rules = [{"box": [20, 100, 12, 2], "fill": "#e7e6d9"}, {"box": [200, 300, 2, 12], "fill": "#e7e6d9"}]
    code = compile_fluid(spec(rules))
    assert "data-glyph" not in code


def test_long_crossing_lines_are_not_a_glyph():
    rules = [{"box": [0, 400, 390, 1], "fill": "#333333"}, {"box": [195, 300, 1, 200], "fill": "#333333"}]
    assert "data-glyph" not in compile_fluid(spec(rules))
