"""Frames as designers export them (orchestrator/frames.py, council plan Oct 12): any width 320–1600, any height,
PNG / JPEG / WebP; labelled by width (swapped file names fixed and said); full pages cropped to the first screen
for scoring; the standard Tailwind prefix for each width; upload bounds against decompression bombs. Hafsa's own
exports (benchmarks/: 402×2453, 768×1936, 1071×1177) are the fixture. Written before the
module (TDD)."""
import io
from pathlib import Path

import pytest
from PIL import Image

from orchestrator import frames as F

ROOT = Path(__file__).resolve().parents[1]


def img(w, h, fmt="PNG", color=(240, 240, 250), mode="RGB"):
    buf = io.BytesIO()
    Image.new(mode, (w, h), color).save(buf, fmt)
    return buf.getvalue()


def size(png):
    return Image.open(io.BytesIO(png)).size


def test_standard_frames_pass_through_unchanged():
    up = {"mobile": img(390, 844), "tablet": img(768, 1024), "desktop": img(1280, 800)}
    out, notes = F.assign(up)
    assert {bp: f.size for bp, f in out.items()} == {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}
    assert out["mobile"].png == up["mobile"] and notes == []
    assert F.prefixes(F.sizes(out)) == {"mobile": "", "tablet": "md:", "desktop": "xl:"}


@pytest.mark.skipif(not (ROOT / "benchmarks" / "mobile.png").exists(), reason="Hafsa's screens not present")
def test_hafsas_exports_are_labelled_by_width_and_cropped_to_the_first_screen():
    b = ROOT / "benchmarks"
    up = {bp: (b / f"{bp}.png").read_bytes() for bp in ("mobile", "tablet", "desktop")}
    out, notes = F.assign(up)
    assert [out[bp].source for bp in ("mobile", "tablet", "desktop")] == ["mobile", "tablet", "desktop"]
    assert out["mobile"].size == (402, 870) and size(out["mobile"].png) == (402, 870)        # 2453 tall → first screen
    assert out["tablet"].size == (768, 1024)                                                  # 1936 tall → first screen
    assert out["desktop"].size == (1071, 1177)                    # ≤ 1.5 screens tall: kept whole
    assert F.prefixes(F.sizes(out)) == {"mobile": "", "tablet": "md:", "desktop": "lg:"}
    text = " ".join(notes)
    assert "2453" in text and "1936" in text and "first screen" in text and "used as" not in text


def test_swapped_file_names_are_fixed_by_width_and_said():
    up = {"mobile": img(402, 900), "tablet": img(1071, 1177), "desktop": img(768, 1024)}
    out, notes = F.assign(up)
    assert out["tablet"].source == "desktop" and out["desktop"].source == "tablet"
    text = " ".join(notes)
    assert "tablet.png is 1071 px wide → used as the desktop frame" in text and "desktop.png is 768 px" in text


def test_prefix_is_the_largest_standard_screen_at_or_below_the_width():
    assert [F.prefix_for(w) for w in (320, 402, 639, 640, 768, 1023, 1024, 1071, 1279, 1280, 1536, 1600)] == \
        ["", "", "", "sm:", "md:", "md:", "lg:", "lg:", "lg:", "xl:", "2xl:", "2xl:"]


def test_formats_are_converted_to_png_on_white():
    up = {"mobile": img(390, 844, "JPEG"), "tablet": img(768, 1024, "WEBP"),
          "desktop": img(1280, 800, "PNG", (0, 0, 0, 0), "RGBA")}
    out, _ = F.assign(up)
    for f in out.values():
        im = Image.open(io.BytesIO(f.png))
        assert im.format == "PNG" and im.mode == "RGB"
    assert Image.open(io.BytesIO(out["desktop"].png)).getpixel((5, 5)) == (255, 255, 255)


@pytest.mark.parametrize("widths,msg", [
    ((300, 768, 1280), "320"),                 # too narrow
    ((390, 768, 1700), "1600"),                # too wide
    ((390, 400, 1280), "different"),           # two frames share a Tailwind screen
    ((700, 768, 1280), "mobile"),              # the smallest frame must be a phone (< 640)
])
def test_frames_outside_the_bounds_are_refused_with_a_reason(widths, msg):
    up = {bp: img(w, 900) for bp, w in zip(("mobile", "tablet", "desktop"), widths)}
    with pytest.raises(F.FrameError) as e:
        F.assign(up)
    assert msg in str(e.value)


def test_not_an_image_and_huge_images_are_refused():
    with pytest.raises(F.FrameError):
        F.assign({"mobile": b"nope", "tablet": img(768, 1024), "desktop": img(1280, 800)})
    with pytest.raises(F.FrameError) as e:                        # 1600 × 6001: taller than the cap
        F.assign({"mobile": img(390, 844), "tablet": img(768, 1024), "desktop": img(1600, 6001)})
    assert "6000" in str(e.value)


def test_a_decompression_bomb_is_a_frame_error_not_a_crash():
    bomb = img(20000, 20000, "PNG", (255, 255, 255))             # small file, 400 Mpx decoded
    with pytest.raises(F.FrameError):
        F.assign({"mobile": img(390, 844), "tablet": img(768, 1024), "desktop": bomb})


def test_use_switches_the_compiler_to_the_runs_sizes_and_always_restores():
    from orchestrator import config, fluid, scaffold
    before = (dict(config.BREAKPOINTS), dict(scaffold.SIZES), dict(scaffold.PREFIX), dict(fluid.W), dict(fluid.VH))
    run = {"mobile": (402, 870), "tablet": (768, 1024), "desktop": (1071, 1177)}
    with F.use(run):
        assert config.BREAKPOINTS["desktop"] == (1071, 1177) and scaffold.SIZES["mobile"] == (402, 870)
        assert scaffold.PREFIX["desktop"] == "lg:" and fluid.W["desktop"] == 1071 and fluid.VH["mobile"] == 870
    assert (dict(config.BREAKPOINTS), dict(scaffold.SIZES), dict(scaffold.PREFIX), dict(fluid.W), dict(fluid.VH)) == before
    with pytest.raises(RuntimeError):
        with F.use(run):
            raise RuntimeError("a failed run")
    assert dict(scaffold.PREFIX) == before[2] and dict(config.BREAKPOINTS) == before[0]


def test_sizes_of_reads_the_frames_themselves():
    assert F.sizes_of({"mobile": img(402, 870), "tablet": img(768, 1024), "desktop": img(1071, 1177)}) == \
        {"mobile": (402, 870), "tablet": (768, 1024), "desktop": (1071, 1177)}
    assert F.is_standard(F.sizes_of({"mobile": img(390, 844), "tablet": img(768, 1024), "desktop": img(1280, 800)}))
