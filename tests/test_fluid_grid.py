"""Rows that wrap into a grid (Oct 12, Hafsa's dashboard): the four stat cards sit 2 × 2 on mobile and tablet and
1 × 4 on desktop. _row_mode only knew one line (flex-row) or a stack (flex-col): the 2 × 2 became a zig-zag
column. Equal lines with aligned columns → grid grid-cols-N with the measured gaps. Written before the code (TDD)."""
from orchestrator.fluid import _row_mode
from orchestrator.scaffold import Item


def items(boxes, bp="tablet"):
    out = []
    for k, b in enumerate(boxes):
        it = Item(f"c{k}", "block")
        it.at[bp] = {"box": list(b), "fill": "#ffffff"}
        out.append(it)
    return out


def test_two_by_two_cards_are_a_two_column_grid():
    p = items([(24, 285, 352, 78), (392, 285, 352, 78), (24, 379, 352, 78), (392, 379, 352, 78)])
    mode, per = _row_mode(p, "tablet", (0, 0, 768, 1024))
    assert mode["disp"] == "grid" and mode["dir"] == "grid-cols-2"
    assert mode["gapx"] == "gap-x-[16px]" and mode["gapy"] == "gap-y-[16px]"
    assert mode["pl"] == "pl-[24px]" and mode["pr"] == "pr-[24px]"
    assert all(v[0] == 0 and v[1] == 0 for v in per.values())


def test_a_real_stack_stays_a_column():
    p = items([(24, 100, 300, 40), (24, 160, 200, 40), (60, 230, 250, 40)])
    mode, _ = _row_mode(p, "tablet", (0, 0, 768, 1024))
    assert mode["dir"] == "flex-col"


def test_unequal_lines_are_not_a_grid():
    p = items([(24, 100, 200, 40), (240, 100, 200, 40), (456, 100, 200, 40), (24, 160, 200, 40)])
    mode, _ = _row_mode(p, "tablet", (0, 0, 768, 1024))
    assert mode["disp"] != "grid"


def test_an_icon_beside_a_number_and_label_is_two_columns():
    """Dashboard stat card: a 44 px icon, then "12" over "Workouts" 13 px to its right — the gutter rule wanted 16."""
    from orchestrator.fluid import _split
    p = items([(41, 301, 44, 44), (98, 307, 21, 15), (98, 332, 50, 9)])
    s = _split(p, "tablet")
    assert s is not None and [c.key for c in s[2]] == ["c0"] and [c.key for c in s[3]] == ["c1", "c2"]
