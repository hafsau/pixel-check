"""Overlapping layers (Phase 2, Oct 6): a hero picture that overlaps the headline (a portfolio's portrait over the
name) was dropped as "background decoration", and its soft shadow became a sliver block that pushed the rest of
the page below the fold. A single large solid block partly overlapping text is a LAYER: absolutely positioned
inside its band (text-free, so the anti-cheat's traced-layout rule is unaffected), centred when centred in every
frame. Low-contrast slivers hugging a layer (its shadow) are dropped. Written before the change (TDD)."""
import re

from orchestrator.fluid import compile_fluid

BG = "#fff4e4"


def text(t, box, size=70, role="heading", weight=700):
    return {"text": t, "box": list(box), "size_px": size, "color": "#191919", "role": role, "weight": weight,
            "lines": 1, "measured": True}


def hero(layer_boxes, halo=True, extra=None):
    frames = {
        "mobile": ([text("NAV ONE", (80, 29, 70, 9), 12, "nav", 500), text("FIRSTNAME", (60, 197, 270, 52)),
                    text("LASTNAME", (60, 446, 272, 52)), text("Designer in a city", (60, 620, 270, 16), 14, "body", 400)],
                   (390, 844)),
        "tablet": ([text("NAV ONE", (224, 38, 80, 10), 13, "nav", 500), text("FIRSTNAME", (100, 149, 560, 113), 150),
                    text("LASTNAME", (88, 580, 595, 114), 150), text("Designer in a city", (88, 753, 300, 16), 15, "body", 400)],
                   (768, 1024)),
        "desktop": ([text("NAV ONE", (596, 38, 90, 10), 13, "nav", 500), text("FIRSTNAME", (184, 150, 930, 208), 270),
                     text("LASTNAME", (184, 571, 930, 208), 270), text("Designer in a city", (184, 790, 300, 8), 15, "body", 400)],
                    (1280, 800)),
    }
    spec = {"breakpoints": {}}
    for bp, (texts, size) in frames.items():
        blocks = []
        if bp in layer_boxes:
            x, y, w, h = layer_boxes[bp]
            blocks.append({"box": [x, y, w, h], "fill": "#d4d4d8", "radius": 24})
            if halo:     # the shadow's visible edge, measured as a faint block beside the picture
                blocks.append({"box": [x - 44, y + 16, 45, h + 26], "fill": "#f7ecdc", "radius": 22})
        blocks += (extra or {}).get(bp, [])
        spec["breakpoints"][bp] = {"size": list(size), "background": BG, "texts": texts, "blocks": blocks}
    return spec


CENTRED = {"mobile": (95, 246, 200, 200), "tablet": (204, 242, 360, 360), "desktop": (430, 329, 420, 420)}


def _layer_line(code):
    lines = [l for l in code.splitlines() if "bg-[#d4d4d8]" in l]
    assert len(lines) == 1, lines
    return lines[0]


def test_an_overlapping_picture_is_kept_as_a_positioned_layer():
    code = compile_fluid(hero(CENTRED))
    line = _layer_line(code)
    assert "absolute" in line and 'aria-hidden="true"' in line
    assert "left-1/2" in line and "-translate-x-1/2" in line          # centred in every frame
    for cls in ("w-[200px]", "md:w-[360px]", "xl:w-[420px]", "h-[200px]", "md:h-[360px]", "xl:h-[420px]",
                "rounded-[24px]"):
        assert cls in line, cls
    assert re.search(r'\btop-\[-?\d+px\]', line)


def test_the_layer_sits_in_a_relative_band_and_the_text_stays_in_flow():
    code = compile_fluid(hero(CENTRED))
    lines = code.splitlines()
    i = next(k for k, l in enumerate(lines) if "bg-[#d4d4d8]" in l)
    band = next(l for l in reversed(lines[:i]) if "data-seg=" in l and "flow-root w-full" in l)
    assert " relative" in band
    for t in ("FIRSTNAME", "LASTNAME", "Designer in a city"):
        tl = next(l for l in lines if t in l)
        assert "absolute" not in tl


def test_the_shadow_sliver_is_dropped():
    code = compile_fluid(hero(CENTRED))
    assert "bg-[#f7ecdc]" not in code


def test_an_off_centre_layer_is_placed_from_the_left_per_breakpoint():
    off = {"mobile": (20, 246, 200, 200), "tablet": (40, 242, 360, 360), "desktop": (100, 329, 420, 420)}
    line = _layer_line(compile_fluid(hero(off)))
    assert "left-1/2" not in line
    assert "left-[20px]" in line and "md:left-[40px]" in line and "xl:left-[100px]" in line


def test_a_layer_in_one_frame_only_is_hidden_elsewhere():
    line = _layer_line(compile_fluid(hero({"mobile": CENTRED["mobile"]})))
    assert "md:hidden" in line and "absolute" in line


def test_small_overlapping_shapes_are_not_layers():
    """An icon-sized partial overlap is still decoration (dropped), never a positioned layer."""
    small = {bp: (b[0], b[1], 30, 30) for bp, b in CENTRED.items()}
    code = compile_fluid(hero(small, halo=False))
    assert "absolute" not in code.replace("sr-only", "")


def test_a_pattern_of_many_shapes_is_still_dropped_not_layered():
    import random
    random.seed(4)
    pills = {"mobile": [{"box": [random.randint(0, 330), random.randint(150, 500), 90, 40], "fill": "#fddfc7"}
                        for _ in range(12)]}
    code = compile_fluid(hero({}, halo=False, extra=pills))
    assert code.count("bg-[#fddfc7]") < 4 and code.count("absolute") <= 1


def test_page_without_overlap_is_unchanged_by_the_layer_pass():
    plain = hero({})
    code = compile_fluid(plain)
    assert "absolute" not in code and " relative" not in code


def test_a_darker_shadow_edge_is_dropped_too():
    """The shadow's edge measured 20 levels off the page (#ebe0d1 on #fff4e4) — still a shadow, not layout."""
    spec = hero(CENTRED, halo=False, extra={"tablet": [{"box": [563, 337, 7, 243], "fill": "#ebe0d1"}],
                                             "mobile": [{"box": [93, 300, 6, 150], "fill": "#ebe1d2"}]})
    code = compile_fluid(spec)
    assert "bg-[#ebe0d1]" not in code and "bg-[#ebe1d2]" not in code


def test_a_layer_missing_its_radius_in_one_frame_borrows_it():
    spec = hero(CENTRED, halo=False)
    del spec["breakpoints"]["tablet"]["blocks"][0]["radius"]
    line = _layer_line(compile_fluid(spec))
    assert "md:rounded-none" not in line and "rounded-none" not in line


def test_each_frame_places_the_layer_in_the_band_holding_its_top_there():
    """When one frame's headline sits in another band, the layer goes there in that frame (it was hidden)."""
    from orchestrator.fluid import _layer_bands
    from orchestrator.scaffold import Item

    def blk(key, at):
        it = Item(key, "block")
        it.at = {bp: {"box": b, "fill": "#111111"} for bp, b in at.items()}
        return it
    band0 = [blk("a", {"mobile": [0, 150, 390, 400], "tablet": [0, 140, 768, 500]})]
    band1 = [blk("b", {"desktop": [0, 140, 1280, 600]})]
    L = blk("L", {"mobile": [95, 246, 200, 200], "tablet": [204, 242, 360, 360], "desktop": [430, 329, 420, 420]})
    assert _layer_bands(L, [band0, band1]) == {0: {"mobile", "tablet"}, 1: {"desktop"}}
