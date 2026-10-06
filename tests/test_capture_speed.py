"""Phase 2 speed + safety (capture.mjs): the three sizes are captured in parallel, the fixed wait becomes a "layout
settled" wait (--wait is now the maximum), and every size records where it really ended up — a page that redirects
only at one width is still checked by the live API."""
import http.server
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "tools" / "capture"
pytestmark = pytest.mark.skipif(not (CAP / "node_modules").exists(), reason="capture deps not installed")

STATIC = b'<!doctype html><html><head><title>Static</title></head><body><h1>Hello</h1><p>Plain page.</p></body></html>'
LATE = (b'<!doctype html><html><head><title>Late</title></head><body><h1>Hello</h1><script>'
        b'setTimeout(()=>{const p=document.createElement("p");p.textContent="Late text";document.body.appendChild(p)},800)'
        b'</script></body></html>')
BUSY = (b'<!doctype html><html><head><title>Busy</title></head><body><h1 id="c">0</h1><script>'
        b'let i=0;setInterval(()=>{document.getElementById("c").textContent=String(++i)},100)</script></body></html>')
WIDE_ONLY = (b'<!doctype html><html><head><title>Home</title></head><body><h1>Home</h1><script>'
             b'setTimeout(()=>{if(innerWidth>1000)location.href="/desk"},50)</script></body></html>')
DESK = b'<!doctype html><html><head><title>Desk</title></head><body><h1>Desktop page</h1></body></html>'


def _png_bytes(rgb=(200, 30, 30), size=(64, 64)):
    import io
    from PIL import Image as _I
    buf = io.BytesIO()
    _I.new("RGB", size, rgb).save(buf, "PNG")
    return buf.getvalue()


PIC = _png_bytes()
FAKE = b"<html>not an image</html>"
PHOTO = (b'<!doctype html><html><head><title>Photo</title><style>body{margin:0}img{display:block;width:120px;height:120px;'
         b'border-radius:16px;margin:20px}</style></head><body><h1>Me</h1><img src="/pic.png" alt="me">'
         b'<img src="/fake.png" alt="x"><button style="color:#123456">Go <svg class="ic" width="16" height="16" '
         b'viewBox="0 0 16 16"><path d="M2 14L14 2" stroke="currentColor"/></svg></button>'
         b'<svg class="bad" width="20" height="20"><script>alert(1)</script><rect width="20" height="20"/></svg>'
         b'</body></html>')


class _H(http.server.BaseHTTPRequestHandler):
    routes = {"/static": STATIC, "/late": LATE, "/busy": BUSY, "/wide": WIDE_ONLY, "/desk": DESK, "/photo": PHOTO,
              "/pic.png": PIC, "/fake.png": FAKE}

    def do_GET(self):
        body = self.routes.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png" if self.path.endswith(".png") else "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def cap(url, out, *extra):
    t0 = time.time()
    r = subprocess.run(["node", "capture.mjs", "fx", url, "--out", str(out), *extra],
                       cwd=CAP, capture_output=True, text=True, timeout=120)
    return r, time.time() - t0


def test_three_sizes_in_parallel_with_a_settle_wait(tmp_path, server):
    r, dt = cap(f"{server}/static", tmp_path, "--wait", "3000")
    assert r.returncode == 0, r.stderr[-400:]
    for bp in ("mobile", "tablet", "desktop"):
        assert (tmp_path / "fx" / f"{bp}.png").exists()
    # sequential with a fixed 3 s wait took > 9 s; parallel + settled page: well under one fixed wait per size
    assert dt < 6.0, dt


def test_content_added_after_load_is_still_captured(tmp_path, server):
    r, _ = cap(f"{server}/late", tmp_path, "--bps", "mobile", "--wait", "3000")
    assert r.returncode == 0, r.stderr[-400:]
    texts = [t["text"] for t in json.loads((tmp_path / "fx" / "mobile.text.json").read_text())]
    assert "Late text" in texts


def test_a_page_that_never_settles_stops_at_the_maximum_wait(tmp_path, server):
    r, dt = cap(f"{server}/busy", tmp_path, "--bps", "mobile", "--wait", "1500")
    assert r.returncode == 0, r.stderr[-400:]
    assert dt < 1.5 + 6.0, dt                       # bounded: max wait + browser start + networkidle grace


def test_every_size_records_where_it_ended_up(tmp_path, server):
    r, _ = cap(f"{server}/wide", tmp_path, "--wait", "1000")
    assert r.returncode == 0, r.stderr[-400:]
    nav = json.loads((tmp_path / "fx" / "meta.json").read_text())["navigation"]
    assert f"{server}/desk" in nav["final_urls"] and f"{server}/wide" in nav["final_urls"]
    assert nav["server_ips"] == ["127.0.0.1"]


# Phase 2 capture fixes: decorative SVGs (aria-hidden wrapper) are dropped, full-screen loaders and cookie bars are
# hidden, and a real (un-normalised) screenshot can be saved next to the target
import numpy as np
from PIL import Image

FX = ROOT / "tests" / "fixtures" / "capture"


def _px(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(int)


def _count(im, rgb, tol=10):
    return int((np.abs(im - rgb).sum(axis=2) < tol).sum())


def _texts(d, bp="mobile"):
    return [t["text"] for t in json.loads((d / f"{bp}.text.json").read_text())]


def test_svg_under_an_aria_hidden_wrapper_is_dropped_not_greyed(tmp_path):
    r, _ = cap((FX / "wave.html").as_uri(), tmp_path, "--bps", "mobile", "--wait", "500")
    assert r.returncode == 0, r.stderr[-400:]
    im = _px(tmp_path / "fx" / "mobile.png")
    grey = _count(im, [212, 212, 216], 6)
    assert grey < 30 * 30, grey                       # only the 16 px icon is a block, not a 390×80 band
    assert grey >= 16 * 16 - 20                       # the icon inside the button still is


def test_a_full_screen_loader_is_hidden_but_a_background_layer_stays(tmp_path):
    r, _ = cap((FX / "loader.html").as_uri(), tmp_path, "--bps", "mobile", "--wait", "500")
    assert r.returncode == 0, r.stderr[-400:]
    im = _px(tmp_path / "fx" / "mobile.png")
    assert _count(im, [255, 0, 0]) == 0
    assert _count(im, [0, 0, 255]) > 390 * 844 * 0.5
    assert "Loading…" not in _texts(tmp_path / "fx")


def test_a_cookie_bar_is_hidden_but_the_header_link_stays(tmp_path):
    r, _ = cap((FX / "cookie.html").as_uri(), tmp_path, "--bps", "mobile", "--wait", "500")
    assert r.returncode == 0, r.stderr[-400:]
    assert _count(_px(tmp_path / "fx" / "mobile.png"), [0, 255, 0]) == 0
    texts = " ".join(_texts(tmp_path / "fx"))
    assert "We use cookies" not in texts and "Cookie policy" in texts and "Studio" in texts


def test_real_screenshot_keeps_media_and_the_target_does_not(tmp_path):
    r, _ = cap((FX / "disclosure.html").as_uri(), tmp_path, "--bps", "mobile", "--wait", "0", "--real")
    assert r.returncode == 0, r.stderr[-400:]
    red = lambda im: int(((im[..., 0] > 200) & (im[..., 1] < 60) & (im[..., 2] < 60)).sum())
    assert red(_px(tmp_path / "fx" / "mobile.real.png")) > 0
    assert red(_px(tmp_path / "fx" / "mobile.png")) == 0


def test_no_real_screenshot_unless_asked(tmp_path):
    r, _ = cap((FX / "disclosure.html").as_uri(), tmp_path, "--bps", "mobile", "--wait", "0")
    assert r.returncode == 0
    assert not (tmp_path / "fx" / "mobile.real.png").exists()


# Phase 2 real images (owned sites): --assets saves the page's own images (bytes as served, checked by signature) and
# inline SVG icons (sanitised), with each one's box at every size; the target frames still show grey blocks
import hashlib


def test_assets_are_saved_with_their_boxes_and_the_target_stays_grey(tmp_path, server):
    r, _ = cap(f"{server}/photo", tmp_path, "--wait", "500", "--assets")
    assert r.returncode == 0, r.stderr[-400:]
    d = tmp_path / "fx"
    man = json.loads((d / "assets.json").read_text())
    by = {a["hash"]: a for a in man["assets"]}
    h = hashlib.sha256(PIC).hexdigest()
    assert h in by and by[h]["ext"] == "png" and by[h]["kind"] == "img" and by[h]["alt"] == "me"
    assert (d / "assets" / f"{h}.png").read_bytes() == PIC
    for bp in ("mobile", "tablet", "desktop"):
        x, y, w, hh = by[h]["boxes"][bp][0]       # every occurrence's box at that size
        assert (w, hh) == (120, 120) and x == 20
    svgs = [a for a in man["assets"] if a["ext"] == "svg"]
    assert len(svgs) == 1                               # the icon; the one with a <script> is skipped
    body = (d / "assets" / f"{svgs[0]['hash']}.svg").read_text()
    assert "<script" not in body and "xmlns" in body and "#123456" in body.lower().replace("rgb(18, 52, 86)", "#123456")
    assert hashlib.sha256(FAKE).hexdigest() not in by      # served as png, but not a png
    red = lambda im: int(((im[..., 0] > 180) & (im[..., 1] < 60) & (im[..., 2] < 60)).sum())
    assert red(_px(d / "mobile.png")) == 0


def test_no_assets_unless_asked(tmp_path, server):
    r, _ = cap(f"{server}/photo", tmp_path, "--bps", "mobile", "--wait", "0")
    assert r.returncode == 0
    assert not (tmp_path / "fx" / "assets.json").exists() and not (tmp_path / "fx" / "assets").exists()


def test_split_letter_headings_are_one_target_string(tmp_path):
    """Split-text animations wrap each letter in a span: the target is the word on screen, not 4 letters."""
    r, _ = cap((FX / "split.html").as_uri(), tmp_path, "--bps", "mobile", "--wait", "0")
    assert r.returncode == 0, r.stderr[-400:]
    items = json.loads((tmp_path / "fx" / "mobile.text.json").read_text())
    texts = [t["text"] for t in items]
    assert "NAME" in texts and "LAST" in texts          # whitespace between flex items is not a visible space
    assert "ONE TWO" in texts                           # a real word gap is
    assert not any(t in texts for t in ("N", "M", "E", "L", "S", "T"))
    name = next(t for t in items if t["text"] == "NAME")
    assert name["box"][2] > 120                         # the union of the letters
    assert "Hello" in texts and "World" in texts and "Two" in texts and "words" in texts   # ordinary inline text unchanged
