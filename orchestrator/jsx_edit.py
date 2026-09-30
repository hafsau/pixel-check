"""Python wrapper for jsx_tool.mjs: tag elements with ids, apply class edits deterministically."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

TOOL = Path(__file__).with_name("jsx_tool.mjs")


def _call(cmd: str, payload: dict) -> dict:
    p = subprocess.run(["node", str(TOOL), cmd], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        try:
            msg = json.loads(p.stdout)["error"]
        except Exception:
            msg = p.stderr.strip()[:400]
        raise ValueError(f"jsx_tool {cmd} failed: {msg}")
    return json.loads(p.stdout)


def tag(code: str) -> tuple[str, list[dict]]:
    r = _call("tag", {"code": code})
    return r["code"], r["elements"]


def apply(code: str, edits: list[dict]) -> tuple[str, int, list[dict]]:
    r = _call("apply", {"code": code, "edits": edits})
    return r["code"], r["applied"], r["skipped"]
