"""Check mode API (orchestrator/api.py POST /api/checks, Phase 3): three design frames + a build (a deployed URL or
an App.jsx) → a check run polled like a live run; the result bundle holds check.json + the design and build frames.
Same gates as live mode: kill switch, passcode, caps, ownership confirmation and the URL policy for URLs; the
capture is verified (navigation, sensitive fields) before scoring. Fake checker, fake resolver. TDD, Oct 6."""
import json

import pytest

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


def test_frames_must_be_within_the_bounds(tmp_path):
    """Oct 12: check mode takes the same frames as a rebuild (any width 320–1600, any height)."""
    assert post(client(tmp_path), sizes=dict(SIZES, tablet=(300, 1000))).status_code == 422
    assert post(client(tmp_path), sizes=dict(SIZES, tablet=(800, 1000))).status_code == 202


def test_repair_needs_the_standard_sizes_for_now(tmp_path):
    files = {bp: ("f.png", png(*wh), "image/png") for bp, wh in dict(SIZES, desktop=(1071, 1177)).items()}
    r = client(tmp_path).post("/api/checks", files=files, data={"owns": "true", "passcode": "letmein", "repair": "true",
                                                                "code": "export default function App(){return null}"})
    assert r.status_code == 422 and "standard frame sizes" in r.text


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


# "Repair it" (Oct 7): an App.jsx check can ask for the Nemotron repair loop; the bundle gets the repaired code,
# before / after scores, the rounds and the share of the author's lines kept
def fake_repairer(code, frames, run_dir, emit):
    emit("repair")
    return {"code": code.replace("w-[1280px]", "w-full max-w-[1280px]"), "lines_kept": 0.9,
            "start": {"worst": 21.3, "per_bp": {"mobile": 21.3}, "fluid_fails": 4},
            "best": {"worst": 30.3, "per_bp": {"mobile": 30.3}, "fluid_fails": 0},
            "history": [{"round": 0, "worst": 21.3}, {"round": 1, "worst": 30.3}], "usd": 0.02}


def repair_client(tmp_path):
    from orchestrator.api import create_app
    s = {"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": []}
    return TestClient(create_app(checker=fake_checker, repairer=fake_repairer, resolver=resolver, live_dir=tmp_path, settings=s))


def test_a_code_check_can_be_repaired_and_the_bundle_has_both_versions(tmp_path):
    c = repair_client(tmp_path)
    code = 'export default function App(){return <main className="w-[1280px]">Hi</main>}'
    files = {bp: ("f.png", png(*wh), "image/png") for bp, wh in SIZES.items()}
    r = c.post("/api/checks", files=files, data={"code": code, "owns": "true", "passcode": "letmein", "repair": "true"})
    assert r.status_code == 202, r.text
    st = wait_done(c, r.json()["id"])
    assert st["state"] == "done" and [s["stage"] for s in st["stages"]][-2:] == ["repair", "brief"] and st["repair"] is True
    assert st["result"]["repair"] == {"before": 21.3, "after": 30.3, "lines_kept": 0.9}
    rep = c.get(st["bundle"]).json()["repair"]
    assert rep["code"] == "repair/App.jsx" and rep["original"] == "original/App.jsx" and rep["history"][1]["worst"] == 30.3
    rid = r.json()["id"]
    assert "max-w-[1280px]" in c.get(f"/api/runs/{rid}/files/repair/App.jsx").text
    assert c.get(f"/api/runs/{rid}/files/original/App.jsx").text == code


def test_repair_needs_code_not_a_url(tmp_path):
    c = repair_client(tmp_path)
    files = {bp: ("f.png", png(*wh), "image/png") for bp, wh in SIZES.items()}
    r = c.post("/api/checks", files=files, data={"url": "https://example.com/app", "owns": "true", "passcode": "letmein",
                                                 "repair": "true"})
    assert r.status_code == 422 and "App.jsx" in r.json()["detail"]


def test_a_failing_repair_keeps_the_check_result(tmp_path):
    from orchestrator.api import create_app

    def broken_repairer(code, frames, run_dir, emit):
        emit("repair")
        raise RuntimeError("sandbox spawn failed: 503")
    s = {"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": []}
    c = TestClient(create_app(checker=fake_checker, repairer=broken_repairer, resolver=resolver, live_dir=tmp_path, settings=s))
    files = {bp: ("f.png", png(*wh), "image/png") for bp, wh in SIZES.items()}
    r = c.post("/api/checks", files=files, data={"code": "export default function App(){return null}", "owns": "true",
                                                 "passcode": "letmein", "repair": "true"})
    st = wait_done(c, r.json()["id"])
    assert st["state"] == "done" and st["result"]["match"] == 64.2
    rep = c.get(st["bundle"]).json()
    assert rep["report"]["match"] == 64.2 and "could not finish" in rep["repair"]["error"] and "503" in rep["repair"]["error"]


# audits without designs (Oct 13): a URL and no frames
def audit_checker(kind, build, frames, run_dir, emit, verify):
    assert kind == "audit" and frames == {}
    verify({"sensitive": {"password": 0}, "navigation": {"final_url": build, "final_urls": [build], "hops": [build],
                                                        "server_ip": "93.184.216.34"}, "page": {"title": "App"}})
    return {"report": {"mode": "audit", "fluidity": {"pass": True, "fails": []}, "vanished": {"mobile": ["Dashboard"]},
                       "warnings": []},
            "build": {bp: png(*wh, (200, 200, 200)) for bp, wh in SIZES.items()}, "meta": {}, "design_texts": {}}


def test_a_url_without_frames_is_audited(tmp_path):
    c = client(tmp_path, checker=audit_checker)
    r = c.post("/api/checks", data={"url": "https://example.com/app", "owns": "true", "passcode": "letmein"})
    assert r.status_code == 202, r.text
    st = wait_done(c, r.json()["id"])
    assert st["state"] == "done" and st["audit"] is True and st["result"]["match"] is None
    bundle = c.get(st["bundle"]).json()
    assert bundle["report"]["mode"] == "audit" and bundle["report"]["vanished"]["mobile"] == ["Dashboard"]
    assert bundle["design"] == {}


def test_an_audit_needs_a_url_all_or_no_frames_and_no_repair(tmp_path):
    c = client(tmp_path, checker=audit_checker)
    base = {"owns": "true", "passcode": "letmein"}
    r = c.post("/api/checks", data={**base, "code": "export default function App(){return null}"})
    assert r.status_code == 422 and "address" in r.text
    one = {"mobile": ("f.png", png(390, 844), "image/png")}
    r = c.post("/api/checks", files=one, data={**base, "url": "https://example.com/app"})
    assert r.status_code == 422 and "all three frames" in r.text
    r = c.post("/api/checks", data={**base, "url": "https://example.com/app", "repair": "true"})
    assert r.status_code == 422


class _Stop(Exception):
    pass


def _meter_spy(monkeypatch):
    """Sandbox() replaced by a spy that records its meter, then stops the run."""
    from orchestrator import sandbox
    seen = {}

    def spy(*a, meter=None, **k):
        seen["meter"] = meter
        raise _Stop
    monkeypatch.setattr(sandbox, "Sandbox", spy)
    return seen


def test_check_and_audit_sandbox_cost_counts_in_the_run_budget(tmp_path, monkeypatch):
    from orchestrator import api, tf_client
    for kind in ("audit", "url", "code"):
        seen = _meter_spy(monkeypatch)
        try:
            api.default_checker(kind, "https://example.com/", {}, tmp_path / "r1", lambda *a, **k: None, lambda m: None)
        except _Stop:
            pass
        assert isinstance(seen.get("meter"), tf_client.TFClient), kind


def test_repair_sandbox_cost_counts_in_its_three_run_budget(tmp_path, monkeypatch):
    from orchestrator import api, config, tf_client
    seen = _meter_spy(monkeypatch)
    try:
        api.default_repairer("export default function App(){return null}", {}, tmp_path / "r1", lambda *a, **k: None)
    except _Stop:
        pass
    assert isinstance(seen.get("meter"), tf_client.TFClient)
    assert seen["meter"].run_budget == 3 * config.LIVE_RUN_BUDGET_USD    # a repair weighs 3 runs


def test_a_check_bundle_carries_diagnostics_beside_the_score(tmp_path):
    """Oct 13 council: the score is explained (text status, drift, points lost, named differences), not changed."""
    def checker(*a):
        out = fake_checker(*a)
        out["dom"] = {"mobile": [{"text": "Start", "box": [1, 400, 41, 20], "font_size": "14px", "font_family": "Roboto"}]}
        out["fonts"] = {"body": "Lato"}
        out["report"]["breakpoints"]["mobile"].update(components={"structure": .5, "layout": .6, "text": .5, "color": .8},
                                                      offset_px=[0, 0])
        return out
    c = client(tmp_path, checker=checker)
    st = wait_done(c, post(c).json()["id"])
    rep = c.get(st["bundle"]).json()
    m = rep["diagnostics"]["mobile"]
    assert m["text"] == [{"text": "Start", "status": "moved", "dy": 406, "dx": 19}]
    assert m["font"] == {"design": "Lato", "build": "Roboto"}
    assert sum(m["lost"].values()) == pytest.approx(100 - 64.2, abs=0.05)
    assert rep["report"]["breakpoints"]["mobile"]["score"] == 64.2       # the score itself is untouched


def test_an_audit_has_no_design_diagnostics(tmp_path):
    c = client(tmp_path, checker=audit_checker)
    r = c.post("/api/checks", data={"url": "https://example.com/app", "owns": "true", "passcode": "letmein"})
    rep = c.get(wait_done(c, r.json()["id"])["bundle"]).json()
    assert rep.get("diagnostics") in (None, {})


def test_a_check_bundle_records_its_frame_sizes(tmp_path):
    """The result page draws the frames and the width strip at the run's own sizes (frames come at any width)."""
    c = client(tmp_path)
    rep = c.get(wait_done(c, post(c).json()["id"])["bundle"]).json()
    assert rep["sizes"] == {bp: list(wh) for bp, wh in SIZES.items()}


# ---- fix brief (Oct 20): Nemotron writes what to do next; a verifier keeps only backed claims

def _diag_checker(client=None):
    def checker(*a):
        out = fake_checker(*a)
        out["dom"] = {"mobile": [{"text": "Start", "box": [1, 400, 41, 20], "font_size": "14px", "font_family": "Roboto"}]}
        out["fonts"] = {"body": "Lato"}
        out["report"]["breakpoints"]["mobile"].update(components={"structure": .5, "layout": .6, "text": .5, "color": .8},
                                                      offset_px=[0, 0])
        if client is not None:
            out["client"] = client
        return out
    return checker


def test_a_check_bundle_carries_a_fix_brief_written_from_its_facts(tmp_path):
    c = client(tmp_path, checker=_diag_checker())
    st = wait_done(c, post(c).json()["id"])
    assert any(s["stage"] == "brief" for s in st["stages"])
    b = c.get(st["bundle"]).json()["brief"]
    assert b["source"] == "template" and b["intro"].startswith("Please")      # no model client given: the template
    assert any("Lato" in i["text"] for i in b["fix"]) and b["facts"]


def test_the_brief_uses_the_checks_own_nemotron_client_and_its_cost_counts(tmp_path):
    import json as _json

    class Client:
        run_spend = 0.0

        def chat(self, model, messages, **kw):
            self.run_spend += 0.002
            facts = [l.split(" ", 1)[0] for l in messages[1]["content"].splitlines() if l.startswith("F")]
            font = next(l.split(" ", 1)[0] for l in messages[1]["content"].splitlines() if "font" in l)
            return type("R", (), {"content": _json.dumps({"summary": [], "fix_prompt": [
                {"text": "Use Lato instead of Roboto.", "facts": [font]}, {"text": "Add a hero video.", "facts": facts[:1]}]})})()
    cl = Client()
    c = client(tmp_path, checker=_diag_checker(cl))
    st = wait_done(c, post(c).json()["id"])
    rep = c.get(st["bundle"]).json()
    assert rep["brief"]["source"] == "nemotron" and rep["brief"]["dropped"] == 1
    fix = [(i["text"], i.get("added", False)) for i in rep["brief"]["fix"]]
    assert fix[0] == ("Use Lato instead of Roboto.", False)
    assert ("At 360 px, the page scrolls sideways by 220 px: make each element fit the screen width.", True) in fix   # uncovered
    assert rep["usd"] == pytest.approx(0.002) and st["result"]["usd"] == pytest.approx(0.002)
    assert "client" not in rep


def test_an_audit_gets_a_brief_too(tmp_path):
    c = client(tmp_path, checker=audit_checker)
    r = c.post("/api/checks", data={"url": "https://example.com/app", "owns": "true", "passcode": "letmein"})
    b = c.get(wait_done(c, r.json()["id"])["bundle"]).json()["brief"]
    assert b["intro"].startswith("Please fix these issues")


def test_a_failing_brief_never_fails_the_check(tmp_path, monkeypatch):
    from orchestrator import brief
    monkeypatch.setattr(brief, "brief", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    c = client(tmp_path, checker=_diag_checker())
    st = wait_done(c, post(c).json()["id"])
    assert st["state"] == "done" and c.get(st["bundle"]).json()["brief"] is None
