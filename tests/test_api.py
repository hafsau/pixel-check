"""Live mode API (orchestrator/api.py): upload three frames, run the pipeline in the background, poll progress,
fetch the result bundle. Written before the implementation (TDD, Oct 5). The pipeline is a fake here — no models,
no sandbox, no key."""
import io
import json
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

SIZES = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}


def png(w, h, colour=(255, 255, 255)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(b, "PNG")
    return b.getvalue()


def frames(**override):
    f = {bp: ("f.png", png(*wh), "image/png") for bp, wh in SIZES.items()}
    f.update(override)
    return f


def fake_pipeline(run_id, frames, run_dir, emit):
    emit("perceive")
    emit("compile")
    (run_dir / "bundle" / "c").mkdir(parents=True)
    (run_dir / "bundle" / "run.json").write_text(json.dumps({"type": "static", "id": run_id}))
    (run_dir / "bundle" / "c" / "mobile.webp").write_bytes(b"RIFF....WEBP")
    return {"match": 87.5, "per_bp": {"mobile": 90.0, "tablet": 88.0, "desktop": 87.5}, "usd": 0.04}


def boom_pipeline(run_id, frames, run_dir, emit):
    emit("perceive")
    raise RuntimeError("Authorization: Bearer sk-secret-123 upstream 500")


def client(tmp_path, pipeline=fake_pipeline, **settings):
    from orchestrator.api import create_app
    s = {"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": ["http://localhost:5173"]}
    s.update(settings)
    return TestClient(create_app(pipeline=pipeline, live_dir=tmp_path, settings=s))


def wait_done(c, rid, timeout=5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = c.get(f"/api/runs/{rid}").json()
        if st["state"] in ("done", "failed"):
            return st
        time.sleep(0.05)
    raise AssertionError(f"run {rid} did not finish: {st}")


def test_health_reports_live_switch_and_runs_left(tmp_path):
    h = client(tmp_path).get("/api/health").json()
    assert h["live"] is True and h["runs_left_today"] == 10 and h["runs_left_total"] == 40
    assert client(tmp_path, enabled=False).get("/api/health").json()["live"] is False


def test_disabled_kill_switch_refuses_runs(tmp_path):
    r = client(tmp_path, enabled=False).post("/api/runs", files=frames(), data={"passcode": "letmein"})
    assert r.status_code == 503


@pytest.mark.parametrize("code", ["", "wrong", "letmein "])
def test_wrong_or_missing_passcode_is_refused(tmp_path, code):
    r = client(tmp_path).post("/api/runs", files=frames(), data={"passcode": code})
    assert r.status_code == 403 and "letmein" not in r.text


def test_frames_must_have_the_exact_sizes(tmp_path):
    r = client(tmp_path).post("/api/runs", files=frames(tablet=("t.png", png(800, 1024), "image/png")),
                              data={"passcode": "letmein"})
    assert r.status_code == 422 and "tablet" in r.text and "768" in r.text


def test_frames_must_be_png_images(tmp_path):
    b = io.BytesIO()
    Image.new("RGB", (390, 844)).save(b, "JPEG")
    r = client(tmp_path).post("/api/runs", files=frames(mobile=("m.jpg", b.getvalue(), "image/jpeg")),
                              data={"passcode": "letmein"})
    assert r.status_code == 422 and "mobile" in r.text and "PNG" in r.text
    r2 = client(tmp_path).post("/api/runs", files=frames(mobile=("m.png", b"not an image", "image/png")),
                               data={"passcode": "letmein"})
    assert r2.status_code == 422


def test_missing_frame_is_rejected(tmp_path):
    f = frames()
    f.pop("desktop")
    assert client(tmp_path).post("/api/runs", files=f, data={"passcode": "letmein"}).status_code == 422


def test_oversized_upload_is_rejected(tmp_path):
    big = ("m.png", png(390, 844) + b"\0" * (9 * 1024 * 1024), "image/png")
    r = client(tmp_path).post("/api/runs", files=frames(mobile=big), data={"passcode": "letmein"})
    assert r.status_code == 413


def test_run_goes_from_queued_to_done_with_result_and_bundle(tmp_path):
    c = client(tmp_path)
    r = c.post("/api/runs", files=frames(), data={"passcode": "letmein"})
    assert r.status_code == 202
    rid = r.json()["id"]
    st = wait_done(c, rid)
    assert st["state"] == "done" and st["result"]["match"] == 87.5
    assert [s["stage"] for s in st["stages"]][:2] == ["perceive", "compile"]
    assert st["bundle"] == f"/api/runs/{rid}/files/run.json"
    assert c.get(st["bundle"]).json()["id"] == rid
    assert c.get(f"/api/runs/{rid}/files/c/mobile.webp").status_code == 200


def test_unknown_run_is_404(tmp_path):
    c = client(tmp_path)
    assert c.get("/api/runs/does-not-exist").status_code == 404
    assert c.get("/api/runs/../../etc/passwd").status_code == 404


@pytest.mark.parametrize("path", ["../status.json", "..%2F..%2Fsecret", "c/../../frames/mobile.png", "/etc/passwd"])
def test_files_endpoint_stays_inside_the_bundle(tmp_path, path):
    c = client(tmp_path)
    rid = c.post("/api/runs", files=frames(), data={"passcode": "letmein"}).json()["id"]
    wait_done(c, rid)
    assert c.get(f"/api/runs/{rid}/files/{path}").status_code == 404


def test_failed_pipeline_reports_without_leaking_secrets(tmp_path):
    c = client(tmp_path, pipeline=boom_pipeline)
    rid = c.post("/api/runs", files=frames(), data={"passcode": "letmein"}).json()["id"]
    st = wait_done(c, rid)
    assert st["state"] == "failed" and "sk-secret" not in json.dumps(st) and "Bearer" not in json.dumps(st)
    assert st["error"]


def test_daily_and_total_caps(tmp_path):
    c = client(tmp_path, daily=2, total=3)
    ok = [c.post("/api/runs", files=frames(), data={"passcode": "letmein"}).status_code for _ in range(3)]
    assert ok == [202, 202, 429]
    assert c.get("/api/health").json()["runs_left_today"] == 0
    # the total cap survives a restart (persisted next to the runs)
    c2 = client(tmp_path, daily=10, total=3)
    assert c2.post("/api/runs", files=frames(), data={"passcode": "letmein"}).status_code == 202
    assert c2.post("/api/runs", files=frames(), data={"passcode": "letmein"}).status_code == 429


def test_refused_uploads_do_not_use_up_the_cap(tmp_path):
    c = client(tmp_path, daily=1)
    c.post("/api/runs", files=frames(), data={"passcode": "wrong"})
    c.post("/api/runs", files=frames(tablet=("t.png", png(10, 10), "image/png")), data={"passcode": "letmein"})
    assert c.post("/api/runs", files=frames(), data={"passcode": "letmein"}).status_code == 202


def test_cors_allows_the_configured_origin_only(tmp_path):
    c = client(tmp_path)
    ok = c.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = c.get("/api/health", headers={"Origin": "https://evil.example"})
    assert bad.headers.get("access-control-allow-origin") is None


def test_live_mode_is_off_unless_the_environment_switches_it_on(monkeypatch):
    import importlib
    from orchestrator import config
    monkeypatch.delenv("LIVE_ENABLED", raising=False)
    monkeypatch.delenv("LIVE_PASSCODE", raising=False)
    importlib.reload(config)
    assert config.LIVE_ENABLED is False and config.LIVE_PASSCODE == ""
    monkeypatch.setenv("LIVE_ENABLED", "1")
    importlib.reload(config)
    assert config.LIVE_ENABLED is True
    monkeypatch.delenv("LIVE_ENABLED")
    importlib.reload(config)


def test_enabled_without_a_passcode_refuses_everyone(tmp_path):
    r = client(tmp_path, passcode="").post("/api/runs", files=frames(), data={"passcode": ""})
    assert r.status_code == 403
