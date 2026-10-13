"""Platform council fixes (Oct 8): visitor IP from the entry Render appends, sandbox 429 retried at spawn, hard VM
timeouts, sandbox cost in each run's budget, repairs weigh 3 runs, request-size limit, LIVE_ORIGINS cleaned, errors
not over-redacted, cost kept when the price list fails. Written before the fixes (TDD)."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from test_api import SIZES, fake_pipeline, png


def app_client(tmp_path, **settings):
    from orchestrator.api import create_app
    s = {"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": [], "per_ip": 3,
         "trust_proxy": True}
    s.update(settings)
    return TestClient(create_app(pipeline=fake_pipeline, live_dir=tmp_path, settings=s))


def frames():
    return {bp: ("f.png", png(*wh), "image/png") for bp, wh in SIZES.items()}


def test_visitor_is_the_address_render_appends_not_a_spoofed_first_entry(tmp_path):
    c = app_client(tmp_path)
    codes = [c.post("/api/runs", files=frames(), data={"passcode": "letmein"},
                    headers={"X-Forwarded-For": f"10.9.9.{i}, 203.0.113.7"}).status_code for i in range(5)]
    assert codes == [202, 202, 202, 429, 429]


def test_a_repair_weighs_three_runs(tmp_path):
    from orchestrator.api import create_app
    from test_api_check import fake_checker, fake_repairer
    from test_api_url import resolver
    s = {"enabled": True, "passcode": "letmein", "daily": 4, "total": 40, "origins": []}
    c = TestClient(create_app(checker=fake_checker, repairer=fake_repairer, resolver=resolver, live_dir=tmp_path, settings=s))
    data = {"code": "export default function App(){return null}", "owns": "true", "passcode": "letmein", "repair": "true"}
    assert c.post("/api/checks", files=frames(), data=data).status_code == 202
    assert c.get("/api/health").json()["runs_left_today"] == 1
    assert c.post("/api/checks", files=frames(), data=data).status_code == 429      # 3 needed, 1 left


def test_oversized_requests_are_refused_before_parsing(tmp_path):
    c = app_client(tmp_path)
    r = c.post("/api/runs", content=b"x" * 10, headers={"content-length": str(40 * 1024 * 1024),
                                                        "content-type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413


def test_live_origins_are_trimmed_and_lose_trailing_slashes(monkeypatch):
    import importlib
    from orchestrator import config
    monkeypatch.setenv("LIVE_ORIGINS", " https://a.vercel.app/ , https://b.app ,")
    importlib.reload(config)
    try:
        assert config.LIVE_ORIGINS == ["https://a.vercel.app", "https://b.app"]
    finally:
        monkeypatch.delenv("LIVE_ORIGINS")
        importlib.reload(config)


def test_scrub_keeps_token_factory_but_hides_secrets():
    from orchestrator.api import _scrub
    assert _scrub("Nebius Token Factory said 500") == "Nebius Token Factory said 500"
    out = _scrub("Authorization: Bearer abc.def token=xyz123 sk-live-999")
    assert "abc.def" not in out and "xyz123" not in out and "sk-live-999" not in out


# sandbox: spawn retries on 429 (no VM was created), hard timeouts, cost charged to a run's meter
class Meter:
    def __init__(self, budget=1.0):
        self.run_spend, self.run_budget = 0.0, budget


def fake_sb(responses, tmp_path, monkeypatch, meter=None):
    from orchestrator import config, sandbox
    monkeypatch.setattr(config, "LEDGER_PATH", tmp_path / "spend.jsonl")
    monkeypatch.setattr(config, "SANDBOX_POLL_S", 0)
    monkeypatch.setattr(sandbox.time, "sleep", lambda s: None)
    calls = []

    def handler(req: httpx.Request):
        calls.append((req.method, req.url.path))
        if req.method == "POST" and req.url.path.endswith("/instances"):
            return responses.pop(0)
        if req.url.path.startswith("/sandboxes/v1/operations") or "/operations/" in req.url.path:
            return httpx.Response(200, json={"status": "SUCCESS", "result_image_uuid": "img",
                                             "metadata": {"result": {"state": {"exit_code": 0},
                                                                     "resources": {"cost": 0.02, "elapsed_time": 2}}}})
        return httpx.Response(200, json={"uuid": "f"})
    monkeypatch.setattr(config, "api_key", lambda: "k")
    monkeypatch.setattr(config, "project_id", lambda: "p")
    sb = sandbox.Sandbox(client=httpx.Client(transport=httpx.MockTransport(handler)), meter=meter)
    return sb, calls


def test_spawn_is_retried_on_429(tmp_path, monkeypatch):
    sb, calls = fake_sb([httpx.Response(429, headers={"Retry-After": "1"}), httpx.Response(429),
                         httpx.Response(200, json={"uuid": "op1"})], tmp_path, monkeypatch)
    r = sb.run("echo hi")
    assert r.exit_code == 0 and sum(1 for m, p in calls if m == "POST" and p.endswith("/instances")) == 3


def test_spawn_is_not_retried_on_other_errors(tmp_path, monkeypatch):
    sb, calls = fake_sb([httpx.Response(500)], tmp_path, monkeypatch)
    with pytest.raises(httpx.HTTPStatusError):
        sb.run("echo hi")


def test_sandbox_cost_is_charged_to_the_runs_meter_and_its_budget_enforced(tmp_path, monkeypatch):
    from orchestrator.tf_client import SpendCapExceeded
    meter = Meter(budget=0.03)
    sb, _ = fake_sb([httpx.Response(200, json={"uuid": "a"}), httpx.Response(200, json={"uuid": "b"})], tmp_path,
                    monkeypatch, meter=meter)
    sb.run("echo 1")
    sb.run("echo 2")
    assert abs(meter.run_spend - 0.04) < 1e-9
    with pytest.raises(SpendCapExceeded):
        sb.run("echo 3")


def test_vm_commands_have_hard_timeouts():
    from orchestrator.evaluate import RENDER_CMD, SCORE_CMD
    from orchestrator.check import SCORE_CHECK
    import inspect
    from orchestrator import api, check
    assert RENDER_CMD.count("timeout ") >= 2 and "timeout " in SCORE_CMD and "timeout " in SCORE_CHECK
    assert "timeout 150 node /opt/pc/check_page.mjs" in inspect.getsource(check.check_url)
    assert "timeout 150 node /opt/pc/capture.mjs" in inspect.getsource(api.default_capture)


def test_a_failing_price_list_still_records_the_cost(tmp_path, monkeypatch):
    from orchestrator import config, tf_client
    monkeypatch.setattr(config, "LEDGER_PATH", tmp_path / "spend.jsonl")

    def boom():
        raise httpx.ConnectError("catalogue down")
    monkeypatch.setattr(tf_client, "prices", boom)
    assert tf_client._price("nvidia/x") == config.FALLBACK_PRICE


def test_owned_sites_are_captured_with_their_own_fonts():
    import inspect
    from orchestrator import api
    src = inspect.getsource(api.default_capture)
    assert '" --real --assets --own-fonts" if owned' in src
