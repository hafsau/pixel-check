"""Photos in designers' own exports (Oct 12, Hafsa's dashboard): the dev pages' captures grey every image, so
perception had no notion of a photo — the yoga images vanished and the text beside them drifted. A textured,
many-coloured rectangle with a clean outline becomes a media placeholder block (#d4d4d8, the capture's grey) at its
measured box; code still never embeds images. Written before the code (TDD)."""
import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from orchestrator import measure

ROOT = Path(__file__).resolve().parents[1]


def page():
    rng = np.random.default_rng(1)
    a = np.full((500, 800, 3), (244, 246, 250), np.float32)
    yy, xx = np.mgrid[0:150, 0:260]
    photo = np.stack([120 + 80 * np.sin(xx / 9) + rng.normal(0, 25, xx.shape),
                      100 + 60 * np.cos(yy / 7) + rng.normal(0, 25, xx.shape),
                      140 + 50 * np.sin((xx + yy) / 13) + rng.normal(0, 25, xx.shape)], axis=-1)
    a[80:230, 60:320] = photo.clip(0, 255)
    im = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.text((400, 100), "Morning Mobility and a long line of text here", fill=(20, 20, 20))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_a_photo_is_a_media_placeholder_block():
    blocks = measure.measure(page())["blocks"]
    ph = [b for b in blocks if b.get("media")]
    assert len(ph) == 1 and measure._iou(ph[0]["box"], [60, 80, 260, 150]) >= 0.85, [(b["box"], b.get("fill")) for b in blocks]
    assert ph[0]["fill"] == "#d4d4d8"
    assert not [b for b in blocks if b is not ph[0] and measure._frac_inside(b["box"], ph[0]["box"]) >= 0.8]


@pytest.mark.skipif(not (ROOT / "benchmarks" / "desktop.png").exists(), reason="Hafsa's screens not present")
def test_hafsas_photos_are_found_and_nothing_else():
    blocks = measure.measure((ROOT / "benchmarks" / "desktop.png").read_bytes())["blocks"]
    ph = [b["box"] for b in blocks if b.get("media")]
    for want in ([398, 464, 275, 155], [732, 792, 108, 97], [732, 931, 108, 101]):  # Up Next + two habit thumbnails
        assert any(measure._iou(p, want) >= 0.7 for p in ph), (want, ph)
    assert len(ph) <= 4, ph                       # not the banner, the cards, the bar chart or the avatar


@pytest.mark.skipif(not (ROOT / "benchmarks" / "mobile.png").exists(), reason="Hafsa's screens not present")
def test_text_on_a_gradient_banner_is_not_a_photo():
    from orchestrator import frames as F
    up = {bp: (ROOT / "benchmarks" / f"{bp}.png").read_bytes() for bp in F.BPS}
    fr, _ = F.assign(up)
    blocks = measure.measure(fr["mobile"].png)["blocks"]
    assert not [b for b in blocks if b.get("media") and b["box"][1] < 300], [b["box"] for b in blocks if b.get("media")]


def test_the_block_cap_keeps_the_largest_blocks_not_the_topmost():
    """solid_blocks kept the first 60 blocks by position: on a dense dashboard the icons at the top used up the cap
    and the cards lower down vanished (Time Logged, Weekly Activity, the habit cards)."""
    a = np.full((900, 800, 3), (244, 246, 250), np.float32)
    for k in range(70):                                       # 70 small coloured icons near the top
        x, y = 20 + (k % 14) * 55, 20 + (k // 14) * 40
        a[y:y + 24, x:x + 24] = ((k * 37) % 200 + 30, (k * 53) % 200 + 30, (k * 91) % 200 + 30)
    a[600:800, 40:400] = 255                                  # a big white card at the bottom
    buf = io.BytesIO()
    Image.fromarray(a.astype(np.uint8)).save(buf, "PNG")
    blocks = measure.solid_blocks(np.asarray(Image.open(buf).convert("RGB"), dtype=np.float32), [], min_area=100)
    assert any(measure._iou(b["box"], [40, 600, 360, 200]) >= 0.9 for b in blocks)
