"""Regression tests for the red-team findings (docs/SCORING.md, council review 2026-09-29).

Thresholds were fixed before measuring v3. Image-level attacks are built from the dev captures
(git-ignored); the fidelity ladder uses the red-team's rendered candidates if present locally.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sandbox"))
import score  # noqa: E402

DEV = ROOT / "benchmarks-dev"
PAGES = sorted(p.name for p in DEV.iterdir() if (p / "desktop.png").exists()) if DEV.exists() else []
BPS = score.BREAKPOINTS
needs_pages = pytest.mark.skipif(not PAGES, reason="no benchmarks-dev captures")


def img(page, bp):
    return score.load(DEV / page / f"{bp}.png")


def texts(page, bp):
    return json.loads((DEV / page / f"{bp}.text.json").read_text())


def dust(t, dot=3):
    """3×3 dot of the local ink colour per 8 px content cell (red-team #2)."""
    bg = score.background(t)
    tm = score.content_mask(t, bg)
    out = np.empty_like(t); out[:] = bg
    c = score.LAYOUT_CELL
    for y in range(0, t.shape[0] - c + 1, c):
        for x in range(0, t.shape[1] - c + 1, c):
            m = tm[y:y + c, x:x + c]
            if m.mean() > 0.02:
                col = t[y:y + c, x:x + c][m].mean(axis=0)
                out[y + 2:y + 2 + dot, x + 2:x + 2 + dot] = col
    return out


def blobs(t):
    """Each 8 px content cell filled solid with its mean ink colour (red-team #3)."""
    bg = score.background(t)
    tm = score.content_mask(t, bg)
    out = np.empty_like(t); out[:] = bg
    c = score.LAYOUT_CELL
    for y in range(0, t.shape[0] - c + 1, c):
        for x in range(0, t.shape[1] - c + 1, c):
            m = tm[y:y + c, x:x + c]
            if m.mean() > 0.02:
                out[y:y + c, x:x + c] = t[y:y + c, x:x + c][m].mean(axis=0)
    return out


def thin_lines(t, tx):
    """2 px rule in the text colour across every text box (red-team #3)."""
    bg = score.background(t)
    out = np.empty_like(t); out[:] = bg
    for e in tx:
        x, y, w, h = e["box"]
        y0 = max(0, y + h // 2)
        region = t[max(0, y):y + h, max(0, x):x + w]
        if region.size == 0:
            continue
        d = np.linalg.norm(region - bg, axis=-1)
        col = region[d >= np.percentile(d, 90)].mean(axis=0) if d.max() > 0 else bg
        out[y0:y0 + 2, max(0, x):x + w] = col
    return out


def shift_down(t, dy):
    bg = score.background(t)
    out = np.empty_like(t); out[:] = bg
    out[dy:] = t[:-dy]
    return out


def s(t, r, tt=None, dom=None):
    return score.score_pair(t, r, tt, dom)["score"]


@needs_pages
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("bp", BPS)
@pytest.mark.parametrize("attack", ["dust", "blobs", "thin_lines"])
def test_text_free_hacks_below_60(page, bp, attack):
    """Production conditions: target text is always known (from the spec); the hack renders none."""
    t = img(page, bp)
    tx = texts(page, bp)
    r = {"dust": lambda: dust(t), "blobs": lambda: blobs(t), "thin_lines": lambda: thin_lines(t, tx)}[attack]()
    assert s(t, r, tx, []) < 60


@needs_pages
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("bp", BPS)
def test_invisible_text_dump_gains_nothing(page, bp):
    t = img(page, bp)
    tx = texts(page, bp)
    r = dust(t)
    # the dump: every target string, claimed at its true box, but not readable (flags from render.mjs)
    dump_flagged = [{"text": e["text"], "box": e["box"], "font_size": "1px", "inked": False, "onscreen": True} for e in tx]
    dump_sneaky = [{"text": e["text"], "box": e["box"], "font_size": "16px"} for e in tx]   # no flags: ink check must catch
    base = s(t, r, tx, [])
    assert s(t, r, tx, dump_flagged) <= base + 0.5
    blank = np.empty_like(t); blank[:] = score.background(t)
    assert s(t, blank, tx, dump_sneaky) <= s(t, blank, tx, []) + 0.5


@needs_pages
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("bp", BPS)
def test_offset_20px_not_below_junk(page, bp):
    t = img(page, bp)
    tx = texts(page, bp)
    dom = [{"text": e["text"], "box": [e["box"][0], e["box"][1] + 20, *e["box"][2:]], "font_size": "16px"} for e in tx]
    # ≥ 80 applies to the offset alone (text off). With text on, strings pushed below the fold by the
    # shift are genuinely missing (text became a multiplier in v4), so the bar there is: beat every hack.
    assert s(t, shift_down(t, 20)) >= 80
    off = s(t, shift_down(t, 20), tx, dom)
    assert off > max(s(t, dust(t), tx, []), s(t, blobs(t), tx, []))


@needs_pages
def test_cta_colour_matters():
    t = img("netflix-signin", "desktop")
    red = np.array([229, 9, 20], np.float32)
    r = t.copy()
    m = np.linalg.norm(t - red, axis=-1) < 60
    assert m.sum() > 1000, "expected the red CTA in the capture"
    r[m] = [37, 99, 235]
    assert s(t, t) - s(t, r) >= 8


def test_transparent_png_reads_as_white(tmp_path):
    a = np.zeros((64, 64, 4), np.uint8)
    a[20:30, 10:50] = [10, 10, 10, 255]
    Image.fromarray(a, "RGBA").save(tmp_path / "t.png")
    t = score.load(tmp_path / "t.png")
    assert tuple(t[0, 0]) == (255.0, 255.0, 255.0) and tuple(t[25, 20]) == (10.0, 10.0, 10.0)


def test_tiny_and_float_inputs_rejected(tmp_path):
    Image.new("RGB", (4, 4)).save(tmp_path / "x.png")
    with pytest.raises(ValueError):
        score.load(tmp_path / "x.png")
    with pytest.raises(ValueError):
        score.score_pair(np.full((64, 64, 3), np.nan, np.float32), np.zeros((64, 64, 3), np.float32))
    with pytest.raises(ValueError):
        score.score_pair(np.zeros((64, 64, 4), np.float32), np.zeros((64, 64, 4), np.float32))
    with pytest.raises(ValueError):
        score.score_pair(np.zeros((16, 16, 3), np.float32), np.zeros((16, 16, 3), np.float32))


def test_short_strings_need_whole_words():
    assert score.text_score(["or"], [{"text": "Netflix Store"}])[0] == 0.0
    assert score.text_score(["or"], [{"text": "sign up or log in"}])[0] == 1.0
    assert score.text_score(["netflix"], [{"text": None}, {"text": "Netflix"}])[0] == 1.0


LADDER = ROOT / "out" / "redteam" / "renders"


@pytest.mark.skipif(not LADDER.exists(), reason="red-team renders not present")
@pytest.mark.parametrize("page,short", [("netflix-signin", "netflix"), ("calcom-signup", "calcom")])
@pytest.mark.parametrize("bp", BPS)
def test_fidelity_ladder_monotonic(page, short, bp):
    root = LADDER / page
    names = ["rough", "decent", "close"]
    if not all((root / n / f"{bp}.png").exists() for n in names):
        pytest.skip("ladder renders missing")
    t = img(page, bp)
    tx = texts(page, bp)
    got = [s(t, score.load(root / n / f"{bp}.png"), tx, json.loads((root / n / f"{bp}.dom.json").read_text())) for n in names]
    assert got[0] < got[1] < got[2], got
