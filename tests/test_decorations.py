"""Decoration filter (fluid._decorations): background patterns are dropped, but layout lines never are.
Oct 2: a menu with 12 row dividers lost 9 of them — "lonely" (15 px from their label) and ≥ 10 of one style, with
text inside their union, they looked like a pattern. Written before the fix (TDD)."""
from orchestrator.fluid import compile_fluid

SIZES = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}


def spec(texts, blocks):
    return {"breakpoints": {"mobile": {"size": [390, 844], "background": "#0b0b0b",
                                       "texts": [{"text": t, "box": list(b), "size_px": 14, "color": "#ffffff",
                                                  "role": "nav", "weight": 400, "lines": 1, "measured": True} for t, b in texts],
                                       "blocks": blocks}}}


def test_many_row_dividers_survive():
    texts = [(f"ITEM {i}", (21, 30 + 46 * i, 80, 11)) for i in range(12)]
    rules = [{"box": [21, 56 + 46 * i, 349, 1], "fill": "#262625", "rule": True} for i in range(12)]
    code = compile_fluid(spec(texts, rules))
    assert code.count("h-[1px]") == 12


def test_scattered_pattern_shapes_still_dropped():
    import random
    random.seed(4)
    texts = [("Jobs for builders", (40, 200, 300, 40))]
    pills = [{"box": [random.randint(0, 330), random.randint(100, 400), 60, 22], "fill": "#fddfc7"} for _ in range(14)]
    code = compile_fluid(spec(texts, pills))
    assert code.count("bg-[#fddfc7]") < 5
