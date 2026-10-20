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


FADE = (b'<!doctype html><html><head><title>Fade</title><style>body{margin:0}@keyframes in{to{opacity:1}}'
        b'h1,p{opacity:0;animation:in 1s ease forwards}</style></head><body><h1>Plan your week</h1><p>One calm list.</p>'
        b'</body></html>')
CLIP = (b'<!doctype html><html><head><title>Clip</title><style>body{margin:0}.wrap{overflow-x:hidden;width:100%}'
        b'.row{display:flex;gap:16px;width:620px}.row div{width:200px}</style></head><body><h1>Pricing</h1><div class="wrap">'
        b'<div class="row"><div>Basic plan</div><div>Pro plan</div><div>Team plan</div></div></div></body></html>')
SHOT = (b'<!doctype html><html><head><title>Shot</title><style>body{margin:0}img{display:block;width:100vw;height:100vh;'
        b'background:#ccd}</style></head><body><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" alt=""></body></html>')
EXACT = (b'<!doctype html><html><head><title>Exact</title><style>body{margin:0}@media (width: 390px){h1{color:red}}'
         b'@media (min-width: 768px) and (max-width: 768px){h1{color:blue}}</style></head><body><h1>Hi there</h1></body></html>')

# honest designs that clip on purpose (found on hafsausmani.com with image v18, Oct 12): a marquee ticker, a carousel
# whose cards peek past the edge, display type whose last glyph overshoots by a few px
MARQUEE = (b'<!doctype html><html><head><title>Marquee</title><style>body{margin:0}.m{overflow:hidden}'
           b'.t{display:flex;gap:40px;width:max-content;animation:scroll 20s linear infinite}'
           b'@keyframes scroll{to{transform:translateX(-50%)}}</style></head><body><h1>Skills</h1><div class="m"><div class="t">'
           + b"".join(b"<span>Figma</span><span>Design Systems</span><span>Prototyping</span><span>Research</span>" for _ in range(4))
           + b'</div></div></body></html>')
CAROUSEL = (b'<!doctype html><html><head><title>Carousel</title><style>body{margin:0}.c{overflow:hidden}'
            b'.track{display:flex;gap:16px;transform:translateX(-40px)}.card{flex:none;width:300px}</style></head><body>'
            b'<h1>Work</h1><div class="c"><div class="track"><div class="card">EqualTales AI</div><div class="card">'
            b'Creative Experiments</div><div class="card">Design tooling</div></div></div></body></html>')
BLEED = (b'<!doctype html><html><head><title>Bleed</title><style>body{margin:0}.b{overflow:hidden}'
         b'.b span{display:block;width:calc(100vw + 4px);font-size:120px;line-height:1}</style></head><body>'
         b'<div class="b"><span>Hi</span></div><p>Designer and engineer</p></body></html>')

NESTED = (b'<!doctype html><html><head><title>Nested</title><style>body{margin:0}'
          b'@media (min-width: 1071px){@media (max-width: 1072px){h1{color:red}}}</style></head>'
          b'<body><h1>Hi there</h1></body></html>')

# Oct 13 (Hafsa's own apps): a full-page background picture with real text on top is a design, not a screenshot
# build; a platform's floating badge ("Edit with Lovable") overlapping content is the platform, not the layout
BGHERO = (b'<!doctype html><html><head><title>Hero</title><style>body{margin:0}.hero{min-height:100vh;'
          b'background:#203040 url("data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7") '
          b'center/cover;color:#fff;padding:40px}</style></head><body><div class="hero"><h1>Stories that change beliefs</h1>'
          b'<p>Type the stereotype your child has expressed.</p><p>We create a personalised story.</p>'
          b'<a href="#">Try it now</a></div></body></html>')
BADGE = (b'<!doctype html><html><head><title>Badge</title><style>body{margin:0;font:16px sans-serif}'
         b'main{padding:20px}.out{position:fixed;right:8px;bottom:8px;background:#111;color:#fff;padding:6px 10px;'
         b'font-size:13px}.result{position:fixed;right:8px;bottom:10px;font-size:14px}</style></head><body>'
         b'<main><h1>Headshots</h1><p>Upload a photo.</p></main><div class="result">Your headshot will appear here</div>'
         b'<a class="out" href="https://lovable.dev">Edit with Lovable</a></body></html>')

SHADOWBADGE = (b'<!doctype html><html><head><title>Pill</title><style>body{margin:0;font:16px sans-serif}main{padding:20px}'
               b'.go{position:fixed;left:20px;bottom:16px;width:240px;padding:12px;background:#7c3aed;color:#fff}</style></head>'
               b'<body><main><h1>Interview questions</h1></main><button class="go">Generate Questions</button>'
               b'<div id="replit-pill-host"></div><script>const h=document.getElementById("replit-pill-host").attachShadow('
               b'{mode:"closed"});h.innerHTML=\'<a href="https://replit.com" style="position:fixed;right:24px;bottom:20px;'
               b'padding:8px 14px;background:#222;color:#fff;font:13px sans-serif">Made with Replit</a>\';</script></body></html>')

# Oct 20 council: the badge test used each text element's whole box — a full-width heading counted as "covered" when its
# letters were nowhere near the badge (the Lovable dashboard's "Weekly Activity"). Text is judged by its glyphs; a
# button or link by its box (part of a tap target covered matters even if the label is readable)
WIDEHEAD = (b'<!doctype html><html><head><title>Wide</title><style>body{margin:0;font:16px sans-serif}main{padding:20px}'
            b'h2{position:fixed;left:0;right:0;bottom:6px;margin:0;padding:4px 16px;font-size:18px;text-align:left}'
            b'.out{position:fixed;right:8px;bottom:6px;background:#111;color:#fff;padding:6px 10px;font-size:13px}</style>'
            b'</head><body><main><h1>Dashboard</h1></main><h2>Weekly Activity</h2>'
            b'<a class="out" href="https://lovable.dev">Edit with Lovable</a></body></html>')

# a button's name is its visible text with spaces between lines, cut at a word ("Drop your selfie hereor click to browseP")
BUTTONNAME = (b'<!doctype html><html><head><title>Upload</title><style>body{margin:0;font:16px sans-serif}main{padding:20px}'
              b'.drop{position:fixed;left:10px;right:10px;bottom:6px;display:block;padding:10px;text-align:left}'
              b'.drop span,.drop small{display:block}.out{position:fixed;right:8px;bottom:8px;background:#111;color:#fff;'
              b'padding:6px 10px;font-size:13px}</style></head><body><main><h1>Headshots</h1></main><button class="drop">'
              b'<span>Drop your selfie here</span><span>or click to browse</span><small>PNG, JPG up to 10MB</small></button>'
              b'<a class="out" href="https://lovable.dev">Edit with Lovable</a></body></html>')


class _H(http.server.BaseHTTPRequestHandler):
    routes = {"/fluid": FLUID, "/wide": WIDE, "/login": LOGIN, "/hidden": HIDDEN, "/split": SPLIT, "/fade": FADE,
              "/clip": CLIP, "/shot": SHOT, "/exact": EXACT,
              "/marquee": MARQUEE, "/carousel": CAROUSEL, "/bleed": BLEED,
              "/nested": NESTED, "/bghero": BGHERO, "/badge": BADGE, "/shadowbadge": SHADOWBADGE, "/widehead": WIDEHEAD, "/buttonname": BUTTONNAME}

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


# repair feedback needs (Oct 7): each element's background colour in nodes.json (block feedback) and, per width,
# the elements that stick out past the screen (sideways-scroll culprits)
def test_nodes_carry_background_colours_and_overflow_names_its_culprits(tmp_path, server):
    r = run(f"{server}/wide", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    nodes = json.loads((tmp_path / "mobile.nodes.json").read_text())
    tiles = [n for n in nodes if n.get("bg") == "rgb(221, 221, 221)"]
    assert len(tiles) == 3
    checks = json.loads((tmp_path / "checks.json").read_text())
    culprits = checks["between"]["360"]["overflowers"]
    assert culprits and culprits[0]["right"] > 600 and culprits[0]["w"] >= 600   # the 620 px row, not its children
    assert len(culprits) <= 5 and not checks["between"]["1024"]["overflowers"]



# red-team council (Oct 8): fade-in pages froze invisible, clipping hid sideways overflow, screenshot builds and
# exact-width media queries passed silently
def test_fade_in_content_is_captured_in_its_end_state(tmp_path, server):
    r = run(f"{server}/fade", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    dom = {d["text"]: d for d in json.loads((tmp_path / "mobile.dom.json").read_text())}
    assert dom["Plan your week"]["inked"] and dom["One calm list."]["inked"]


def test_text_cut_off_by_a_clipping_wrapper_counts_as_overflow(tmp_path, server):
    r = run(f"{server}/clip", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    checks = json.loads((tmp_path / "checks.json").read_text())
    v = checks["between"]["360"]
    assert v["overflow_px"] == 0 and v["clipped_overflow_px"] > 100
    assert any("plan" in (c.get("text") or "").lower() for c in v["overflowers"])
    assert checks["between"]["1024"]["clipped_overflow_px"] == 0



@pytest.mark.parametrize("page", ["marquee", "carousel", "bleed"])
def test_clipping_on_purpose_is_not_overflow(tmp_path, server, page):
    r = run(f"{server}/{page}", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    between = json.loads((tmp_path / "checks.json").read_text())["between"]
    assert {w: v["clipped_overflow_px"] for w, v in between.items()} == {w: 0 for w in between}


def test_a_screenshot_build_is_flagged(tmp_path, server):
    r = run(f"{server}/shot", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    w = json.loads((tmp_path / "checks.json").read_text())["warnings"]
    assert any("picture covers" in x for x in w)


def test_exact_width_media_queries_are_flagged(tmp_path, server):
    r = run(f"{server}/exact", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    w = json.loads((tmp_path / "checks.json").read_text())["warnings"]
    assert any("exactly 390" in x for x in w) and any("exactly 768" in x for x in w)


def test_an_honest_page_has_no_warnings(tmp_path, server):
    r = run(f"{server}/fluid", tmp_path)
    assert json.loads((tmp_path / "checks.json").read_text())["warnings"] == []


def test_a_runs_own_sizes_are_captured(tmp_path, server):
    sizes = {"mobile": [402, 870], "tablet": [768, 1024], "desktop": [1071, 1177]}
    (tmp_path / "sizes.json").write_text(json.dumps(sizes))
    r = run(f"{server}/fluid", tmp_path / "out", "--sizes", str(tmp_path / "sizes.json"))
    assert r.returncode == 0, r.stderr[-400:]
    checks = json.loads((tmp_path / "out" / "checks.json").read_text())
    assert {bp: [v["width"], v["height"]] for bp, v in checks["breakpoints"].items()} == sizes == checks["sizes"]
    assert sorted(int(w) for w in checks["between"]) == [360, 375, 585, 920, 1600]
    b = (tmp_path / "out" / "desktop.png").read_bytes()
    assert (int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")) == (1071, 1177)


def test_a_nested_media_window_at_a_runs_own_width_is_flagged(tmp_path, server):
    """Red team (Oct 12): a 2 px window built from nested @media rules at the run's desktop width (1071) slipped
    past the check, which only looked at single rules and the standard widths."""
    (tmp_path / "sizes.json").write_text(json.dumps({"mobile": [402, 870], "tablet": [768, 1024], "desktop": [1071, 1177]}))
    r = run(f"{server}/nested", tmp_path / "out", "--sizes", str(tmp_path / "sizes.json"))
    assert r.returncode == 0, r.stderr[-400:]
    w = json.loads((tmp_path / "out" / "checks.json").read_text())["warnings"]
    assert any("exactly 1071" in x for x in w), w


def test_a_background_picture_with_real_text_on_top_is_not_called_a_screenshot(tmp_path, server):
    r = run(f"{server}/bghero", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    w = json.loads((tmp_path / "checks.json").read_text())["warnings"]
    assert not any("picture covers" in x for x in w), w


def test_a_platform_badge_is_reported_apart_from_the_layout(tmp_path, server):
    r = run(f"{server}/badge", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    checks = json.loads((tmp_path / "checks.json").read_text())
    assert all(v["text_overlaps"] == 0 for v in checks["between"].values()), checks["between"]
    assert all(v["text_overlaps"] == 0 for v in checks["breakpoints"].values())
    assert any("Edit with Lovable" in x and "badge" in x and "Your headshot" in x for x in checks["warnings"]), checks["warnings"]


def test_a_badge_inside_a_closed_shadow_root_is_found_by_its_host(tmp_path, server):
    """interview-sage (Replit): "Made with Replit" lives in a closed shadow root on #replit-pill-host and sits over the
    Generate button on phones — no text or link matching can see it."""
    r = run(f"{server}/shadowbadge", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    w = json.loads((tmp_path / "checks.json").read_text())["warnings"]
    assert any("Replit" in x and "Generate Questions" in x for x in w), w


def test_a_badge_over_a_wide_heading_box_but_not_its_letters_is_not_reported(tmp_path, server):
    r = run(f"{server}/widehead", tmp_path)
    assert r.returncode == 0, r.stderr[-400:]
    w = json.loads((tmp_path / "checks.json").read_text())["warnings"]
    assert not any("Weekly Activity" in x for x in w), w


def test_a_badge_over_part_of_a_button_says_so(tmp_path, server):
    r = run(f"{server}/shadowbadge", tmp_path)
    w = json.loads((tmp_path / "checks.json").read_text())["warnings"]
    assert any('covers part of the "Generate Questions" button' in x for x in w), w


def test_a_covered_buttons_name_reads_like_its_label(tmp_path, server):
    run(f"{server}/buttonname", tmp_path)
    w = json.loads((tmp_path / "checks.json").read_text())["warnings"]
    assert any('covers part of the "Drop your selfie here or click to browse' in x for x in w), w
    assert not any("hereor" in x or "browseP" in x for x in w), w
