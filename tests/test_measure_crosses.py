"""measure.crosses: small "+" icons (two short bars crossing at their centres) are found as a pair of thin rules.
lambda's menu rows end in 12 px "+" icons; thin_lines needs ≥ 24/40 px runs, so they were invisible to perception.
Written before the implementation (TDD, Oct 2)."""
import numpy as np

from orchestrator.measure import crosses


def canvas():
    img = np.full((300, 390, 3), 11.0)
    return img


def plus(img, cx, cy, size=12, t=2, c=(231, 230, 217)):
    img[cy - t // 2:cy - t // 2 + t, cx - size // 2:cx + size // 2] = c
    img[cy - size // 2:cy + size // 2, cx - t // 2:cx - t // 2 + t] = c


def test_finds_small_plus_as_two_crossing_rules():
    img = canvas()
    plus(img, 362, 188)
    out = crosses(img, [])
    assert len(out) == 2
    h = [b for b in out if b["box"][2] > b["box"][3]][0]
    v = [b for b in out if b["box"][3] > b["box"][2]][0]
    assert abs((h["box"][0] + h["box"][2] / 2) - (v["box"][0] + v["box"][2] / 2)) <= 2
    assert 10 <= h["box"][2] <= 14 and h["box"][3] <= 3 and h["fill"].startswith("#e")


def test_several_plus_icons():
    img = canvas()
    for y in (50, 140, 230):
        plus(img, 362, y)
    assert len(crosses(img, [])) == 6


def test_lone_dash_and_text_area_are_ignored():
    img = canvas()
    img[100:102, 50:62] = 230                     # a dash, no vertical partner
    img[200:212, 100:102] = 230                   # glyph-like strokes inside a text box
    img[205:207, 95:107] = 230
    assert crosses(img, [[90, 195, 60, 20]]) == []


def test_t_junction_is_not_a_plus():
    img = canvas()
    img[100:102, 50:62] = 230                      # top bar
    img[100:112, 55:57] = 230                      # stem from the bar's end (a "T"), centres 5 px apart vertically
    assert crosses(img, []) == []
