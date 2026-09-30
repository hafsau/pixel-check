"""Anti-cheat: every cheat fixture must fail (static lint or runtime integrity); legit ones must pass."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "sandbox"
sys.path.insert(0, str(SANDBOX))
import integrity  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
CHEATS = sorted((FIX / "cheat").glob("*.jsx"))
LEGIT = sorted((FIX / "legit").glob("*.jsx"))


def lint(path):
    p = subprocess.run(["node", "lint.mjs", str(path)], cwd=SANDBOX, capture_output=True, text=True)
    return json.loads(p.stdout)


def runtime(path, tmp):
    subprocess.run(["node", "render.mjs", "--in", str(path), "--out", str(tmp)], cwd=SANDBOX, capture_output=True, text=True)
    targets = ["Enter your info to sign in", "Or get started with a new account.", "Email or mobile number", "Continue", "Get Help"]
    return integrity.failures(json.loads((tmp / "checks.json").read_text()), tmp, targets)


@pytest.mark.parametrize("path", CHEATS, ids=lambda p: p.stem)
def test_cheat_is_caught(path, tmp_path):
    static = lint(path)
    if path.stem.startswith("runtime_"):
        assert static["ok"], f"runtime fixture should pass static lint to prove the runtime check: {static}"
        assert runtime(path, tmp_path), "runtime integrity did not catch it"
    else:
        assert not static["ok"], "static lint did not catch it"


@pytest.mark.parametrize("path", LEGIT, ids=lambda p: p.stem)
def test_legit_passes(path, tmp_path):
    assert lint(path)["ok"], lint(path)
    assert runtime(path, tmp_path) == []
