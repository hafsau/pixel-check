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
    return {bp: png(*wh) for bp, wh in SIZES.items()}, {"sensitive": {"password": 0, "payment": 0}}


def login_capture(url, run_dir, emit):
    emit("capture")
    return {bp: png(*wh) for bp, wh in SIZES.items()}, {"sensitive": {"password": 1, "payment": 0}}


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
