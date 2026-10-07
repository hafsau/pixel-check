"""Check mode capture (tools/capture/check_page.mjs, Phase 3): any deployed page measured the way the scorer measures
our own renders — {bp}.png / .dom.json / .notext.png / .coded.png at the three design sizes, layout health at the
in-between widths (overflow, text overlaps), as the page really looks (its own fonts and images), behind the same
URL guards as live mode. Local HTTP server; written before the script (TDD, Oct 6)."""
import http.server
import json
import os
import subprocess
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "tools" / "capture"
pytestmark = pytest.mark.skipif(not (CAP / "node_modules").exists() or not (ROOT / "sandbox" / "node_modules").exists(),
                                reason="capture / sandbox deps not installed")

FLUID = (b'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
         b'<title>Fluid</title><style>body{margin:0;font-family:Georgia,serif}main{max-width:900px;margin:0 auto;'
         b'padding:24px}h1{font-size:40px}</style></head><body><main><h1>Plan your week</h1><p>One calm list.</p>'
         b'<button>Start</button></main></body></html>')
WIDE = (b'<!doctype html><html><head><meta charset="utf-8"><title>Wide</title><style>body{margin:0}'
        b'.row{display:flex;gap:16px;width:620px}.row div{width:200px;height:80px;background:#ddd}</style></head><body>'
        b'<h1>Pricing</h1><div class="row"><div>Basic</div><div>Pro</div><div>Team</div></div></body></html>')
LOGIN = (b'<!doctype html><html><head><title>Sign in</title></head><body><h1>Sign in</h1>'
         b'<input type="password" name="pw"></body></html>')


HIDDEN = (b'<!doctype html><html><head><title>Hidden</title><style>body{margin:0}.egg{position:absolute;top:0;left:0;'
          b'opacity:0}</style></head><body><h1>Visible title</h1><p>Body copy here.</p>'
          b'<div class="egg"><h2>You found it!</h2><p>Secret line over the title</p></div></body></html>')
SPLIT = (b'<!doctype html><html><head><title>Split</title><style>body{margin:0}.c{display:inline-block;color:#222}</style></head>'
         b'<body><h1><span class="c">N</span><span class="c">A</span><span class="c">M</span><span class="c">E</span></h1>'
         b'<p>Plain <b>bold</b> text</p></body></html>')


class _H(http.server.BaseHTTPRequestHandler):
    routes = {"/fluid": FLUID, "/wide": WIDE, "/login": LOGIN, "/hidden": HIDDEN, "/split": SPLIT}

    def do_GET(self):
        body = self.routes.get(self.path)
        self.send_response(200 if body else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body or b"")

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def run(url, out, *extra):
    env = {**os.environ, "PC_RENDER": str(ROOT / "sandbox" / "render.mjs")}
    return subprocess.run(["node", "check_page.mjs", url, "--out", str(out), "--wait", "500", *extra],
                          cwd=CAP, capture_output=True, text=True, timeout=180, env=env)


def test_outputs_match_what_the_scorer_reads(tmp_path, server):
    r = run(f"{server}/fluid", tmp_path)
    assert r.returncode == 0, r.stderr[-600:]
    for bp in ("mobile", "tablet", "desktop"):
        for suffix in (".png", ".dom.json", ".notext.png", ".coded.png"):
            assert (tmp_path / f"{bp}{suffix}").exists(), bp + suffix
        dom = json.loads((tmp_path / f"{bp}.dom.json").read_text())
        texts = {d["text"] for d in dom}
        assert {"Plan your week", "One calm list.", "Start"} <= texts
        assert all(d.get("code") for d in dom)                     # colour-coded readability pass ran
    checks = json.loads((tmp_path / "checks.json").read_text())
    assert set(checks["breakpoints"]) == {"mobile", "tablet", "desktop"}
    assert {int(w) for w in checks["between"]} == {360, 375, 500, 1024, 1600}
    assert all(v["overflow_px"] == 0 for v in checks["between"].values())


def test_the_page_keeps_its_own_fonts(tmp_path, server):
    r = run(f"{server}/fluid", tmp_path)
    assert r.returncode == 0
    dom = json.loads((tmp_path / "desktop.dom.json").read_text())
    h1 = next(d for d in dom if d["text"] == "Plan your week")
    assert h1["font_family"].lower() != "inter"


def test_horizontal_overflow_is_reported_at_narrow_widths(tmp_path, server):
    r = run(f"{server}/wide", tmp_path)
    assert r.returncode == 0, r.stderr[-600:]
    checks = json.loads((tmp_path / "checks.json").read_text())
    assert checks["between"]["360"]["overflow_px"] > 200 and checks["between"]["1024"]["overflow_px"] == 0
    assert checks["breakpoints"]["mobile"]["overflow_px"] > 200


def test_meta_records_navigation_and_sensitive_fields(tmp_path, server):
    r = run(f"{server}/login", tmp_path)
    assert r.returncode == 0
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["sensitive"]["password"] >= 1
    assert meta["navigation"]["final_urls"] == [f"{server}/login"] and meta["page"]["title"] == "Sign in"


def test_block_private_refuses_local_addresses(tmp_path, server):
    r = run(f"{server}/fluid", tmp_path, "--block-private")
    assert r.returncode != 0 and "blocked" in (r.stdout + r.stderr).lower()


# the scoring side: sandbox/evaluate.py --check scores any page's capture against design frames — no anti-cheat
# verdict (someone else's code may use <img>, absolute layouts …), the width sweep reported with it
import shutil
import sys


def score_check(out, targets, texts=None):
    env = {**os.environ, "PC_OUT": str(out), "PC_TARGETS": str(targets)}
    r = subprocess.run([sys.executable, "evaluate.py", "--check"], cwd=ROOT / "sandbox", capture_output=True, text=True,
                       timeout=300, env=env)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout)


def test_check_scoring_a_page_against_its_own_screenshots_is_near_perfect(tmp_path, server):
    out, tg = tmp_path / "out", tmp_path / "targets"
    assert run(f"{server}/fluid", out).returncode == 0
    tg.mkdir()
    for bp in ("mobile", "tablet", "desktop"):
        shutil.copy(out / f"{bp}.png", tg / f"{bp}.png")
        (tg / f"{bp}.text.json").write_text(json.dumps(["Plan your week", "One calm list.", "Start"]))
    res = score_check(out, tg)
    assert res["mode"] == "check" and res["disqualified"] is False and "integrity_failures" not in res
    assert res["match"] >= 95 and res["fluidity"]["pass"] is True


def test_check_scoring_reports_a_different_page_and_its_overflow(tmp_path, server):
    a, b, tg = tmp_path / "a", tmp_path / "b", tmp_path / "targets"
    assert run(f"{server}/fluid", a).returncode == 0 and run(f"{server}/wide", b).returncode == 0
    tg.mkdir()
    for bp in ("mobile", "tablet", "desktop"):
        shutil.copy(a / f"{bp}.png", tg / f"{bp}.png")
    res = score_check(b, tg)
    assert res["match"] < 60 and res["fluidity"]["pass"] is False and 360 in [int(w) for w in res["fluidity"]["fails"] if str(w).isdigit()]


def test_invisible_text_does_not_count_as_overlapping(tmp_path, server):
    r = run(f"{server}/hidden", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    checks = json.loads((tmp_path / "checks.json").read_text())
    assert all(v["text_overlaps"] == 0 for v in checks["between"].values())
    assert checks["breakpoints"]["mobile"]["text_overlaps"] == 0


def test_split_letter_headings_are_one_text_in_the_build_dom(tmp_path, server):
    r = run(f"{server}/split", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    texts = [d["text"] for d in json.loads((tmp_path / "mobile.dom.json").read_text())]
    assert "NAME" in texts and not any(t in texts for t in ("N", "M", "E"))
    assert any(t.startswith("Plain") for t in texts) and "bold" in texts      # ordinary inline text as before


def test_a_split_word_is_painted_in_its_code_colour_so_it_reads_as_visible(tmp_path, server):
    """The readability pass paints each text its own colour; letters with their own CSS colour must take it too."""
    import numpy as np
    from PIL import Image
    r = run(f"{server}/split", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    dom = json.loads((tmp_path / "mobile.dom.json").read_text())
    name = next(d for d in dom if d["text"] == "NAME")
    code = [int(v) for v in name["code"].strip("rgb()").split(",")]
    x, y, w, h = name["box"]
    im = np.asarray(Image.open(tmp_path / "mobile.coded.png").convert("RGB")).astype(int)[y:y + h, x:x + w]
    assert int((np.abs(im - code).sum(axis=2) < 30).sum()) > 50
