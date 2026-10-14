"""Check diagnostics (Oct 13, council on the Lovable build): explain a check's score without changing it.
- text the scorer could not credit is missing, moved (how far), below the first screen, or there but unreadable
- drift profile: vertical offset band by band and the page's vertical scale (one global alignment cannot absorb it)
- named differences: font family, text size
- points lost per factor, summing to 100 − score
Written before orchestrator/diagnose.py (TDD)."""
import numpy as np
import pytest

from orchestrator import diagnose as D

VIEW = (400, 800)


def dom(text, x, y, w=120, h=20, size="16px", family="Roboto"):
    return {"text": text, "box": [x, y, w, h], "font_size": size, "font_family": family}


# ---------------------------------------------------------------- text status

def test_text_absent_from_the_build_is_missing():
    out = D.text_status(["time logged"], [{"text": "Time Logged", "box": [20, 600, 120, 20]}], [dom("Workouts", 20, 100)], VIEW)
    assert out == [{"text": "time logged", "status": "missing"}]


def test_text_elsewhere_on_the_first_screen_is_moved_with_its_distance():
    out = D.text_status(["1h 20m"], [{"text": "1h 20m", "box": [20, 600, 100, 40]}], [dom("1h 20m", 20, 450, 100, 40)], VIEW)
    assert out == [{"text": "1h 20m", "status": "moved", "dy": -150, "dx": 0}]


def test_text_pushed_past_the_first_screen_is_below():
    out = D.text_status(["minutes moved each day"], [{"text": "Minutes moved each day", "box": [20, 760, 200, 20]}],
                        [dom("Minutes moved each day", 20, 830, 200, 20)], VIEW)
    assert out == [{"text": "minutes moved each day", "status": "below", "dy": 70, "dx": 0}]


def test_text_near_its_spot_but_not_credited_is_unreadable():
    """e.g. covered by a platform badge or too faint: the scorer only credits readable text"""
    out = D.text_status(["weekly activity"], [{"text": "Weekly Activity", "box": [20, 700, 150, 20]}],
                        [dom("Weekly Activity", 24, 710, 150, 20)], VIEW)
    assert out == [{"text": "weekly activity", "status": "unreadable"}]


def test_the_nearest_copy_is_used_and_short_words_match_whole_words():
    d = [dom("Days left", 20, 100), dom("4 Days", 20, 500), dom("Sundays", 20, 520)]
    out = D.text_status(["days"], [{"text": "Days", "box": [60, 640, 60, 30]}], d, VIEW)
    assert out[0]["status"] == "moved" and out[0]["dy"] == 500 + 10 - (640 + 15)


def test_text_without_a_design_box_found_in_the_build_is_moved_without_distance():
    out = D.text_status(["streak"], [], [dom("Streak", 20, 100)], VIEW)
    assert out == [{"text": "streak", "status": "moved"}]


def test_no_missing_text_no_status():
    assert D.text_status([], [{"text": "A", "box": [0, 0, 1, 1]}], [], VIEW) == []


# ---------------------------------------------------------------- drift profile

def _page(h=800, w=400, rows=8, scale=1.0, shift=0):
    """White page with dark bars of varied widths every 100 px (scaled / shifted vertically)."""
    a = np.full((h, w, 3), 255, np.uint8)
    for i in range(rows):
        y = int(round((40 + i * 100) * scale)) + shift
        if 0 <= y < h - 24:
            a[y:y + 24, 30:30 + 40 * (i % 5 + 2)] = 30
            a[y + 4:y + 12, 300:300 + 10 * (i % 3 + 1)] = 120
    return a


def test_identical_pages_have_no_drift():
    out = D.drift(_page(), _page())
    assert out["scale"] == pytest.approx(1.0, abs=0.01)
    assert all(abs(b["dy"]) <= 2 for b in out["bands"] if b["dy"] is not None)


def test_a_uniform_shift_is_the_same_in_every_band_and_scale_one():
    out = D.drift(_page(), _page(shift=20))
    dys = [b["dy"] for b in out["bands"] if b["dy"] is not None]
    assert len(dys) >= 4 and all(abs(d - 20) <= 3 for d in dys)
    assert out["scale"] == pytest.approx(1.0, abs=0.02)


@pytest.mark.parametrize("scale", [0.85, 1.06])
def test_a_stretched_or_compressed_page_drifts_more_down_the_page(scale):
    out = D.drift(_page(), _page(scale=scale))
    dys = [b["dy"] for b in out["bands"] if b["dy"] is not None]
    assert len(dys) >= 3
    assert (dys[-1] < dys[0]) if scale < 1 else (dys[-1] > dys[0])
    assert out["scale"] == pytest.approx(scale, abs=0.03)


def test_blank_bands_have_no_drift_reading():
    a = _page()
    a[400:] = 255
    out = D.drift(a, a.copy())
    assert any(b["dy"] is None for b in out["bands"])


def test_drift_needs_same_size_images():
    assert D.drift(_page(), _page(h=700)) is None


# ---------------------------------------------------------------- named differences

def test_font_family_mismatch_is_named():
    d = [dom("Welcome back", 0, 0, family="Roboto"), dom("Keep the momentum going", 0, 30, family="Roboto"), dom("x", 0, 60, family="Inter")]
    assert D.font_finding({"body": "Lato"}, d) == {"design": "Lato", "build": "Roboto"}


def test_same_font_or_unknown_design_font_names_nothing():
    d = [dom("Welcome back", 0, 0, family="Lato")]
    assert D.font_finding({"body": "lato"}, d) is None
    assert D.font_finding(None, d) is None
    assert D.font_finding({"body": "Lato"}, []) is None


def test_text_size_ratio_is_the_median_over_matched_texts():
    design = [{"text": "Welcome back", "box": [0, 0, 1, 1], "size_px": 24}, {"text": "Workouts", "box": [0, 0, 1, 1], "size_px": 13},
              {"text": "Current Streak", "box": [0, 0, 1, 1], "size_px": 18}, {"text": "Nowhere", "box": [0, 0, 1, 1], "size_px": 30}]
    d = [dom("Welcome back", 0, 0, size="20px"), dom("Workouts", 0, 0, size="11px"), dom("Current Streak", 0, 0, size="15px")]
    assert D.text_size_ratio(design, d) == pytest.approx(0.83, abs=0.01)


def test_text_size_needs_three_matches():
    design = [{"text": "Welcome back", "box": [0, 0, 1, 1], "size_px": 24}]
    assert D.text_size_ratio(design, [dom("Welcome back", 0, 0, size="20px")]) is None


# ---------------------------------------------------------------- points lost

def test_points_lost_split_the_gap_to_100_and_sum_to_it():
    """mobile of the Lovable check: 38.49 = 100 × colour .8117 × text .9167 × spatial .5172"""
    bp = {"score": 38.49, "components": {"structure": 0.4782, "layout": 0.569, "text": 0.8333, "color": 0.7489},
          "weights": {"structure": 0.57, "layout": 0.43}, "offset_px": [0, 0]}
    out = D.points_lost(bp)
    assert set(out) == {"layout", "color", "text", "offset"}
    assert sum(out.values()) == pytest.approx(100 - 38.49, abs=0.05)
    assert out["layout"] > out["color"] > out["text"] > 0 and out["offset"] == 0
    assert str(out["offset"]) == "0.0"


def test_points_lost_include_the_alignment_shift():
    bp = {"score": 64.54, "components": {"structure": 0.7596, "layout": 0.7939, "text": 1.0, "color": 0.88},
          "weights": {"structure": 0.57, "layout": 0.43}, "offset_px": [-14, 0]}
    out = D.points_lost(bp)
    assert out["text"] == 0 and out["offset"] > 0
    assert sum(out.values()) == pytest.approx(100 - 64.54, abs=0.05)


def test_points_lost_without_text_comparison_and_bad_input():
    bp = {"score": 80.0, "components": {"structure": 0.9, "layout": 0.9, "color": 0.95}, "offset_px": [0, 0]}
    assert D.points_lost(bp)["text"] == 0
    assert D.points_lost({"score": 0.0, "error": "size mismatch"}) is None
    assert D.points_lost({"score": 100.0, "components": {"structure": 1, "layout": 1, "color": 1}}) == {"layout": 0, "color": 0, "text": 0, "offset": 0}


# ---------------------------------------------------------------- one call per check

def test_diagnose_builds_a_section_per_size():
    rep = {"breakpoints": {"mobile": {"score": 38.49, "missing_text": ["1h 20m"], "offset_px": [0, 0],
                                      "components": {"structure": 0.4782, "layout": 0.569, "text": 0.8333, "color": 0.7489}}}}
    pg = _page()
    out = D.diagnose(rep, frames={"mobile": pg}, build={"mobile": _page(shift=10)},
                     design_texts={"mobile": [{"text": "1h 20m", "box": [20, 600, 100, 40], "size_px": 40}]},
                     dom={"mobile": [dom("1h 20m", 20, 450, 100, 40, size="32px")]}, fonts={"body": "Lato"})
    m = out["mobile"]
    assert m["text"] == [{"text": "1h 20m", "status": "moved", "dy": -150, "dx": 0}]
    assert m["drift"]["bands"] and m["lost"]["layout"] > 0
    assert m["font"] == {"design": "Lato", "build": "Roboto"}
    assert "tablet" not in out


def test_diagnose_never_fails_the_check():
    """diagnostics are extras: broken input yields nothing, not an exception"""
    assert D.diagnose({"breakpoints": {"mobile": "junk"}}, frames={}, build={}, design_texts={}, dom={}, fonts=None) == {}
