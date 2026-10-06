"""Soft shadows measured from pixels (orchestrator/shadow.py, Oct 6): a portrait card with a large soft shadow lost
SSIM over the whole halo because the compiler only knew "shadow: yes" (→ shadow-sm). fit_shadow recovers a CSS
box-shadow (y offset, blur, opacity) from the darkening profile beside the box. Synthetic shadows rendered the
way browsers do (offset rect, Gaussian blur with sigma = blur / 2), so the truth is known. Written first (TDD)."""
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

from orchestrator.shadow import fit_shadow, shadow_class

BG = (255, 244, 228)
BOX = (95, 246, 200, 200)


def scene(oy, blur, alpha, size=(390, 844), box=BOX, fill=(212, 212, 216)):
    W, H = size
    x, y, w, h = box
    base = Image.new("RGB", size, BG)
    if alpha > 0:
        sh = Image.new("L", size, 0)
        ImageDraw.Draw(sh).rectangle([x, y + oy, x + w - 1, y + oy + h - 1], fill=255)
        if blur:
            sh = sh.filter(ImageFilter.GaussianBlur(blur / 2))
        a = np.asarray(sh, np.float32) / 255 * alpha
        img = np.asarray(base, np.float32) * (1 - a[..., None])
        base = Image.fromarray(img.round().astype(np.uint8))
    ImageDraw.Draw(base).rectangle([x, y, x + w - 1, y + h - 1], fill=fill)
    return np.asarray(base)


@pytest.mark.parametrize("oy,blur,alpha", [(24, 60, 0.15), (8, 24, 0.25), (0, 40, 0.12), (40, 80, 0.2)])
def test_recovers_offset_blur_and_opacity(oy, blur, alpha):
    s = fit_shadow(scene(oy, blur, alpha), list(BOX), np.array(BG, np.float32))
    assert s is not None
    assert abs(s["y"] - oy) <= max(4, 0.2 * oy)
    assert abs(s["blur"] - blur) <= max(8, 0.3 * blur)
    assert abs(s["alpha"] - alpha) <= 0.05


def test_no_shadow_is_none():
    assert fit_shadow(scene(0, 0, 0), list(BOX), np.array(BG, np.float32)) is None


def test_a_hard_border_is_not_a_soft_shadow():
    img = scene(0, 0, 0).copy()
    x, y, w, h = BOX
    img[y - 1:y + h + 1, x - 1] = img[y - 1:y + h + 1, x + w] = (120, 120, 120)
    img[y - 1, x - 1:x + w + 1] = img[y + h, x - 1:x + w + 1] = (120, 120, 120)
    assert fit_shadow(img, list(BOX), np.array(BG, np.float32)) is None


def test_box_at_the_image_edge_uses_the_sides_it_has():
    box = (0, 300, 200, 200)
    s = fit_shadow(scene(16, 40, 0.2, box=box), list(box), np.array(BG, np.float32))
    assert s is not None and abs(s["y"] - 16) <= 5


def test_small_boxes_are_skipped():
    box = (100, 100, 16, 16)
    assert fit_shadow(scene(4, 8, 0.3, box=box), list(box), np.array(BG, np.float32)) is None


def test_shadow_class_is_a_tailwind_arbitrary_value():
    assert shadow_class({"y": 24, "blur": 60, "alpha": 0.15}) == "shadow-[0_24px_60px_rgba(0,0,0,0.15)]"
    assert shadow_class(None) == "shadow-none"


def test_text_crossing_the_halo_does_not_spoil_the_fit():
    """A headline runs through the shadow above and below the picture (a portfolio hero)."""
    img = scene(24, 60, 0.15).copy()
    x, y, w, h = BOX
    for top in (y - 60, y + h + 10):          # thick black letter strokes crossing the profile columns
        for k in range(6):
            x0 = x + 10 + k * 34
            img[top:top + 50, x0:x0 + 18] = (26, 26, 26)
    s = fit_shadow(img, list(BOX), np.array(BG, np.float32))
    assert s is not None and abs(s["y"] - 24) <= 6 and abs(s["blur"] - 60) <= 20 and abs(s["alpha"] - 0.15) <= 0.06


def test_measure_records_the_fitted_shadow_on_the_block():
    import io
    from orchestrator.measure import measure
    buf = io.BytesIO()
    Image.fromarray(scene(24, 60, 0.15)).save(buf, "PNG")
    m = measure(buf.getvalue())
    big = [b for b in m["blocks"] if b["box"][2] >= 180 and b["box"][3] >= 180]
    assert big and big[0].get("shadow_fit") and abs(big[0]["shadow_fit"]["y"] - 24) <= 6


def test_the_compiler_emits_the_measured_shadow():
    from orchestrator.fluid import compile_fluid
    spec = {"breakpoints": {"mobile": {"size": [390, 844], "background": "#fff4e4",
            "texts": [{"text": "Hello there", "box": [40, 40, 120, 20], "size_px": 18, "color": "#111111", "role": "heading",
                       "weight": 600, "lines": 1, "measured": True}],
            "blocks": [{"box": [95, 246, 200, 200], "fill": "#d4d4d8", "radius": 24,
                        "shadow_fit": {"y": 40, "blur": 76, "alpha": 0.15}}]}}}
    code = compile_fluid(spec)
    assert "shadow-[0_40px_76px_rgba(0,0,0,0.15)]" in code
