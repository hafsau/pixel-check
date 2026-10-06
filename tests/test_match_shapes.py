"""Text-free box matching across frames (orchestrator/match.py): a 360×360 picture placeholder was paired with a
6×300 beige line in another frame, and a 16×16 icon with a 74×9 sliver — fills within the colour tolerance and
heights within 2×, but nothing alike. Boxes must have a similar shape (aspect ratio within 5×), and the capture's
media-placeholder grey only pairs with itself. Written before the fix (TDD, Oct 6)."""
from orchestrator.match import _compatible


def obs(box, fill):
    return {"box": list(box), "fill": fill}


def test_square_picture_does_not_pair_with_a_thin_line():
    assert not _compatible(obs((204, 242, 360, 360), "#d4d4d8"), obs((424, 424, 6, 300), "#ebe1d2"))


def test_icon_does_not_pair_with_a_flat_sliver():
    assert not _compatible(obs((249, 681, 16, 16), "#d4d4d8"), obs((702, 749, 74, 9), "#e0d6c8"))


def test_placeholder_grey_pairs_only_with_placeholder_grey():
    assert _compatible(obs((95, 246, 200, 200), "#d4d4d8"), obs((204, 242, 360, 360), "#d5d4d8"))
    assert not _compatible(obs((95, 246, 200, 200), "#d4d4d8"), obs((204, 242, 360, 360), "#dcd6cc"))


def test_full_width_banner_still_pairs_across_frames():
    assert _compatible(obs((0, 100, 390, 200), "#1e293b"), obs((0, 120, 1280, 400), "#1f2a3c"))
    assert _compatible(obs((16, 300, 358, 60), "#f4f4f5"), obs((140, 300, 1000, 60), "#f4f4f5"))


def test_rules_keep_working():
    assert _compatible(obs((0, 50, 390, 1), "#262625"), obs((0, 60, 1280, 1), "#3d3d21"))


def test_reading_order_rank_never_overrides_an_incompatible_pair():
    """Same coarse colour bin and same rank in a one-member group used to force a pairing (cost 0.8) even when the
    boxes were incompatible."""
    from orchestrator.match import rematch_textfree
    from orchestrator.scaffold import Item
    anchor = Item("t:name", "text")
    anchor.at = {"desktop": {"box": [184, 150, 930, 208]}, "tablet": {"box": [134, 149, 509, 113]}}
    a = Item("b:tf0:-", "block")
    a.at = {"desktop": {"box": [424, 424, 6, 300], "fill": "#ebe1d2"}}
    b = Item("b:tf1:-", "block")
    b.at = {"tablet": {"box": [204, 242, 360, 360], "fill": "#d4d4d8"}}
    out = rematch_textfree([anchor, a, b])
    blocks = [it for it in out if it.kind == "block"]
    assert sorted(len(it.at) for it in blocks) == [1, 1]
