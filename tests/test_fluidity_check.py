"""Width sweep on real pages (check mode, Oct 6): overlaps the design itself has at its nearest size (a decorative
star over a headline) are not breakage between sizes; only overlaps beyond them fail. Our own renders have none at
the design sizes, so their verdicts are unchanged. Written before the change (TDD)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sandbox"))
import fluidity  # noqa: E402


def checks(bp_overlaps, between_overlaps):
    bps = {b: {"text_overlaps": bp_overlaps, "overflow_px": 0, "max_vertical_gap": 10, "height": 800,
               "background_covers": True, "content": [0, 100], "centre_ratio": 0.5} for b in ("mobile", "tablet", "desktop")}
    between = {str(w): {"text_overlaps": between_overlaps, "overflow_px": 0, "max_vertical_gap": 10, "viewport_h": 800,
                        "background_covers": True, "content": [0, 100], "centre_ratio": 0.5} for w in (360, 375, 500, 1024, 1600)}
    return {"breakpoints": bps, "between": between}


def test_overlaps_already_in_the_design_size_are_not_failures():
    r = fluidity.report(checks(3, 3))
    assert r["pass"] and r["widths"][360]["overlaps"] == 0


def test_new_overlaps_between_sizes_still_fail():
    r = fluidity.report(checks(3, 5))
    assert not r["pass"] and 360 in r["fails"] and r["widths"][360]["overlaps"] == 2


def test_our_renders_unchanged_any_overlap_fails():
    r = fluidity.report(checks(0, 1))
    assert not r["pass"] and r["widths"][1600]["overlaps"] == 1
