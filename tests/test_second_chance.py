"""Second-chance OCR (orchestrator/measure.py, Oct 7): small letter-spaced labels ("HELLO" on a portfolio's desktop
frame) were missed by the whole-page OCR pass, so the vision model's rough box was used. Text-like ink that no OCR
line or block covers is grouped into lines and OCR'd on its own, upscaled. Written before the change (TDD)."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from orchestrator.measure import second_chance
from orchestrator.typography import FONT_DIR, _ensure_fonts

BG = (255, 244, 228)


def frame(text="HELLO", at=(594, 82), spacing=4, size=16, colour=(40, 40, 40)):
    _ensure_fonts()
    im = Image.new("RGB", (1280, 800), BG)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(str(FONT_DIR / "inter-500.ttf"), size)
    x, y = at
    for ch in text:                       # letter-spaced, like the real label
        d.text((x, y), ch, font=f, fill=colour)
        x += d.textlength(ch, font=f) + spacing
    return np.asarray(im, dtype=np.float32)


def test_an_uncovered_label_is_found_and_read():
    lines = second_chance(frame(), lines=[], blocks=[])
    hit = [l for l in lines if l["text"].upper() == "HELLO"]
    assert hit, lines
    x, y, w, h = hit[0]["box"]
    assert abs(x - 594) <= 4 and abs(y - 85) <= 6 and 60 <= w <= 100 and hit[0]["second"]


def test_text_already_read_is_not_read_again():
    lines = second_chance(frame(), lines=[{"text": "HELLO", "box": [592, 82, 90, 18]}], blocks=[])
    assert lines == []


def test_large_shapes_are_not_text():
    im = frame()
    im[300:500, 200:700] = (20, 20, 20)            # a big dark panel
    lines = second_chance(im, lines=[], blocks=[{"box": [200, 300, 500, 200], "fill": "#141414"}])
    assert [l["text"].upper() for l in lines] == ["HELLO"]


def test_noise_without_letters_yields_nothing():
    im = np.full((800, 1280, 3), BG, np.float32)
    im[100:104, 100:104] = 0                        # a dot
    assert second_chance(im, lines=[], blocks=[]) == []
