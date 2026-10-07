"""Deploy preflight (orchestrator/preflight.py, Phase 4): before the live server takes runs, check what it needs —
secrets present (never printed), storage writable, tesseract / node / the JSX tool / fonts / capture scripts in place,
the spend cap inside the credit. Written before the module (TDD, Oct 7)."""
import json
import subprocess
import sys
from pathlib import Path

from orchestrator import preflight as P

ROOT = Path(__file__).resolve().parents[1]


def env(tmp_path, **over):
    e = {"NEBIUS_API_KEY": "dummy-value-for-tests", "NEBIUS_AI_PROJECT": "proj-x", "LIVE_ENABLED": "1",
         "LIVE_PASSCODE": "pass-word", "LIVE_ORIGINS": "https://pixelcheck.vercel.app", "SPEND_CAP_USD": "30",
         "LIVE_DIR": str(tmp_path / "live"), "LEDGER_PATH": str(tmp_path / "spend.jsonl"),
         "VISION_CACHE_DIR": str(tmp_path / "cache")}
    e.update(over)
    return {k: v for k, v in e.items() if v is not None}


def by_name(results):
    return {r["check"]: r for r in results}


def test_a_complete_environment_passes(tmp_path):
    res = by_name(P.run(env(tmp_path), static=False))
    bad = {k: v for k, v in res.items() if not v["ok"]}
    assert not bad, bad


def test_missing_secrets_fail_without_printing_values(tmp_path):
    res = P.run(env(tmp_path, NEBIUS_API_KEY=None, LIVE_PASSCODE=None), static=False)
    r = by_name(res)
    assert not r["env NEBIUS_API_KEY"]["ok"] and not r["env LIVE_PASSCODE"]["ok"]
    dump = json.dumps(res)
    assert "proj-x" not in dump and "dummy-value" not in dump and "pass-word" not in dump


def test_live_mode_needs_origins_and_a_passcode_only_when_enabled(tmp_path):
    r = by_name(P.run(env(tmp_path, LIVE_ENABLED="0", LIVE_PASSCODE=None, LIVE_ORIGINS=None), static=False))
    assert r["env LIVE_PASSCODE"]["ok"] and r["env LIVE_ORIGINS"]["ok"]
    r = by_name(P.run(env(tmp_path, LIVE_ORIGINS=None), static=False))
    assert not r["env LIVE_ORIGINS"]["ok"]


def test_spend_cap_must_stay_inside_the_credit(tmp_path):
    r = by_name(P.run(env(tmp_path, SPEND_CAP_USD="80"), static=False))
    assert not r["spend cap"]["ok"] and "50" in r["spend cap"]["detail"]


def test_unwritable_storage_fails(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    r = by_name(P.run(env(tmp_path, LIVE_DIR=str(blocker / "live")), static=False))
    assert not r["writable LIVE_DIR"]["ok"]


def test_static_mode_skips_environment_checks(tmp_path):
    names = {x["check"] for x in P.run({}, static=True)}
    assert "tesseract" in names and "node + JSX tool" in names and "fonts" in names and "capture scripts" in names
    assert not any(n.startswith("env ") for n in names)


def test_cli_exit_code_and_json(tmp_path):
    r = subprocess.run([sys.executable, "-m", "orchestrator.preflight", "--static", "--json"], cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert all(x["ok"] for x in json.loads(r.stdout))
