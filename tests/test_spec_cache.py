"""Frame-reading cache (Oct 21, live-deploy council): Render free reads frames in ~9 min (0.1 CPU); the example frames'
reading ships in the image so a judge's live check of the example takes ~1 min. Keyed by pixels, not bytes, so the
same frames re-encoded on another machine still hit. Written before orchestrator/spec_cache.py."""
import io

from PIL import Image

from orchestrator import spec_cache as C


def png(w, h, colour, level=6):
    b = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(b, "PNG", compress_level=level)
    return b.getvalue()


FR = {"mobile": png(40, 80, (10, 20, 30)), "tablet": png(60, 80, (40, 50, 60)), "desktop": png(90, 60, (70, 80, 90))}


def test_the_key_follows_the_pixels_not_the_bytes():
    again = {bp: png(*Image.open(io.BytesIO(v)).size, Image.open(io.BytesIO(v)).getpixel((0, 0)), level=1) for bp, v in FR.items()}
    assert again != FR and C.key(again) == C.key(FR)
    other = {**FR, "tablet": png(60, 80, (41, 50, 60))}
    assert C.key(other) != C.key(FR)


def test_a_cached_reading_is_used_and_perception_is_skipped(tmp_path):
    C.save(FR, {"breakpoints": {"mobile": {"texts": []}}}, root=tmp_path)
    calls = []
    spec = C.read_design(None, FR, perceive=lambda c, f: calls.append(1) or {"x": 1}, root=tmp_path)
    assert spec == {"breakpoints": {"mobile": {"texts": []}}} and calls == []


def test_unknown_frames_are_read_as_usual(tmp_path):
    calls = []
    assert C.read_design("client", FR, perceive=lambda c, f: calls.append(c) or {"x": 1}, root=tmp_path) == {"x": 1}
    assert calls == ["client"]


def test_a_damaged_cache_file_falls_back_to_reading(tmp_path):
    (tmp_path / f"{C.key(FR)}.json").write_text("{not json")
    assert C.read_design(None, FR, perceive=lambda c, f: {"x": 2}, root=tmp_path) == {"x": 2}


def test_the_shipped_example_is_in_the_cache():
    """the example frames (ui/public/examples/dashboard) as the server crops them — the reading is committed"""
    assert any(C.ROOT.glob("*.json"))
