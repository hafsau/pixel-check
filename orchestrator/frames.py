"""Design frames as designers export them (council plan, Oct 12).

Any width 320–1600 px, any height (≤ 6000 px), PNG / JPEG / WebP. The three uploads are labelled by width — the
narrowest is mobile, the widest desktop — whatever the files are called, and a swap is said. A full page taller
than 1.5 screens is cropped to its first screen for perception and scoring (full-page scoring dilutes errors: the
red team measured a missing hero costing a third as much on a 2453 px page). The code keeps standard Tailwind
screens: each frame gets the largest one at or below its width (402 → none, 768 → md:, 1071 → lg:), and the three
must differ. `use(sizes)` switches the compiler to a run's sizes and always restores the defaults.
"""
from __future__ import annotations

import io
from contextlib import contextmanager
from dataclasses import dataclass

from PIL import Image

BPS = ("mobile", "tablet", "desktop")
STANDARD = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}
SCREENS = (("sm:", 640), ("md:", 768), ("lg:", 1024), ("xl:", 1280), ("2xl:", 1536))
MIN_W, MAX_W, MAX_H = 320, 1600, 6000
MAX_PIXELS = 12_000_000           # decoded size cap (an 8 MB PNG can decode to hundreds of megapixels)
KEEP_WHOLE = 1.5                  # up to 1.5 screens tall: scored whole; taller: the first screen


class FrameError(ValueError):
    pass


@dataclass
class Frame:
    bp: str
    source: str           # the upload field / file name it came in as
    png: bytes            # what perception and scoring use (PNG, RGB, cropped)
    size: tuple[int, int]
    original: tuple[int, int]


def prefix_for(width: int) -> str:
    """The largest standard Tailwind screen at or below the width ('' = no prefix)."""
    pre = ""
    for p, w in SCREENS:
        if width >= w:
            pre = p
    return pre


def screen_height(bp: str, width: int) -> int:
    """The first screen's height for a frame of this width (the standard frames' proportions; desktops 800)."""
    if bp == "desktop":
        return 800
    w, h = STANDARD[bp]
    return round(width * h / w)


def _open(name: str, data: bytes) -> Image.Image:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        im = Image.open(io.BytesIO(data))
        w, h = im.size
        if w * h > MAX_PIXELS:
            raise FrameError(f"{name}: {w}×{h} px is too large to process")
        im.load()
    except FrameError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise FrameError(f"{name}: the image is too large to process") from None
    except Exception:
        raise FrameError(f"{name}: not a readable PNG, JPEG or WebP image") from None
    if im.format not in ("PNG", "JPEG", "WEBP"):
        raise FrameError(f"{name}: use a PNG, JPEG or WebP image")
    return im


def _png_rgb(im: Image.Image, crop_h: int | None) -> bytes:
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    if crop_h is not None:
        im = im.crop((0, 0, im.size[0], crop_h))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def assign(uploads: dict[str, bytes]) -> tuple[dict[str, Frame], list[str]]:
    """{field or file name: bytes} (three) → ({bp: Frame}, notes for the user). Raises FrameError with a reason."""
    if len(uploads) != 3:
        raise FrameError("give three frames: a phone, a tablet and a desktop width")
    opened = {name: _open(name, data) for name, data in uploads.items()}
    for name, im in opened.items():
        w, h = im.size
        if not MIN_W <= w <= MAX_W:
            raise FrameError(f"{name}: {w} px wide — frames must be {MIN_W}–{MAX_W} px wide (export at 1×)")
        if h > MAX_H:
            raise FrameError(f"{name}: {h} px tall — frames can be at most {MAX_H} px tall")
        if h < 200:
            raise FrameError(f"{name}: {h} px tall is too short for a screen")
    order = sorted(opened, key=lambda n: opened[n].size[0])
    widths = [opened[n].size[0] for n in order]
    if prefix_for(widths[0]) != "":
        raise FrameError(f"the narrowest frame ({order[0]}, {widths[0]} px) must be a mobile width (under 640 px)")
    pres = [prefix_for(w) for w in widths]
    if len(set(pres)) != 3:
        raise FrameError(f"the frames ({', '.join(f'{w} px' for w in widths)}) must fall in three different Tailwind "
                         f"screens (under 640 · 640 · 768 · 1024 · 1280 · 1536 px): two are too close")
    out, notes = {}, []
    for bp, name in zip(BPS, order):
        im = opened[name]
        w, h = im.size
        sh = screen_height(bp, w)
        crop = sh if h > KEEP_WHOLE * sh else None
        png = uploads[name] if (crop is None and im.format == "PNG" and im.mode == "RGB") else _png_rgb(im, crop)
        out[bp] = Frame(bp=bp, source=name, png=png, size=(w, crop or h), original=(w, h))
        label = name if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) else f"{name}.png"
        if name != bp:
            notes.append(f"{label} is {w} px wide → used as the {bp} frame")
        if crop:
            notes.append(f"{label} is {h} px tall (a full page) → scored on the first screen ({w}×{crop}); "
                         f"the full page is kept for display")
    return out, notes


def sizes(frames: dict[str, Frame]) -> dict[str, tuple[int, int]]:
    return {bp: frames[bp].size for bp in BPS}


def sizes_of(pngs: dict[str, bytes]) -> dict[str, tuple[int, int]]:
    """A run's sizes, read from its (already assigned) frames."""
    out = {}
    for bp in BPS:
        with Image.open(io.BytesIO(pngs[bp])) as im:
            out[bp] = tuple(im.size)
    return out


def is_standard(sz: dict[str, tuple[int, int]]) -> bool:
    return {bp: tuple(v) for bp, v in sz.items()} == STANDARD


def prefixes(sz: dict[str, tuple[int, int]]) -> dict[str, str]:
    return {bp: prefix_for(sz[bp][0]) for bp in BPS}


@contextmanager
def use(sz: dict[str, tuple[int, int]]):
    """Switch the compiler to a run's frame sizes and Tailwind prefixes; the defaults always come back (the live
    server runs one job at a time — JOB_SLOTS=1 — so module state is not shared between runs)."""
    from . import config, fluid, panel, scaffold
    targets = [(config.BREAKPOINTS, {bp: tuple(sz[bp]) for bp in BPS}),
               (scaffold.SIZES, {bp: tuple(sz[bp]) for bp in BPS}),
               (panel.SIZES, {bp: tuple(sz[bp]) for bp in BPS}),
               (scaffold.PREFIX, prefixes(sz)),
               (fluid.W, {bp: sz[bp][0] for bp in BPS}),
               (fluid.VH, {bp: sz[bp][1] for bp in BPS})]
    saved = [dict(d) for d, _ in targets]
    try:
        for d, new in targets:
            d.clear()
            d.update(new)
        yield
    finally:
        for (d, _), old in zip(targets, saved):
            d.clear()
            d.update(old)
