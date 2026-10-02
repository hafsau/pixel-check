"""orchestrator/states.state_diff: what an interaction changes between a base frame and a state frame.
Written before the implementation (TDD, Oct 2)."""
import json
from pathlib import Path

import pytest

from orchestrator.states import state_diff

ROOT = Path(__file__).resolve().parents[1]
W, H = 390, 844


def frame(texts=(), blocks=()):
    return {"size": [W, H], "background": "#000000",
            "texts": [{"text": t, "box": list(b), "size_px": 16, "color": "#ffffff"} for t, b in texts],
            "blocks": [{"box": list(b), "fill": f} for b, f in blocks]}


def names(items):
    return sorted(x["text"] for x in items)


def test_identical_frames_change_nothing():
    f = frame([("Home", (20, 20, 60, 16)), ("About", (100, 20, 60, 16))], [((0, 0, 390, 60), "#111111")])
    d = state_diff(f, f)
    assert d["appeared"]["texts"] == [] and d["disappeared"]["texts"] == [] and d["moved"] == []
    assert names(d["persisted"]["texts"]) == ["About", "Home"]
    assert d["appeared"]["blocks"] == [] and d["disappeared"]["blocks"] == []


def test_new_text_appears():
    base = frame([("Home", (20, 20, 60, 16))])
    state = frame([("Home", (20, 20, 60, 16)), ("Pricing", (20, 100, 70, 16))])
    d = state_diff(base, state)
    assert names(d["appeared"]["texts"]) == ["Pricing"]


def test_moved_text_is_not_appeared():
    base = frame([("Home", (20, 20, 60, 16))])
    state = frame([("Home", (20, 120, 60, 16))])
    d = state_diff(base, state)
    assert d["appeared"]["texts"] == [] and d["disappeared"]["texts"] == []
    assert [m["text"] for m in d["moved"]] == ["Home"]


def test_small_jitter_is_persisted_not_moved():
    base = frame([("Home", (20, 20, 60, 16))])
    state = frame([("Home", (22, 21, 60, 16))])
    d = state_diff(base, state)
    assert d["moved"] == [] and names(d["persisted"]["texts"]) == ["Home"]


def test_covered_content_disappears():
    base = frame([("Hero title", (20, 200, 300, 40)), ("Logo", (20, 20, 60, 16))])
    state = frame([("Logo", (20, 20, 60, 16)), ("Menu item", (20, 100, 100, 16))])
    d = state_diff(base, state)
    assert names(d["disappeared"]["texts"]) == ["Hero title"]


def test_duplicate_strings_matched_by_position():
    base = frame([("Item", (20, 100, 40, 16)), ("Item", (20, 200, 40, 16))])
    state = frame([("Item", (20, 100, 40, 16)), ("Item", (20, 200, 40, 16)), ("Item", (20, 300, 40, 16))])
    d = state_diff(base, state)
    assert len(d["appeared"]["texts"]) == 1 and d["appeared"]["texts"][0]["box"][1] == 300


def test_block_appears_and_disappears():
    base = frame(blocks=[((0, 0, 390, 60), "#111111"), ((20, 300, 350, 48), "#e50914")])
    state = frame(blocks=[((0, 0, 390, 60), "#111111"), ((0, 60, 390, 784), "#000000")])
    d = state_diff(base, state)
    assert [b["box"] for b in d["appeared"]["blocks"]] == [[0, 60, 390, 784]]
    assert [b["box"] for b in d["disappeared"]["blocks"]] == [[20, 300, 350, 48]]


def test_kind_overlay_full_width_panel():
    base = frame([("Logo", (20, 20, 60, 16)), ("Hero", (20, 300, 300, 40))])
    state = frame([("Logo", (20, 20, 60, 16))] + [(f"Link {i}", (20, 100 + 40 * i, 120, 16)) for i in range(5)],
                  [((0, 70, 390, 774), "#0b0b0b")])
    d = state_diff(base, state)
    assert d["kind"] == "overlay"
    assert d["panel"][2] >= 0.85 * W


def test_kind_drawer_side_panel():
    base = frame([("Logo", (20, 20, 60, 16)), ("Hero", (20, 300, 300, 40))])
    state = frame([("Logo", (20, 20, 60, 16)), ("Hero", (20, 300, 300, 40))] +
                  [(f"Link {i}", (150, 40 + 30 * i, 120, 16)) for i in range(6)],
                  [((140, 0, 250, 844), "#ffffff")])
    d = state_diff(base, state)
    assert d["kind"] == "drawer"
    assert d["panel"][0] >= 0.3 * W and d["panel"][3] >= 0.8 * H


def test_kind_inline_expansion():
    base = frame([("Question", (20, 300, 200, 16)), ("Next question", (20, 340, 200, 16))])
    state = frame([("Question", (20, 300, 200, 16)), ("The answer text", (20, 330, 300, 16)),
                   ("Next question", (20, 370, 200, 16))])
    d = state_diff(base, state)
    assert d["kind"] == "inline"
    assert names(d["appeared"]["texts"]) == ["The answer text"]
    assert [m["text"] for m in d["moved"]] == ["Next question"]


def test_no_change_has_no_panel():
    f = frame([("Home", (20, 20, 60, 16))])
    d = state_diff(f, f)
    assert d["kind"] == "none" and d["panel"] is None


DEV = ROOT / "benchmarks-dev" / "lambda-lx"


@pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_real_lambda_mobile_menu():
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from oracle_spec import frame as oracle_frame
    base = oracle_frame("lambda-lx", "mobile")
    state = oracle_frame("lambda-lx", "mobile", state="menu")
    d = state_diff(base, state)
    got = {t["text"] for t in d["appeared"]["texts"]}
    assert {"AI FACTORIES", "PRODUCTS", "PRICING", "COMPANY"} <= got
    gone = {t["text"] for t in d["disappeared"]["texts"]}
    assert any("Supercomputers" in t for t in gone) and "LAUNCH GPU INSTANCE" in gone
    assert d["kind"] == "overlay"
