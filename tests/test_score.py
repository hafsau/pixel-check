"""Adversarial tests for sandbox/score.py.

Thresholds were fixed BEFORE measuring (BUILD_GUIDE §6.2 + additions in docs/SCORING.md);
do not loosen them to make a failing scorer pass — fix the scorer.
Real-page cases use benchmarks-dev/ captures (git-ignored); they skip when absent.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sandbox"))
import score  # noqa: E402

DEV = ROOT / "benchmarks-dev"
# "-lx" folders are the same pages re-captured in the scoring image (tools/capture_linux.py), not other pages
PAGES = sorted(p.name for p in DEV.iterdir() if (p / "desktop.png").exists() and not p.name.endswith("-lx")) if DEV.exists() else []
BPS = score.BREAKPOINTS
needs_pages = pytest.mark.skipif(not PAGES, reason="no benchmarks-dev captures")


def img(page, bp):
    return score.load(DEV / page / f"{bp}.png")


def fill_like(t, rgb):
    return np.broadcast_to(np.array(rgb, np.float32), t.shape).copy()


def shift(t, dx, dy):
    bg = score.background(t)
    out = fill_like(t, bg)
    h, w, _ = t.shape
    out[dy:, dx:] = t[: h - dy, : w - dx]
    return out


def s(t, r):
    return score.score_pair(t, r)["score"]


# ---- synthetic (always run) -------------------------------------------------

def synthetic():
    t = np.full((800, 1280, 3), 255, np.float32)
    t[40:80, 60:400] = 20            # heading bar
    t[120:140, 60:900] = 90          # text line
    t[160:180, 60:700] = 90
    t[240:520, 60:400] = [79, 70, 229]   # card
    t[240:520, 440:780] = [230, 230, 235]
    return t


def test_synthetic_identical():
    t = synthetic()
    assert s(t, t) >= 99.9


def test_synthetic_blank():
    t = synthetic()
    assert s(t, fill_like(t, (255, 255, 255))) < 20


def test_size_mismatch_scores_zero():
    t = synthetic()
    assert score.score_pair(t, t[:400])["score"] == 0.0


def test_text_component():
    dom = [{"text": "Sign in"}, {"text": "Continue"}]
    assert score.text_score(["Sign in", "Continue"], dom)[0] == 1.0
    assert score.text_score(["Sign in", "Continue"], [])[0] == 0.0
    assert score.text_score(["Sign  in", "continue"], dom)[0] == 1.0      # whitespace/case
    assert score.text_score(["Contine"], dom)[0] == 1.0                     # fuzzy ≥ 0.85
    assert score.text_score(["Create account"], dom)[0] == 0.0


# ---- real pages ---------------------------------------------------------------

@needs_pages
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("bp", BPS)
def test_identical_is_100(page, bp):
    t = img(page, bp)
    assert s(t, t) >= 99.9


@needs_pages
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("bp", BPS)
def test_blank_below_20(page, bp):
    t = img(page, bp)
    for rgb in ((255, 255, 255), (0, 0, 0), tuple(score.background(t))):
        assert s(t, fill_like(t, rgb)) < 20, rgb


@needs_pages
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("bp", BPS)
def test_2px_shift_at_least_95(page, bp):
    t = img(page, bp)
    assert s(t, shift(t, 2, 2)) >= 95


@needs_pages
@pytest.mark.parametrize("page", PAGES)
def test_perfect_desktop_blank_mobile_match_below_20(page, tmp_path):
    from PIL import Image
    for bp in BPS:
        t = img(page, bp)
        r = t if bp != "mobile" else fill_like(t, score.background(t))
        Image.fromarray(r.astype(np.uint8)).save(tmp_path / f"{bp}.png")
    res = score.score_run(DEV / page, tmp_path)
    assert res["match"] < 20 and res["worst"] == "mobile"


@needs_pages
@pytest.mark.parametrize("bp", BPS)
def test_other_page_below_60(bp):
    for a in PAGES:
        for b in PAGES:
            if a != b:
                assert s(img(a, bp), img(b, bp)) < 60, (a, b)


@needs_pages
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("bp", BPS)
def test_inverted_below_40(page, bp):
    t = img(page, bp)
    assert s(t, 255.0 - t) < 40


@needs_pages
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("bp", BPS)
def test_half_content_removed_below_75(page, bp):
    t = img(page, bp)
    r = t.copy()
    h = t.shape[0]
    r[h // 2:] = score.background(t)
    tm = score.content_mask(t, score.background(t))
    if tm[h // 2:].mean() < 0.25 * tm.mean():   # page has little content in its lower half
        pytest.skip("lower half nearly empty")
    assert s(t, r) < 75


@needs_pages
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("bp", BPS)
def test_monotonic_within_defect_family(page, bp):
    """More of the same damage never scores higher. (Cross-family ordering — e.g. 12 px offset
    vs. missing lower half — depends on how much content each removes; see docs/SCORING.md.)"""
    t = img(page, bp)
    bg = score.background(t)
    shifts = [s(t, shift(t, d, d)) if d else s(t, t) for d in (0, 2, 6, 12, 24)]
    assert all(a >= b - 0.5 for a, b in zip(shifts, shifts[1:])), shifts
    h = t.shape[0]
    removed = []
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        r = t.copy()
        if frac:
            r[int(h * (1 - frac)):] = bg
        removed.append(s(t, r))
    assert all(a >= b - 0.5 for a, b in zip(removed, removed[1:])), removed
    assert removed[-1] < 20 and shifts[-1] > removed[-1]


@needs_pages
@pytest.mark.parametrize("page", PAGES)
def test_text_from_capture_ground_truth(page):
    texts = json.loads((DEV / page / "desktop.text.json").read_text())
    dom = [{"text": x["text"]} for x in texts]
    assert score.text_score([x["text"] for x in texts], dom)[0] == 1.0
