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
