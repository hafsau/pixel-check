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
