"""Durable state for hosts that wipe their disk (Render free sleeps after 15 idle minutes and may restart anytime).

The safety limits depend on a few numbers that must survive: the run entries behind the caps (10/day, 40 total,
3 per visitor), the spend so far and today's spend. They live in a small JSON document — a local file, or a private
GitHub gist (STATE_GIST_ID + STATE_GIST_TOKEN, a token that can only edit gists). Errors raise StateError (never with
the token in the message) so the API can fail closed: no readable state → no live runs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

EMPTY = {"caps": [], "spend_usd": 0.0, "spend_day": [None, 0.0]}
GIST_FILE = "pixelcheck-state.json"


class StateError(RuntimeError):
    pass


def _parse(text: str) -> dict:
    try:
        d = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        raise StateError("the stored state is not valid JSON") from None
    if not isinstance(d, dict) or not isinstance(d.get("caps", []), list):
        raise StateError("the stored state has an unexpected shape")
    return {"caps": d.get("caps") or [], "spend_usd": float(d.get("spend_usd") or 0.0),
            "spend_day": list(d.get("spend_day") or [None, 0.0])}


class FileStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return json.loads(json.dumps(EMPTY))
        return _parse(self.path.read_text())

    def save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        os.replace(tmp, self.path)


class GistStore:
    def __init__(self, gist_id: str, token: str, client=None):
        import httpx
        self.url = f"https://api.github.com/gists/{gist_id}"
        self._h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        self._c = client or httpx.Client(timeout=15)

    def _call(self, method: str, **kw):
        import httpx
        try:
            r = self._c.request(method, self.url, headers=self._h, **kw)
        except httpx.HTTPError as e:
            raise StateError(f"the state gist is unreachable ({type(e).__name__})") from None
        if r.status_code >= 300:
            raise StateError(f"the state gist answered {r.status_code}")
        return r.json()

    def load(self) -> dict:
        f = (self._call("GET").get("files") or {}).get(GIST_FILE)
        if not f:
            return json.loads(json.dumps(EMPTY))
        return _parse(f.get("content"))

    def save(self, state: dict) -> None:
        self._call("PATCH", json={"files": {GIST_FILE: {"content": json.dumps(state)}}})


def from_env(env: dict, default_dir) -> FileStore | GistStore:
    gid, tok = (env.get("STATE_GIST_ID") or "").strip(), (env.get("STATE_GIST_TOKEN") or "").strip()
    if gid and tok:
        return GistStore(gid, tok)
    return FileStore(Path(default_dir) / "state.json")
