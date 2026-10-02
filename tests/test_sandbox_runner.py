"""Stage 5/6 in the Token Factory sandbox (docs/INTERACTIONS.md, Gate A): the generated scenarios run in the runtime
image (render.mjs --interact, networking off); the captures come back through the checkpoint archive and are judged
locally (the design images never enter the render VM). Written before the implementation (TDD, Oct 2). Fake sandbox —
no network, no key."""
import json
from pathlib import Path

import pytest

from orchestrator.sandbox import RunResult


def result(status="SUCCESS", exit_code=0, image="img-1", stderr=""):
    return RunResult(op_id="op", status=status, exit_code=exit_code, timed_out=False, stdout="done", stderr=stderr,
                     stdout_truncated=False, cost=None, elapsed_s=3.0, wall_s=4.0, result_image=image, error=None)


class FakeSandbox:
    def __init__(self, run=None, files=None):
        self.runs, self.downloads = [], []
        self._run = run or result()
        self._files = files if files is not None else {
            "interact.json": json.dumps({"scenarios": [{"name": "mobile.base", "ok": True}]}).encode(),
            "mobile.base.png": b"\x89PNG fake", "mobile.base.dom.json": b"[]"}

    def run(self, command, **kw):
        self.runs.append((command, kw))
        return self._run

    def download_dir(self, image, path):
        self.downloads.append((image, path))
        return dict(self._files)


SCEN = [{"name": "mobile.base", "bp": "mobile", "steps": []}]


def test_runs_scenarios_in_the_sandbox_and_fetches_the_captures(tmp_path):
    from orchestrator.interact_loop import sandbox_runner
    sb = FakeSandbox()
    out = sandbox_runner("export default function App(){return null}", SCEN, tmp_path / "a0", sb=sb)
    (cmd, kw), = sb.runs
    assert "--interact /work/scenarios.json" in cmd and "--in /work/App.jsx" in cmd and "--out /work/out" in cmd
    assert kw["files"]["/work/App.jsx"].startswith(b"export default")
    assert json.loads(kw["files"]["/work/scenarios.json"]) == SCEN
    assert kw.get("networking", False) is False and kw.get("disposable", False) is False
    assert not any(p.endswith(".png") for p in kw["files"])           # no design image in the render VM
    assert sb.downloads == [("img-1", "/work/out")]
    assert json.loads((out / "interact.json").read_text())["scenarios"][0]["ok"]
    assert (out / "mobile.base.png").read_bytes() == b"\x89PNG fake"
    assert (out / "App.jsx").exists() and (out / "sandbox.json").exists()   # what ran, op id, timing


def test_failed_sandbox_run_is_an_infrastructure_error_not_a_writer_failure(tmp_path):
    from orchestrator.interact_loop import RunnerError, sandbox_runner
    sb = FakeSandbox(run=result(status="FAILED", exit_code=None, image=None, stderr="vm lost"))
    with pytest.raises(RunnerError, match="FAILED"):
        sandbox_runner("x", SCEN, tmp_path, sb=sb)
    assert sb.downloads == []


def test_missing_report_is_an_infrastructure_error(tmp_path):
    from orchestrator.interact_loop import RunnerError, sandbox_runner
    with pytest.raises(RunnerError, match="interact.json"):
        sandbox_runner("x", SCEN, tmp_path, sb=FakeSandbox(files={"mobile.base.png": b"x"}))


def test_archive_names_cannot_escape_the_output_dir(tmp_path):
    from orchestrator.interact_loop import sandbox_runner
    files = {"interact.json": b'{"scenarios": []}', "../evil.txt": b"x", "/etc/evil2": b"x", "sub/../../evil3": b"x"}
    out = sandbox_runner("x", SCEN, tmp_path / "o", sb=FakeSandbox(files=files))
    assert not (tmp_path / "evil.txt").exists() and not (tmp_path / "evil3").exists()
    assert not any("evil" in p.name for p in tmp_path.rglob("*"))
    assert (out / "interact.json").exists()


def test_build_failure_inside_the_sandbox_reaches_the_writer(tmp_path):
    """render.mjs reports a build error in interact.json and exits 0 — that one IS the writer's to fix."""
    from orchestrator.acceptance import evaluate
    from orchestrator.interact_loop import sandbox_runner
    files = {"interact.json": json.dumps({"build_failed": "Unexpected token (3:4)"}).encode()}
    out = sandbox_runner("x", SCEN, tmp_path, sb=FakeSandbox(files=files))
    v = evaluate(out, {"base": {}, "states": {"mobile": Path("x.png")}}, "menu")
    assert not v["pass"] and "does not build" in v["failures"][0]


def test_importing_the_runner_needs_no_key(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    import importlib
    import orchestrator.interact_loop as m
    importlib.reload(m)
    assert callable(m.sandbox_runner)


ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "benchmarks-dev" / "lambda-lx"


@pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_infrastructure_error_retests_the_same_code_without_misleading_the_writer(tmp_path):
    """A failed sandbox run says nothing about the code: the next attempt re-tests the same code (no new writer call,
    no cost), and the writer never sees the infrastructure message."""
    from test_interact_loop import GOOD, NO_ESCAPE, Scripted, inputs
    from orchestrator.interact_loop import RunnerError, local_runner, run_interaction
    base, states, trig, targets = inputs()
    calls = []

    def flaky(code, scenarios, out):
        if out.name == "static":                                      # the static reference render
            return local_runner(code, scenarios, out)
        calls.append(code)
        if len(calls) == 1:
            raise RunnerError("sandbox run FAILED: vm lost")
        return local_runner(code, scenarios, out)
    c = Scripted([NO_ESCAPE, GOOD])
    res = run_interaction(base, states, trig, targets, "menu", c, flaky, out=tmp_path, max_attempts=3)
    a0 = res["attempts"][0]["verdict"]
    assert a0.get("infra") and not a0["pass"] and "vm lost" in a0["failures"][0]
    assert calls[0] == calls[1] and len(c.calls) == 2                 # attempt 1 re-tested attempt 0's code
    assert any("Escape" in f for f in res["attempts"][1]["verdict"]["failures"])
    assert "vm lost" not in json.dumps(c.calls) and "Escape" in c.calls[1][-1]["content"]
    assert res["pass"] and len(res["attempts"]) == 3 and res["best_attempt"] == 2


@pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_infrastructure_errors_on_every_attempt_end_cleanly(tmp_path):
    from test_interact_loop import GOOD, Scripted, inputs
    from orchestrator.interact_loop import RunnerError, run_interaction
    base, states, trig, targets = inputs()

    from orchestrator.interact_loop import local_runner

    def down(code, scenarios, out):
        if out.name == "static":
            return local_runner(code, scenarios, out)
        raise RunnerError("sandbox run FAILED")
    c = Scripted([GOOD])
    res = run_interaction(base, states, trig, targets, "menu", c, down, out=tmp_path, max_attempts=2)
    assert not res["pass"] and len(res["attempts"]) == 2 and len(c.calls) == 1
    assert all(a["verdict"].get("infra") for a in res["attempts"])


@pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_static_reference_render_failing_twice_raises_before_any_model_call(tmp_path):
    from test_interact_loop import GOOD, Scripted, inputs
    from orchestrator.interact_loop import RunnerError, run_interaction
    base, states, trig, targets = inputs()
    seen = []

    def down(code, scenarios, out):
        seen.append(out.name)
        raise RunnerError("sandbox run FAILED")
    c = Scripted([GOOD])
    with pytest.raises(RunnerError):
        run_interaction(base, states, trig, targets, "menu", c, down, out=tmp_path, max_attempts=2)
    assert seen == ["static", "static"] and c.calls == []


def test_local_runner_timeout_is_an_infrastructure_error(tmp_path, monkeypatch):
    import subprocess
    from orchestrator import interact_loop as m

    def slow(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="node", timeout=1)
    monkeypatch.setattr(m.subprocess, "run", slow)
    with pytest.raises(m.RunnerError, match="timed out"):
        m.local_runner("x", SCEN, tmp_path)


def test_local_runner_without_report_is_an_infrastructure_error(tmp_path, monkeypatch):
    from orchestrator import interact_loop as m
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **kw: None)
    with pytest.raises(m.RunnerError, match="interact.json"):
        m.local_runner("x", SCEN, tmp_path)


def test_sandbox_cost_sums_every_run_including_the_static_reference(tmp_path):
    """Council (Oct 2): the reported '$0.0042/run' left out ~$0.02 per sandbox run."""
    from orchestrator.interact_loop import sandbox_cost
    for d, c in (("static", 0.021), ("attempt0", 0.019), ("attempt1", None)):   # None: cost not reported
        (tmp_path / d).mkdir()
        (tmp_path / d / "sandbox.json").write_text(json.dumps({"cost": c}))
    (tmp_path / "attempt2").mkdir()                                            # lint failure: no sandbox run
    assert sandbox_cost(tmp_path) == pytest.approx(0.040)
    assert sandbox_cost(tmp_path / "nothing") == 0.0
