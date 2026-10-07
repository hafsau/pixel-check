"""Check mode API (orchestrator/api.py POST /api/checks, Phase 3): three design frames + a build (a deployed URL or
an App.jsx) → a check run polled like a live run; the result bundle holds check.json + the design and build frames.
Same gates as live mode: kill switch, passcode, caps, ownership confirmation and the URL policy for URLs; the
capture is verified (navigation, sensitive fields) before scoring. Fake checker, fake resolver. TDD, Oct 6."""
import json

from fastapi.testclient import TestClient

from test_api import SIZES, png, wait_done
from test_api_url import PUBLIC, resolver


def fake_checker(kind, build, frames, run_dir, emit, verify):
    emit("capture" if kind == "url" else "render")
    if kind == "url":
        verify({"sensitive": {"password": 0}, "navigation": {"final_url": build, "final_urls": [build], "hops": [build],
                                                            "server_ip": "93.184.216.34"}, "page": {"title": "Build"}})
    emit("score")
    return {"report": {"mode": "check", "match": 64.2, "per_bp": {"mobile": 64.2, "tablet": 70.0, "desktop": 80.1},
                       "breakpoints": {"mobile": {"score": 64.2, "missing_text": ["Start"]}},
                       "fluidity": {"pass": False, "fails": [360], "widths": {"360": {"overflow": 220, "ok": False}}}},
            "build": {bp: png(*wh, (200, 200, 200)) for bp, wh in SIZES.items()}, "meta": {},
            "design_texts": {"mobile": [{"text": "Start", "box": [1, 2, 3, 4]}]}}


def login_checker(kind, build, frames, run_dir, emit, verify):
    verify({"sensitive": {"password": 1}, "navigation": {"final_url": build, "final_urls": [build], "hops": [build]}})
    raise AssertionError("must not get here")


def client(tmp_path, checker=fake_checker, **settings):
    from orchestrator.api import create_app
    s = {"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": []}
    s.update(settings)
    return TestClient(create_app(checker=checker, resolver=resolver, live_dir=tmp_path, settings=s))


def post(c, url="https://example.com/app", code=None, owns="true", passcode="letmein", sizes=SIZES):
    files = {bp: ("f.png", png(*wh), "image/png") for bp, wh in sizes.items()}
    data = {"owns": owns, "passcode": passcode, **({"url": url} if url is not None else {}), **({"code": code} if code else {})}
    return c.post("/api/checks", files=files, data=data)


def test_a_url_check_runs_and_bundles_its_report(tmp_path):
    c = client(tmp_path)
    r = post(c)
    assert r.status_code == 202, r.text
    st = wait_done(c, r.json()["id"])
    assert st["state"] == "done" and st["kind"] == "check" and st["result"]["match"] == 64.2
    assert st["source"] == {"url": "https://example.com/app"}
    rep = c.get(st["bundle"]).json()
    assert rep["type"] == "check" and rep["report"]["fluidity"]["fails"] == [360]
    assert rep["design"]["mobile"].startswith("design/") and rep["build"]["mobile"].startswith("build/")
    assert c.get(f"/api/runs/{r.json()['id']}/files/{rep['build']['desktop']}").status_code == 200


def test_a_code_check_needs_no_url(tmp_path):
    c = client(tmp_path)
    r = post(c, url=None, code="export default function App(){return <main>Hi</main>}")
    assert r.status_code == 202, r.text
    st = wait_done(c, r.json()["id"])
    assert st["state"] == "done" and st["source"] == {"code": True}


def test_exactly_one_of_url_or_code(tmp_path):
    c = client(tmp_path)
    assert post(c, url=None).status_code == 422
    assert post(c, code="export default function App(){return null}").status_code == 422


def test_gates_match_live_mode(tmp_path):
    assert post(client(tmp_path, enabled=False)).status_code == 503
    assert post(client(tmp_path), passcode="nope").status_code == 403
    assert post(client(tmp_path), owns="").status_code == 422
    assert post(client(tmp_path), url="http://10.0.0.5/").status_code == 422
    PUBLIC.setdefault("www.chase.com", ["93.184.216.34"])
    r = post(client(tmp_path), url="https://www.chase.com/")
    assert r.status_code == 422 and "does not" in r.json()["detail"]


def test_frames_must_have_the_design_sizes(tmp_path):
    bad = dict(SIZES, tablet=(800, 1000))
    assert post(client(tmp_path), sizes=bad).status_code == 422


def test_sensitive_builds_are_refused_after_the_capture(tmp_path):
    c = client(tmp_path, checker=login_checker)
    st = wait_done(c, post(c).json()["id"])
    assert st["state"] == "failed" and "does not" in st["error"]


def test_checks_share_the_run_caps(tmp_path):
    c = client(tmp_path, daily=1)
    assert post(c).status_code == 202
    assert post(c).status_code == 429


def test_code_too_large_is_refused(tmp_path):
    assert post(client(tmp_path), url=None, code="x" * 300_001).status_code == 413
