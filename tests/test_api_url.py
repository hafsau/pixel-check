"""Live mode from a URL (orchestrator/api.py): capture the page at the three breakpoints in the sandbox, then the same
pipeline. Guards: ownership confirmation, public http(s) URLs only (no private / loopback / metadata addresses, no
credentials, standard ports), no rebuilding of login / payment pages. Written before the implementation (TDD,
Oct 5). Fake capture, fake resolver, fake pipeline — no network, no models."""
import time

import pytest
from fastapi.testclient import TestClient

from test_api import fake_pipeline, png, SIZES, wait_done

PUBLIC = {"example.com": ["93.184.216.34"], "www.example.org": ["2606:2800:220:1::1"]}


def resolver(host):
    if host in PUBLIC:
        return PUBLIC[host]
    if host in ("intranet.local", "rebind.example"):
        return ["10.0.0.5"] if host == "intranet.local" else ["93.184.216.34", "127.0.0.1"]
    raise OSError("no such host")


def fake_capture(url, run_dir, emit):
    emit("capture")
    return {bp: png(*wh) for bp, wh in SIZES.items()}, {"sensitive": {"password": 0, "payment": 0},
                                                         "navigation": {"final_url": url, "hops": [url], "server_ip": "93.184.216.34"}}


def login_capture(url, run_dir, emit):
    emit("capture")
    return {bp: png(*wh) for bp, wh in SIZES.items()}, {"sensitive": {"password": 1, "payment": 0},
                                                         "navigation": {"final_url": url, "hops": [url], "server_ip": "93.184.216.34"}}


def broken_capture(url, run_dir, emit):
    emit("capture")
    raise RuntimeError("navigation timeout; token=abc123")


def client(tmp_path, capture=fake_capture, **settings):
    from orchestrator.api import create_app
    s = {"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": []}
    s.update(settings)
    return TestClient(create_app(pipeline=fake_pipeline, capture=capture, resolver=resolver, live_dir=tmp_path, settings=s))


def post(c, url="https://example.com/pricing", owns="true", passcode="letmein"):
    return c.post("/api/runs/url", data={"url": url, "owns": owns, "passcode": passcode})


def test_public_url_runs_capture_then_the_pipeline(tmp_path):
    c = client(tmp_path)
    r = post(c)
    assert r.status_code == 202
    st = wait_done(c, r.json()["id"])
    assert st["state"] == "done" and [s["stage"] for s in st["stages"]][:3] == ["capture", "perceive", "compile"]
    assert st["source"] == {"url": "https://example.com/pricing"}


def test_ipv6_public_host_is_fine(tmp_path):
    assert post(client(tmp_path), url="https://www.example.org/").status_code == 202


@pytest.mark.parametrize("owns", ["", "false", "no"])
def test_ownership_must_be_confirmed(tmp_path, owns):
    r = post(client(tmp_path), owns=owns)
    assert r.status_code == 422 and "own" in r.text


@pytest.mark.parametrize("url", [
    "ftp://example.com/", "javascript:alert(1)", "file:///etc/passwd", "example.com", "https://",
    "http://localhost/", "http://127.0.0.1/", "http://[::1]/", "http://10.1.2.3/", "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/", "http://intranet.local/", "http://rebind.example/",
    "https://user:pw@example.com/", "https://example.com:8080/", "https://nosuchhost.invalid/",
    "https://example.com/" + "a" * 2100,
])
def test_unsafe_or_invalid_urls_are_refused(tmp_path, url):
    r = post(client(tmp_path), url=url)
    assert r.status_code == 422, (url, r.status_code, r.text)


def test_wrong_passcode_and_kill_switch_apply_to_urls_too(tmp_path):
    assert post(client(tmp_path), passcode="nope").status_code == 403
    assert post(client(tmp_path, enabled=False)).status_code == 503


def test_login_or_payment_pages_are_not_rebuilt(tmp_path):
    c = client(tmp_path, capture=login_capture)
    st = wait_done(c, post(c).json()["id"])
    assert st["state"] == "failed" and "password" in st["error"].lower()
    assert not (tmp_path / st.get("id", "x") / "bundle").exists()


def test_capture_failure_is_reported_scrubbed(tmp_path):
    c = client(tmp_path, capture=broken_capture)
    st = wait_done(c, post(c).json()["id"])
    assert st["state"] == "failed" and "abc123" not in st["error"]


def test_url_runs_share_the_caps_with_uploads(tmp_path):
    c = client(tmp_path, daily=1)
    assert post(c).status_code == 202
    assert post(c).status_code == 429


def test_refused_urls_do_not_use_up_the_cap(tmp_path):
    c = client(tmp_path, daily=1)
    post(c, url="http://127.0.0.1/")
    post(c, owns="false")
    assert post(c).status_code == 202


# council guardrails (Oct 5): category policy, private links, redirects / final URL / server IP, page identity
@pytest.mark.parametrize("url,word", [("https://chase.com/", "banking"), ("https://secure.chase.com/login", "banking"),
                                      ("https://www.paypal.com/", "payment"), ("https://paypal-secure.com/", "imitate"),
                                      ("https://example.com/reset?token=abc", "private")])
def test_policy_refusals_before_the_run(tmp_path, url, word):
    PUBLIC.update({"chase.com": ["93.184.216.34"], "secure.chase.com": ["93.184.216.34"],
                   "www.paypal.com": ["93.184.216.34"], "paypal-secure.com": ["93.184.216.34"]})
    c = client(tmp_path, daily=1)
    r = post(c, url=url)
    assert r.status_code == 422 and word in r.text.lower() and "upload your design frames" in r.text, r.text
    assert post(c).status_code == 202                       # refusals do not use up the cap


def test_stored_source_drops_query_and_fragment(tmp_path):
    c = client(tmp_path)
    st = wait_done(c, post(c, url="https://example.com/pricing?utm_source=x#plans").json()["id"])
    assert st["source"] == {"url": "https://example.com/pricing"}


def capture_with(meta_extra):
    def cap(url, run_dir, emit):
        emit("capture")
        meta = {"sensitive": {"password": 0, "payment": 0}, "navigation": {"final_url": url, "hops": [url],
                                                                           "server_ip": "93.184.216.34"}}
        for k, v in meta_extra.items():
            meta.setdefault(k, {}).update(v) if isinstance(v, dict) else meta.__setitem__(k, v)
        return {bp: png(*wh) for bp, wh in SIZES.items()}, meta
    return cap


@pytest.mark.parametrize("extra,word", [
    ({"navigation": {"final_url": "https://www.chase.com/", "hops": ["https://example.com/pricing", "https://www.chase.com/"]}}, "banking"),
    ({"navigation": {"hops": ["https://example.com/pricing", "http://169.254.169.254/latest/meta-data/"]}}, "public"),
    ({"navigation": {"server_ip": "10.0.0.7"}}, "public"),
    ({"page": {"title": "Sign in to your Chase account", "site_name": ""}}, "banking"),
    ({"navigation": {"final_url": "https://example.com/x?session=1"}}, "private"),
    # Phase 2: sizes are captured in parallel and each records where it ended up (a redirect at one width only)
    ({"navigation": {"final_urls": ["https://example.com/pricing", "https://www.chase.com/"]}}, "banking"),
    ({"navigation": {"final_urls": ["https://example.com/pricing", "http://10.0.0.8/admin"]}}, "public"),
    ({"navigation": {"server_ips": ["93.184.216.34", "192.168.1.4"]}}, "public"),
    ({"navigation": {"server_ips": ["not-an-ip"]}}, "public"),
    ({"pages": [{"title": "Studio", "site_name": ""}, {"title": "PayPal: log in", "site_name": ""}]}, "payment"),
])
def test_refusals_after_the_capture(tmp_path, extra, word):
    PUBLIC.setdefault("www.chase.com", ["93.184.216.34"])
    c = client(tmp_path, capture=capture_with(extra))
    st = wait_done(c, post(c).json()["id"])
    assert st["state"] == "failed" and word in st["error"].lower(), st
    assert not list(tmp_path.glob("*/bundle/run.json"))      # nothing rebuilt


def test_missing_navigation_record_is_refused(tmp_path):
    """The capture must say where it ended up; without that record the redirect check cannot run."""
    def cap(url, run_dir, emit):
        emit("capture")
        return {bp: png(*wh) for bp, wh in SIZES.items()}, {"sensitive": {"password": 0, "payment": 0}}
    c = client(tmp_path, capture=cap)
    st = wait_done(c, post(c).json()["id"])
    assert st["state"] == "failed" and "could not verify" in st["error"].lower()


@pytest.mark.parametrize("field", ["password", "payment", "signin", "crypto"])
def test_every_sensitive_signal_refuses(tmp_path, field):
    c = client(tmp_path, capture=capture_with({"sensitive": {field: 1}}))
    st = wait_done(c, post(c).json()["id"])
    assert st["state"] == "failed" and "does not rebuild" in st["error"], st


def test_default_capture_blocks_private_addresses():
    import inspect
    from orchestrator.api import default_capture
    assert "--block-private" in inspect.getsource(default_capture)


def test_code_rebuilt_from_a_url_carries_an_attribution_header(tmp_path):
    def pipe(run_id, frames, run_dir, emit):
        d = run_dir / "bundle" / "c" / "c1"
        d.mkdir(parents=True)
        (d / "App.jsx").write_text("export default function App() { return null; }\n")
        (run_dir / "bundle" / "run.json").write_text("{}")
        return {"match": 80.0}
    from orchestrator.api import create_app
    c = TestClient(create_app(pipeline=pipe, capture=fake_capture, resolver=resolver, live_dir=tmp_path,
                              settings={"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": []}))
    rid = post(c).json()["id"]
    wait_done(c, rid)
    code = c.get(f"/api/runs/{rid}/files/c/c1/App.jsx").text
    assert code.startswith("// Generated by PixelCheck from a capture of example.com") and "Replace third-party" in code
    assert code.rstrip().endswith("return null; }")


def test_per_visitor_daily_limit(tmp_path):
    c = client(tmp_path, per_ip=2)
    assert [post(c).status_code for _ in range(3)] == [202, 202, 429]
    other = c.post("/api/runs/url", data={"url": "https://example.com/", "owns": "true", "passcode": "letmein"},
                   headers={"X-Forwarded-For": "203.0.113.9"})
    assert other.status_code == 429                    # forwarded headers are ignored unless the proxy is trusted
    c2 = client(tmp_path, per_ip=2, trust_proxy=True)
    ok = c2.post("/api/runs/url", data={"url": "https://example.com/", "owns": "true", "passcode": "letmein"},
                 headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})
    assert ok.status_code == 202


def test_optional_url_allow_list(tmp_path):
    PUBLIC["hafsausmani.com"] = ["76.76.21.21"]
    c = client(tmp_path, url_allow=["hafsausmani.com"])
    assert post(c, url="https://hafsausmani.com/").status_code == 202
    r = post(c, url="https://example.com/")
    assert r.status_code == 422 and "only" in r.text.lower()


# Phase 2: owned sites (settings "owned_hosts") get a real screenshot and their own images; other pages do not
def recording_capture(calls):
    def cap(url, run_dir, emit, **kw):
        calls.append((url, kw))
        return fake_capture(url, run_dir, emit)
    return cap


@pytest.mark.parametrize("url,owned", [("https://example.com/", True), ("https://www.example.com/x", True),
                                       ("https://www.example.org/", False)])
def test_owned_hosts_capture_with_real_screenshots_and_images(tmp_path, url, owned):
    PUBLIC.setdefault("www.example.com", ["93.184.216.34"])
    calls = []
    c = client(tmp_path, capture=recording_capture(calls), owned_hosts=["example.com"])
    wait_done(c, post(c, url=url).json()["id"])
    assert calls and calls[0][1] == ({"owned": True} if owned else {})


def test_no_owned_hosts_means_plain_capture(tmp_path):
    calls = []
    c = client(tmp_path, capture=recording_capture(calls))
    wait_done(c, post(c).json()["id"])
    assert calls[0][1] == {}


def test_save_owned_keeps_only_verified_files(tmp_path):
    import hashlib
    import io
    import json
    from PIL import Image
    from orchestrator.api import _save_owned
    b = io.BytesIO()
    Image.new("RGB", (390, 844), "white").save(b, "PNG")
    real = b.getvalue()
    img = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(img, "PNG")
    img = img.getvalue()
    h = hashlib.sha256(img).hexdigest()
    man = {"assets": [{"hash": h, "ext": "png", "kind": "img", "bytes": len(img), "alt": "", "boxes": {"mobile": [[0, 0, 8, 8]]}}]}
    got = {"mobile.real.png": real, "tablet.real.png": b"not a png", "assets.json": json.dumps(man).encode(),
           f"assets/{h}.png": img, "../escape.png": real, "assets/../../x.png": img}
    _save_owned(got, tmp_path)
    assert (tmp_path / "real" / "mobile.png").read_bytes() == real
    assert not (tmp_path / "real" / "tablet.png").exists()
    assert (tmp_path / "assets" / f"{h}.png").read_bytes() == img
    assert json.loads((tmp_path / "assets.json").read_text())["assets"][0]["hash"] == h
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == sorted(["mobile.png", f"{h}.png", "assets.json"])


def test_files_endpoint_serves_assets_with_safe_headers(tmp_path):
    c = client(tmp_path)
    rid = post(c).json()["id"]
    wait_done(c, rid)
    d = tmp_path / rid / "bundle" / "assets"
    d.mkdir(parents=True, exist_ok=True)
    (d / ("a" * 64 + ".svg")).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    r = c.get(f"/api/runs/{rid}/files/assets/{'a' * 64}.svg")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in r.headers["content-security-policy"]


def test_owned_site_header_says_so_and_covers_the_delivered_code(tmp_path):
    def pipe(run_id, frames, run_dir, emit):
        for sub in ("c/c1", "display"):
            d = run_dir / "bundle" / sub
            d.mkdir(parents=True)
            (d / "App.jsx").write_text("export default function App() { return null; }\n")
        (run_dir / "bundle" / "run.json").write_text("{}")
        return {"match": 80.0}
    from orchestrator.api import create_app
    c = TestClient(create_app(pipeline=pipe, capture=recording_capture([]), resolver=resolver, live_dir=tmp_path,
                              settings={"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": [],
                                        "owned_hosts": ["example.com"]}))
    rid = post(c).json()["id"]
    wait_done(c, rid)
    for path in ("c/c1/App.jsx", "display/App.jsx"):
        code = c.get(f"/api/runs/{rid}/files/{path}").text
        assert code.startswith("// Generated by PixelCheck from example.com (an owned site)") and "third-party" not in code


def test_capture_uploads_include_every_local_module_the_scripts_import():
    """capture.mjs runs in the sandbox from uploaded files: each ./x.mjs it imports must be uploaded too."""
    import re
    from pathlib import Path
    from orchestrator.api import capture_files
    files = capture_files()
    here = Path(__file__).resolve().parents[1] / "tools" / "capture"
    for script in ("capture.mjs",):
        for mod in re.findall(r'from "\./([\w.-]+\.mjs)"', (here / script).read_text()):
            assert f"/opt/pc/{mod}" in files, mod
    assert files["/opt/pc/capture.mjs"] == (here / "capture.mjs").read_bytes()
