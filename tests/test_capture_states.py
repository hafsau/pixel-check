"""Dev capture tool (tools/capture/capture.mjs --state): media that appears or is re-rendered after the click must be
replaced exactly like media in the base frame (netflix "Get help": the base showed the chevron as a grey block, the
state frame the real chevron → an inconsistent target). Written before the fix (TDD, Oct 2)."""
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "tools" / "capture"
pytestmark = pytest.mark.skipif(not (CAP / "node_modules").exists(), reason="capture deps not installed")


def test_media_revealed_by_the_click_is_replaced_like_the_base(tmp_path):
    url = (ROOT / "tests" / "fixtures" / "capture" / "disclosure.html").as_uri()
    for extra in ([], ["--state", "help", "--click", "#t"]):          # base frame, then the state frame
        r = subprocess.run(["node", "capture.mjs", "fx", url, "--bps", "mobile", "--out", str(tmp_path), "--wait", "0"]
                           + extra, cwd=CAP, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr[-500:]
    d = tmp_path / "fx"
    for f in ("mobile.png", "mobile.help.png"):
        im = np.asarray(Image.open(d / f).convert("RGB")).astype(int)
        red = (im[..., 0] > 200) & (im[..., 1] < 60) & (im[..., 2] < 60)
        assert red.sum() == 0, (f, int(red.sum()))                    # no original media pixels left
    st = np.asarray(Image.open(d / "mobile.help.png").convert("RGB")).astype(int)
    grey = (np.abs(st - [212, 212, 216]).sum(axis=2) < 6)
    assert grey.sum() >= 16 * 16 + 32 * 32 - 40                       # the chevron and the new icon, as blocks


def test_capture_reports_password_and_payment_fields(tmp_path):
    """Live mode from a URL refuses login / checkout pages: the capture reports them in meta.json."""
    import json
    url = (ROOT / "tests" / "fixtures" / "capture" / "login.html").as_uri()
    r = subprocess.run(["node", "capture.mjs", "fx", url, "--bps", "mobile", "--out", str(tmp_path), "--wait", "0"],
                       cwd=CAP, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-500:]
    meta = json.loads((tmp_path / "fx" / "meta.json").read_text())
    assert meta["sensitive"]["password"] == 1 and meta["sensitive"]["payment"] >= 1
    plain = (ROOT / "tests" / "fixtures" / "capture" / "disclosure.html").as_uri()
    subprocess.run(["node", "capture.mjs", "fx2", plain, "--bps", "mobile", "--out", str(tmp_path), "--wait", "0"],
                   cwd=CAP, capture_output=True, text=True, timeout=120)
    m2 = json.loads((tmp_path / "fx2" / "meta.json").read_text())
    assert m2["sensitive"] == {"password": 0, "payment": 0, "signin": 0, "crypto": 0}


# council guardrails (Oct 5): where the capture really went, private-address blocking, stronger sensitive detection
import http.server
import json as _json
import threading

PAGE = (b'<!doctype html><html><head><meta charset="utf-8"><title>Studio Home</title>'
        b'<meta property="og:site_name" content="Studio"></head><body><h1>Hello</h1>'
        b'<img src="/img" width="40" height="40"></body></html>')


class _H(http.server.BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):
        _H.hits.append(self.path)
        if self.path == "/r":
            self.send_response(302)
            self.send_header("Location", "/page")
            self.end_headers()
        elif self.path == "/page":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(PAGE)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _H.hits = []
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def cap(url, out, *extra):
    return subprocess.run(["node", "capture.mjs", "fx", url, "--bps", "mobile", "--out", str(out), "--wait", "0", *extra],
                          cwd=CAP, capture_output=True, text=True, timeout=120)


def test_capture_records_redirects_final_url_server_ip_and_page_identity(tmp_path, server):
    r = cap(f"{server}/r", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    meta = _json.loads((tmp_path / "fx" / "meta.json").read_text())
    nav = meta["navigation"]
    assert nav["final_url"] == f"{server}/page" and nav["hops"] == [f"{server}/r", f"{server}/page"]
    assert nav["server_ip"] == "127.0.0.1"
    assert meta["page"] == {"title": "Studio Home", "site_name": "Studio"}


def test_block_private_refuses_a_local_page(tmp_path, server):
    r = cap(f"{server}/page", tmp_path, "--block-private")
    assert r.returncode != 0 and "blocked" in (r.stderr + r.stdout).lower()


def test_block_private_blocks_local_subrequests(tmp_path, server):
    page = tmp_path / "p.html"
    page.write_text(f'<!doctype html><html><head><title>x</title></head><body><img src="{server}/img"></body></html>')
    r = cap(page.as_uri(), tmp_path, "--block-private")
    assert r.returncode == 0, r.stderr[-400:]
    meta = _json.loads((tmp_path / "fx" / "meta.json").read_text())
    assert any("/img" in b for b in meta["navigation"]["blocked"]) and "/img" not in _H.hits


@pytest.mark.parametrize("fixture,field", [("otp.html", "password"), ("iframe_pw.html", "password"),
                                           ("shadow_pw.html", "password"), ("stripe_iframe.html", "payment"),
                                           ("iban.html", "payment"), ("email_signin.html", "signin"),
                                           ("seed.html", "crypto")])
def test_sensitive_pages_are_detected(tmp_path, fixture, field):
    url = (ROOT / "tests" / "fixtures" / "capture" / fixture).as_uri()
    r = cap(url, tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    sens = _json.loads((tmp_path / "fx" / "meta.json").read_text())["sensitive"]
    assert sens[field] >= 1, (fixture, sens)


def test_a_newsletter_form_is_not_a_sign_in_page(tmp_path):
    r = cap((ROOT / "tests" / "fixtures" / "capture" / "newsletter.html").as_uri(), tmp_path)
    assert r.returncode == 0
    sens = _json.loads((tmp_path / "fx" / "meta.json").read_text())["sensitive"]
    assert sens == {"password": 0, "payment": 0, "signin": 0, "crypto": 0}
