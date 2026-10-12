"""Render free (512 MB, 0.1 CPU), Oct 8: one heavy job at a time (others wait as "queued"), the three frames measured
one after another, and the Inter TTFs generated safely (the platform council: concurrent first use raised
'unknown file format' in 17 of 30 trials). Written before the changes (TDD)."""
import threading
import time

from fastapi.testclient import TestClient

from test_api import png, SIZES


def test_frames_are_measured_one_at_a_time(monkeypatch):
    from orchestrator import perceive as P
    live, peak = [0], [0]
    lock = threading.Lock()

    def fake_measure(png_bytes):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.05)
        with lock:
            live[0] -= 1
        return {"text_lines": []}
    monkeypatch.setattr(P, "measure", fake_measure)
    monkeypatch.setattr(P, "cached_read", lambda *a, **k: {"texts": [], "blocks": []})
    monkeypatch.setattr(P, "merge", lambda v, m: {"texts": [], "blocks": [], "size": [1, 1]})
    P.perceive(None, {"mobile": b"m", "tablet": b"t", "desktop": b"d"}, cache=None, hedge_after_s=None)
    assert peak[0] == 1


def test_one_heavy_job_runs_at_a_time_and_the_rest_wait_queued(tmp_path):
    from orchestrator.api import create_app
    running, peak, gate = [0], [0], threading.Event()
    lock = threading.Lock()

    def slow_pipeline(run_id, frames, run_dir, emit):
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        emit("perceive")
        gate.wait(5)
        with lock:
            running[0] -= 1
        return {"match": 1.0}
    s = {"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": [], "job_slots": 1}
    c = TestClient(create_app(pipeline=slow_pipeline, live_dir=tmp_path, settings=s))
    files = lambda: {bp: ("f.png", png(*wh), "image/png") for bp, wh in SIZES.items()}  # noqa: E731
    a = c.post("/api/runs", files=files(), data={"passcode": "letmein"}).json()["id"]
    b = c.post("/api/runs", files=files(), data={"passcode": "letmein"}).json()["id"]
    time.sleep(0.3)
    states = {c.get(f"/api/runs/{a}").json()["state"], c.get(f"/api/runs/{b}").json()["state"]}
    assert states == {"running", "queued"}
    gate.set()
    for rid in (a, b):
        for _ in range(100):
            if c.get(f"/api/runs/{rid}").json()["state"] == "done":
                break
            time.sleep(0.05)
        assert c.get(f"/api/runs/{rid}").json()["state"] == "done"
    assert peak[0] == 1


def test_fonts_are_generated_safely_under_concurrent_first_use(tmp_path, monkeypatch):
    from orchestrator import typography as T
    errors = []
    for trial in range(5):
        d = tmp_path / f"fonts{trial}"
        monkeypatch.setattr(T, "FONT_DIR", d)
        T._font.cache_clear()

        def use():
            try:
                T.metrics("Hello", 500)
            except Exception as e:      # noqa: BLE001
                errors.append(repr(e))
        ts = [threading.Thread(target=use) for _ in range(6)]
        [t.start() for t in ts]
        [t.join() for t in ts]
    assert not errors, errors[:3]


def test_preflight_static_builds_the_fonts(tmp_path, monkeypatch):
    from orchestrator import preflight, typography as T
    monkeypatch.setattr(T, "FONT_DIR", tmp_path / "f")
    res = {r["check"]: r for r in preflight.run({}, static=True)}
    assert res["fonts"]["ok"] and all((tmp_path / "f" / f"inter-{w}.ttf").exists() for w in (400, 500, 600, 700))
