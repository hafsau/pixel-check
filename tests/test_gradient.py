"""Gradients (Oct 12, Hafsa's dashboard): a blue→purple banner was measured as a dozen 7–30 px strips of slightly
different blues, and the compiler laid the text into the strips (match 6.3). A smooth region whose colour runs from
one side to the other is ONE block with a gradient → `bg-gradient-to-r from-[…] to-[…]` (lint allows gradients;
the mean colour stays as the fallback fill). Written before the code (TDD)."""
import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from orchestrator import measure

ROOT = Path(__file__).resolve().parents[1]
BG = (244, 245, 251)


def page(direction="r", via=False):
    w, h = 800, 400
    a = np.zeros((h, w, 3), np.uint8)
    a[:] = BG
    x0, y0, bw, bh = 40, 60, 700, 120
    t = (np.arange(bw) / (bw - 1))[None, :, None] if direction == "r" else (np.arange(bh) / (bh - 1))[:, None, None]
    start, end = np.array([59, 108, 255]), np.array([138, 63, 252])
    if via:                                      # blue → purple → blue (Hafsa's banner)
        t = 1 - np.abs(2 * t - 1)
    band = start + (end - start) * t
    a[y0:y0 + bh, x0:x0 + bw] = np.broadcast_to(band, (bh, bw, 3)).astype(np.uint8)
    im = Image.fromarray(a)
    d = ImageDraw.Draw(im)
    d.rectangle([80, 100, 380, 130], fill=(255, 255, 255))          # a white label inside the banner
    d.rectangle([40, 260, 240, 310], fill=(37, 99, 235))            # a solid button
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue(), (x0, y0, bw, bh)


def _iou(a, b):
    return measure._iou(a, b)


@pytest.mark.parametrize("direction", ["r", "b"])
def test_a_smooth_gradient_is_one_block(direction):
    png, box = page(direction)
    blocks = measure.measure(png)["blocks"]
    grads = [b for b in blocks if b.get("gradient")]
    assert len(grads) == 1, [(b["box"], b.get("fill")) for b in blocks]
    g = grads[0]
    assert _iou(g["box"], box) >= 0.9 and g["gradient"]["dir"] == direction
    f, t = g["gradient"]["from"], g["gradient"]["to"]
    hexrgb = lambda h: np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)])
    assert np.abs(hexrgb(f) - [59, 108, 255]).max() <= 16 and np.abs(hexrgb(t) - [138, 63, 252]).max() <= 16
    # no strips left inside the banner (the white label may stay)
    inside = [b for b in blocks if b is not g and measure._frac_inside(b["box"], g["box"]) >= 0.8
              and b.get("fill") not in ("#ffffff",)]
    assert not inside, [(b["box"], b["fill"]) for b in inside]
    # the solid button stays a solid block
    btn = [b for b in blocks if _iou(b["box"], [40, 260, 201, 51]) >= 0.8]
    assert btn and not btn[0].get("gradient")


def test_a_three_stop_gradient_keeps_its_middle_colour():
    png, box = page("r", via=True)
    g = [b for b in measure.measure(png)["blocks"] if b.get("gradient")]
    assert len(g) == 1 and _iou(g[0]["box"], box) >= 0.9
    hexrgb = lambda h: np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)])
    gr = g[0]["gradient"]
    assert np.abs(hexrgb(gr["via"]) - [138, 63, 252]).max() <= 16
    assert np.abs(hexrgb(gr["from"]) - [59, 108, 255]).max() <= 16 and np.abs(hexrgb(gr["to"]) - [59, 108, 255]).max() <= 16


def test_the_compiler_writes_gradient_classes_with_a_fallback_fill():
    from orchestrator.fluid import _fill
    at = {bp: {"fill": "#6a55fd", "gradient": {"dir": "r", "from": "#3b6cff", "to": "#8a3ffc"}} for bp in
          ("mobile", "tablet", "desktop")}
    cls = _fill(at).split()
    assert {"bg-[#6a55fd]", "bg-gradient-to-r", "from-[#3b6cff]", "to-[#8a3ffc]"} <= set(cls)
    at3 = {bp: {"fill": "#6a55fd", "gradient": {"dir": "r", "from": "#3b6cff", "via": "#8a3ffc", "to": "#3b6cff"}}
           for bp in ("mobile", "tablet", "desktop")}
    assert "via-[#8a3ffc]" in _fill(at3).split()
    plain = {bp: {"fill": "#ffffff"} for bp in ("mobile", "tablet", "desktop")}
    assert _fill(plain) == "bg-[#ffffff]"                              # unchanged without gradients


@pytest.mark.skipif(not (ROOT / "benchmarks" / "desktop.png").exists(), reason="Hafsa's screens not present")
def test_hafsas_focus_banner_is_one_gradient_block():
    png = (ROOT / "benchmarks" / "desktop.png").read_bytes()
    blocks = measure.measure(png)["blocks"]
    banner = [b for b in blocks if b.get("gradient") and _iou(b["box"], [24, 157, 1023, 104]) >= 0.8]
    assert banner, [(b["box"], b.get("fill"), b.get("gradient")) for b in blocks if b["box"][1] < 300]
    strips = [b for b in blocks if b is not banner[0] and measure._frac_inside(b["box"], banner[0]["box"]) >= 0.8
              and b["box"][3] >= 80]
    assert not strips, [(b["box"], b["fill"]) for b in strips]


@pytest.mark.skipif(not (ROOT / "benchmarks" / "desktop.png").exists(), reason="Hafsa's screens not present")
def test_white_cards_on_a_light_page_are_blocks():
    """The page is #f4f6fa and its white cards cover more area than it: the most frequent colour was the cards,
    so they were 'background' and vanished. The page colour is read from the frame's side margins."""
    img = np.asarray(Image.open(ROOT / "benchmarks" / "desktop.png").convert("RGB"), dtype=np.float32)
    assert np.abs(measure.background(img) - [244, 246, 250]).max() <= 4
    blocks = measure.measure((ROOT / "benchmarks" / "desktop.png").read_bytes())["blocks"]
    cards = [b for b in blocks if b.get("fill") in ("#ffffff", "#fefefe", "#fdfdfd") and b["box"][2] >= 200 and b["box"][3] >= 60]
    assert len(cards) >= 6, [(b["box"], b["fill"]) for b in blocks if b["box"][2] >= 150]


def test_a_page_whose_margins_are_its_colour_keeps_it():
    a = np.full((400, 600, 3), 255, np.float32)            # white page, a big grey panel in the middle
    a[50:350, 100:500] = (230, 230, 230)
    assert np.abs(measure.background(a) - 255).max() <= 1


def test_a_soft_glow_is_not_a_block_but_a_faint_card_with_an_edge_is():
    """The dashboard's header glow (a lavender haze fading into the page) was quantised into pale overlapping boxes
    that pushed the header down ~130 px. A faint box with no edge on any side is a glow; a white card on a light
    page has a crisp edge (border / shadow)."""
    h, w = 500, 800
    yy, xx = np.mgrid[0:h, 0:w]
    a = np.zeros((h, w, 3), np.float32)
    a[:] = (244, 246, 250)
    glow = np.exp(-(((xx - 120) / 160) ** 2 + ((yy - 60) / 90) ** 2))[..., None]
    a = a + glow * (np.array([226, 230, 252]) - a)                  # a lavender haze, no edges
    a[260:400, 60:360] = 255                                        # a white card…
    a[259, 60:360] = a[400, 60:360] = a[260:400, 59] = a[260:400, 360] = (229, 231, 235)   # …with a 1 px border
    buf = io.BytesIO()
    Image.fromarray(a.clip(0, 255).astype(np.uint8)).save(buf, "PNG")
    blocks = measure.measure(buf.getvalue())["blocks"]
    assert not [b for b in blocks if b["box"][1] < 220], [(b["box"], b["fill"]) for b in blocks]
    assert [b for b in blocks if _iou(b["box"], [60, 260, 300, 140]) >= 0.8]


def test_a_full_width_light_band_stays_a_block():
    a = np.full((500, 800, 3), 255, np.float32)
    a[300:420, :] = (238, 240, 244)                     # a light-grey footer band, edge to edge
    buf = io.BytesIO()
    Image.fromarray(a.astype(np.uint8)).save(buf, "PNG")
    blocks = measure.measure(buf.getvalue())["blocks"]
    assert [b for b in blocks if _iou(b["box"], [0, 300, 800, 120]) >= 0.8], [(b["box"], b["fill"]) for b in blocks]


def test_an_edge_to_edge_gradient_band_is_a_section_background_not_a_block():
    """lennysjobs (Oct 12): its full-width peach hero became one gradient block that swallowed the section's layout
    (6.2 vs 16.2 without). A band spanning the frame stays with the band-background handling."""
    h, w = 500, 400
    a = np.full((h, w, 3), 255, np.float32)
    t = (np.arange(300) / 299)[:, None, None]
    a[60:360] = np.array([253, 217, 189]) + (np.array([252, 170, 120]) - np.array([253, 217, 189])) * t
    buf = io.BytesIO()
    Image.fromarray(a.astype(np.uint8)).save(buf, "PNG")
    assert not [b for b in measure.measure(buf.getvalue())["blocks"] if b.get("gradient")]


def test_a_rounded_gradient_banner_keeps_its_radius():
    png, box = page("r", via=True)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    a = np.asarray(im).copy()
    x0, y0, bw, bh = box
    r = 16
    for (cx, cy) in ((x0 + r, y0 + r), (x0 + bw - r - 1, y0 + r), (x0 + r, y0 + bh - r - 1), (x0 + bw - r - 1, y0 + bh - r - 1)):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                inside_corner = (xx < x0 + r or xx > x0 + bw - r - 1) and (yy < y0 + r or yy > y0 + bh - r - 1)
                if inside_corner and (xx - cx) ** 2 + (yy - cy) ** 2 > r * r:
                    a[yy, xx] = BG
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, "PNG")
    g = [b for b in measure.measure(buf.getvalue())["blocks"] if b.get("gradient")]
    assert g and 12 <= (g[0].get("radius") or 0) <= 20, g


def test_haze_strips_of_slightly_different_heights_are_one_run():
    from orchestrator.measure import _haze_runs
    bg = np.array([244, 246, 250], float)
    blocks = [{"box": [10, 133, 139, 27], "fill": "#d7e0fb"}, {"box": [134, 133, 63, 24], "fill": "#dddff9"},
              {"box": [190, 133, 57, 24], "fill": "#e0e6fa"}, {"box": [241, 133, 44, 24], "fill": "#ebecf9"}]
    assert _haze_runs(blocks, bg) == {0, 1, 2, 3}


def test_small_steep_gradient_tiles_round_avatars_and_thin_bars_are_found():
    """Dashboard: 53 px gradient achievement tiles, a 56 px gradient avatar circle and 16 px chart bars whose colour
    barely changes were all missing."""
    a = np.full((300, 600, 3), 255, np.float32)
    t = (np.arange(53) / 52)[None, :, None]
    a[40:93, 40:93] = np.array([254, 112, 17]) + (np.array([253, 70, 40]) - np.array([254, 112, 17])) * t   # tile
    yy, xx = np.mgrid[0:56, 0:56]
    circ = ((xx - 27.5) ** 2 + (yy - 27.5) ** 2) <= 28 ** 2
    grad = np.array([80, 110, 250]) + (np.array([140, 60, 230]) - np.array([80, 110, 250])) * (xx / 55)[..., None]
    a[40:96, 200:256][circ] = grad[circ]                                                                  # avatar
    tb = (np.arange(42) / 41)[:, None, None]
    a[200:242, 400:416] = np.array([112, 148, 255]) + (np.array([100, 136, 250]) - np.array([112, 148, 255])) * tb  # bar
    buf = io.BytesIO()
    Image.fromarray(a.astype(np.uint8)).save(buf, "PNG")
    blocks = measure.measure(buf.getvalue())["blocks"]
    found = lambda box: [b for b in blocks if _iou(b["box"], box) >= 0.7]
    assert found([40, 40, 53, 53]), [b["box"] for b in blocks]
    av = found([200, 40, 56, 56])
    assert av and (av[0].get("radius") or 0) >= 20, av
    assert found([400, 200, 16, 42]), [b["box"] for b in blocks]


def test_a_diagonal_gradient_is_one_block_with_a_diagonal_direction():
    """Dashboard: the achievement tiles and the avatar run corner to corner; the one-direction check rejected them."""
    a = np.full((200, 300, 3), 255, np.float32)
    yy, xx = np.mgrid[0:60, 0:60]
    t = ((xx + yy) / 118)[..., None]
    a[50:110, 50:110] = np.array([254, 120, 20]) + (np.array([230, 40, 60]) - np.array([254, 120, 20])) * t
    buf = io.BytesIO()
    Image.fromarray(a.astype(np.uint8)).save(buf, "PNG")
    g = [b for b in measure.measure(buf.getvalue())["blocks"] if b.get("gradient")]
    assert g and _iou(g[0]["box"], [50, 50, 60, 60]) >= 0.8 and g[0]["gradient"]["dir"] == "br", g
    from orchestrator.fluid import _fill
    assert "bg-gradient-to-br" in _fill({bp: g[0] for bp in ("mobile", "tablet", "desktop")}).split()


def test_chart_bars_and_check_circles_inside_a_card_are_found():
    """Dashboard: bars inside the Weekly Activity card and the streak's check circles were dropped — a smooth block
    inside any existing block (the card) was taken for a duplicate."""
    a = np.full((300, 400, 3), (244, 246, 250), np.float32)
    a[20:280, 20:380] = 255                                                       # the card
    a[19, 20:380] = a[280, 20:380] = a[20:280, 19] = a[20:280, 380] = (226, 230, 238)
    tb = (np.arange(30) / 29)[:, None, None]
    for x, h in ((60, 30), (100, 18), (140, 52)):                                 # short faint-shaded bars
        a[240 - h:240, x:x + 16] = np.array([112, 148, 255]) + (np.array([104, 140, 252]) - np.array([112, 148, 255])) * (np.arange(h) / max(h - 1, 1))[:, None, None]
    yy, xx = np.mgrid[0:34, 0:34]
    circ = ((xx - 16.5) ** 2 + (yy - 16.5) ** 2) <= 17 ** 2
    for x in (60, 96, 132):                                                       # check circles with a white tick
        patch = a[60:94, x:x + 34]
        patch[circ] = (52, 102, 255)
        patch[15:19, 9:25] = 255
    buf = io.BytesIO()
    Image.fromarray(a.astype(np.uint8)).save(buf, "PNG")
    blocks = measure.measure(buf.getvalue())["blocks"]
    found = lambda box: [b for b in blocks if _iou(b["box"], box) >= 0.6]
    for box in ([60, 210, 16, 30], [100, 222, 16, 18], [140, 188, 16, 52], [60, 60, 34, 34], [96, 60, 34, 34], [132, 60, 34, 34]):
        assert found(box), (box, [b["box"] for b in blocks])
