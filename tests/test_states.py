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


def test_trigger_icon_swap_is_not_panel_content():
    """Hamburger → X inside the trigger area is the trigger's open look, not part of the opened panel
    (lambda: counting the X made the panel start at y=33 and the overlay hid the logo)."""
    bars = [((343, 41 + 8 * i, 24, 2), "#e7e6d9") for i in range(3)]
    base = frame([("Logo", (20, 40, 60, 16)), ("Hero", (20, 300, 300, 40))], bars)
    x_icon = [((344, 38, 22, 22), "#e7e6d9")]
    links = [(f"Link {i}", (20, 140 + 40 * i, 120, 16)) for i in range(4)]
    state = frame([("Logo", (20, 40, 60, 16))] + links, x_icon + [((0, 100, 390, 744), "#0b0b0b")])
    d = state_diff(base, state, trigger_box=[335, 33, 40, 34])
    assert [b["box"] for b in d["trigger_changes"]["appeared"]["blocks"]] == [[344, 38, 22, 22]]
    assert len(d["trigger_changes"]["disappeared"]["blocks"]) == 3
    assert d["panel"][1] == 100, "panel starts below the header"
    assert all(b["box"] != [344, 38, 22, 22] for b in d["appeared"]["blocks"])


def test_trigger_box_optional_and_far_away_changes_unaffected():
    base = frame([("Logo", (20, 40, 60, 16))])
    state = frame([("Logo", (20, 40, 60, 16)), ("Link", (20, 200, 60, 16))])
    d = state_diff(base, state, trigger_box=[335, 33, 40, 34])
    assert [t["text"] for t in d["appeared"]["texts"]] == ["Link"]
    assert d["trigger_changes"]["appeared"]["texts"] == [] and d["trigger_changes"]["appeared"]["blocks"] == []


VDEV = ROOT / "benchmarks-dev" / "vercel-pricing-lx"


@pytest.mark.skipif(not (VDEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_oracle_state_frame_has_only_painted_text():
    """Closed <details> content has real boxes and passes every style check but is not painted (vercel's mobile
    menu: "Agent Stack", "AI SDK" leaked into the oracle). Visibility = the element's own colour shows up in a
    colour-coded screenshot."""
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from oracle_spec import frame as oracle_frame
    st = oracle_frame("vercel-pricing-lx", "mobile", state="menu")
    texts = {t["text"] for t in st["texts"]}
    assert {"Products", "Resources", "Enterprise", "Pricing", "Get a Demo", "Log In", "Sign Up"} <= texts
    assert not ({"Agent Stack", "AI SDK", "Learn", "Docs"} & texts), texts


@pytest.mark.skipif(not (VDEV / "mobile.menu.text.json").exists(), reason="dev state capture not present")
def test_state_ground_truth_text_is_visible_only():
    import json as _j
    gt = {t["text"] for t in _j.loads((VDEV / "mobile.menu.text.json").read_text())}
    assert "Agent Stack" not in gt and "Products" in gt


def _imgs(dim=None, panel=(368, 100, 400, 924), seed=0):
    import numpy as np
    rng = np.random.default_rng(seed)
    base = np.full((1024, 768, 3), 11.0)
    base[150:500, 20:700] = rng.integers(120, 255, size=(350, 680, 3))   # bright page content
    state = base.copy()
    if dim is not None:                   # the page below the header is dimmed; the header stays (as on lambda)
        state[100:] = state[100:] * (1 - dim)
    x, y, w, h = panel
    state[y:y + h, x:x + w] = 11.0                                    # the drawer itself
    return base, state


def test_backdrop_detected_with_opacity():
    from orchestrator.states import backdrop
    base, state = _imgs(dim=0.6)
    b = backdrop(base, state, [368, 100, 400, 924])
    assert b is not None and b["color"] == "#000000" and abs(b["opacity"] - 0.6) < 0.05


def test_no_backdrop_when_page_unchanged():
    from orchestrator.states import backdrop
    base, state = _imgs(dim=None)
    assert backdrop(base, state, [368, 100, 400, 924]) is None


def test_backdrop_ignores_the_panel_area():
    from orchestrator.states import backdrop
    base, state = _imgs(dim=None, panel=(0, 100, 768, 924))   # full-width panel: nothing outside to compare
    assert backdrop(base, state, [0, 100, 768, 924]) is None


def test_backdrop_area_excludes_undimmed_header():
    import numpy as np
    from orchestrator.states import backdrop
    base, state = _imgs(dim=0.6)
    base[10:60, 20:300] = 200
    state[10:60, 20:300] = 200            # header above the backdrop stays bright
    b = backdrop(base, state, [368, 100, 400, 924])
    assert b is not None and b["box"][1] >= 100 and b["box"][1] <= 160


def test_backdrop_ignores_trigger_area_and_spans_viewport():
    from orchestrator.states import backdrop
    base, state = _imgs(dim=0.6)
    base[41:59, 721:745] = 230             # hamburger bars that turn into an X
    state[41:59, 721:745] = 11
    b = backdrop(base, state, [368, 100, 400, 924], exclude=[[713, 33, 40, 34]])
    assert b["box"][0] == 0 and b["box"][2] == 768 and b["box"][1] >= 100
    assert b["box"][1] + b["box"][3] == 1024


def test_opaque_full_screen_cover_is_not_dimming():
    """A full-screen menu of the page colour over bright content looks like 'ratio ≈ 0.05' on the bright pixels, but the
    page background is unchanged — that is a cover, not a backdrop (lambda mobile)."""
    import numpy as np
    from orchestrator.states import dim_region
    rng = np.random.default_rng(2)
    base = np.full((844, 390, 3), 11.0)
    base[200:400, 20:370] = rng.integers(120, 255, size=(200, 350, 3))
    state = base.copy()
    state[100:] = 11.0                       # opaque panel, same colour as the page
    assert dim_region(base, state) is None


def test_white_page_dimmed_is_dimming():
    import numpy as np
    from orchestrator.states import dim_region
    rng = np.random.default_rng(3)
    base = np.full((1024, 768, 3), 255.0)
    base[200:400, 20:700] = rng.integers(0, 140, size=(200, 680, 3))
    state = base.copy()
    state[100:] = state[100:] * 0.5
    state[100:, 400:] = 255.0                # white drawer
    d = dim_region(base, state)
    assert d is not None and abs(d["opacity"] - 0.5) < 0.06 and d["undimmed"][0] >= 380


def _trigger_imgs(state_draw):
    import numpy as np
    base = np.full((100, 390, 3), 11.0)
    for i in range(3):                              # hamburger bars at x 343..367
        base[41 + 8 * i:43 + 8 * i, 343:367] = 231
    state = np.full((100, 390, 3), 11.0)
    state_draw(state)
    return base, state


def test_trigger_look_detects_an_x():
    import numpy as np
    from orchestrator.states import trigger_look

    def draw_x(img):
        for k in range(20):
            img[39 + k, 345 + k] = 231
            img[39 + k, 364 - k] = 231
    base, state = _trigger_imgs(draw_x)
    look = trigger_look(base, state, [335, 33, 40, 34])
    assert look and look["shape"] == "x" and look["fill"].startswith("#e")
    assert 8 <= look["box"][0] <= 12 and look["box"][2] >= 18      # relative to the trigger box


def test_trigger_look_none_when_unchanged():
    import numpy as np
    from orchestrator.states import trigger_look
    base, state = _trigger_imgs(lambda img: None)
    base2 = base.copy()
    assert trigger_look(base, base2, [335, 33, 40, 34]) is None


def test_trigger_look_unknown_shape():
    from orchestrator.states import trigger_look

    def draw_ring(img):              # an outline (not a solid block, not an X) — a solid dot is now a "block"
        img[44:56, 349:361] = 231
        img[46:54, 351:359] = img[40, 340]
    base, state = _trigger_imgs(draw_ring)
    look = trigger_look(base, state, [335, 33, 40, 34])
    assert look and look["shape"] == "unknown"


# Gate B: a drawer over a blurred, whitened page (lennysjobs mobile menu) — dim_region finds nothing (blur is not a
# constant darkening), perception reads the blurred page as new items, the kind came out "inline"
def _veiled(sigma=8, a=0.4, colour=(255, 255, 255), x0=110):
    import numpy as np
    from scipy import ndimage
    rng = np.random.default_rng(3)
    H, W = 844, 390
    base = ndimage.gaussian_filter(rng.uniform(0, 255, (H, W, 3)), (3, 3, 0))
    base[200:260, 20:360] = 30                                   # a headline-like dark bar
    blurred = ndimage.gaussian_filter(base, (sigma, sigma, 0)) if sigma else base
    state = a * np.array(colour, float) + (1 - a) * blurred
    state[:, x0:] = 255                                          # the drawer surface
    for i in range(6):
        state[54 + 44 * i:70 + 44 * i, x0 + 8:x0 + 8 + 90] = 20  # its menu labels
    return base.clip(0, 255).astype(np.uint8), state.clip(0, 255).astype(np.uint8)


def test_panel_surface_finds_the_drawer():
    from orchestrator.states import panel_surface
    b, s = _veiled()
    r = panel_surface(b, s)
    assert r and abs(r["box"][0] - 110) <= 2 and r["box"][0] + r["box"][2] >= 388
    assert r["box"][1] <= 2 and r["box"][3] >= 840 and r["fill"] == "#ffffff"


def test_panel_surface_none_without_a_new_uniform_region():
    import numpy as np
    from orchestrator.states import panel_surface
    b, _ = _veiled()
    assert panel_surface(b, b.copy()) is None
    s = b.copy()
    s[300:320, 20:200] = 250                                      # a small new bar is not a panel surface
    assert panel_surface(b, s) is None


def test_panel_surface_rejects_a_frame_wide_uniform_region():
    """lambda's tablet drawer: dark panel over a page dimmed to near-black — both look uniform → no surface claimed
    (the dimming path handles it)."""
    import numpy as np
    from orchestrator.states import panel_surface
    b = np.full((1024, 768, 3), 11, np.uint8)
    b[200:260, 20:700] = 200
    s = np.full_like(b, 11)
    assert panel_surface(b, s) is None


@pytest.mark.parametrize("sigma,a", [(8, 0.4), (0, 0.6), (16, 0.3)])
def test_backdrop_fit_recovers_colour_opacity_and_blur(sigma, a):
    import numpy as np
    from orchestrator.states import backdrop_fit
    b, s = _veiled(sigma=sigma, a=a)
    r = backdrop_fit(b, s, [110, 0, 280, 844])
    assert r and abs(r["opacity"] - a) <= 0.06, r
    c = [int(r["color"][i:i + 2], 16) for i in (1, 3, 5)]
    assert all(abs(v - 255) <= 16 for v in c), r
    assert abs(r["blur"] - sigma) <= max(3, 0.25 * sigma), r
    assert r["box"] == [0, 0, 110, 844]


def test_backdrop_fit_none_when_the_page_is_unchanged():
    from orchestrator.states import backdrop_fit
    b, _ = _veiled()
    s = b.copy()
    s[:, 110:] = 255
    assert backdrop_fit(b, s, [110, 0, 280, 844]) is None


def test_panel_surface_bridges_dense_text_rows():
    """lennysjobs: a row of wide menu labels is < 60 % panel colour; the surface still spans the drawer's height."""
    from orchestrator.states import panel_surface
    b, s = _veiled()
    for i in range(6):
        s[54 + 44 * i:72 + 44 * i, 118:380] = 20                # labels nearly as wide as the drawer
    r = panel_surface(b, s)
    assert r and r["box"][1] <= 2 and r["box"][3] >= 840, r


@pytest.mark.parametrize("panel,kind", [([99, 0, 291, 844], "drawer"), ([0, 0, 300, 844], "drawer"),
                                        ([368, 100, 400, 924], "drawer"), ([0, 100, 390, 744], "overlay"),
                                        ([20, 438, 262, 43], "inline"), ([60, 0, 270, 844], "inline")])
def test_classify_wide_drawer_touching_one_edge(panel, kind):
    from orchestrator.states import classify
    W, H = (768, 1024) if panel[0] == 368 else (390, 844)
    assert classify(panel, W, H) == kind


def test_trigger_look_solid_block():
    """vercel / lennysjobs: the open icon is media → a solid grey placeholder block in the state frame (wider than the
    closed one, or the drawer's close icon drawn over the trigger)."""
    import numpy as np
    from orchestrator.states import trigger_look
    base = np.full((844, 390, 3), 250, np.uint8)
    base[20:44, 342:366] = 212                       # closed: 24 × 24 placeholder
    state = base.copy()
    state[20:44, 342:366] = 250
    state[26:38, 330:378] = 212                      # open: 48 × 12 placeholder
    look = trigger_look(base, state, [332, 10, 44, 44])
    assert look["shape"] == "block" and look["box"] == [0, 16, 44, 12], look
    assert look["fill"] == "#d4d4d4" and look["trigger_size"] == [44, 44]
