"""Durable state for Render free (orchestrator/state.py, Oct 8): the free plan wipes the disk whenever the service
sleeps or restarts, which would reset the run caps and the spend ledger — the safety limits. The few numbers that
must survive (run entries, spend so far, today's spend) live in a file or a private GitHub gist. Fake HTTP for the
gist; written before the module (TDD)."""
import json
import time

import httpx
import pytest

from orchestrator import state as S


def test_file_store_round_trip(tmp_path):
    st = S.FileStore(tmp_path / "state.json")
    assert st.load() == S.EMPTY
    st.save({"caps": [[1.0, "a"]], "spend_usd": 1.5, "spend_day": ["2026-10-08", 0.4]})
    assert st.load()["spend_usd"] == 1.5 and st.load()["caps"] == [[1.0, "a"]]
    assert not list(tmp_path.glob("*.tmp"))                       # written atomically


class Gist:
    """A fake GitHub gist API: GET/PATCH /gists/{id} with a token."""
    def __init__(self, content=None, fail=False):
        self.files = {} if content is None else {S.GIST_FILE: {"content": content}}
        self.fail, self.calls = fail, []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, str(request.url), request.headers.get("authorization")))
        if self.fail:
            return httpx.Response(503, json={"message": "down"})
        if request.method == "GET":
            return httpx.Response(200, json={"files": self.files})
        if request.method == "PATCH":
            body = json.loads(request.content)
            for name, f in body["files"].items():
                self.files[name] = {"content": f["content"]}
            return httpx.Response(200, json={"files": self.files})
        return httpx.Response(405)


def gist_store(g):
    return S.GistStore("abc123", "tok-secret", client=httpx.Client(transport=httpx.MockTransport(g.handler)))


def test_gist_store_round_trip_with_the_token():
    g = Gist()
    st = gist_store(g)
    assert st.load() == S.EMPTY
    st.save({"caps": [[2.0, "b"]], "spend_usd": 3.25, "spend_day": ["2026-10-08", 1.0]})
    assert gist_store(g).load()["spend_usd"] == 3.25
    assert all(c[1] == "https://api.github.com/gists/abc123" and c[2] == "Bearer tok-secret" for c in g.calls)


def test_gist_errors_raise_without_leaking_the_token():
    with pytest.raises(S.StateError) as e:
        gist_store(Gist(fail=True)).load()
    assert "tok-secret" not in str(e.value)


def test_corrupt_state_is_an_error_not_an_empty_state():
    """Fail closed: a garbled state must not read as 'nothing spent, no runs used'."""
    with pytest.raises(S.StateError):
        gist_store(Gist(content="{not json")).load()


def test_from_env_picks_the_gist_when_configured(tmp_path):
    assert isinstance(S.from_env({"STATE_GIST_ID": "x", "STATE_GIST_TOKEN": "y"}, tmp_path), S.GistStore)
    assert isinstance(S.from_env({}, tmp_path), S.FileStore)


# the API keeps caps and spend in the store
from fastapi.testclient import TestClient  # noqa: E402

from test_api import fake_pipeline, png, SIZES, wait_done  # noqa: E402


class MemStore:
    def __init__(self, data=None, fail_save=False, fail_load=False):
        self.data = data or dict(S.EMPTY)
        self.fail_save, self.fail_load, self.saves = fail_save, fail_load, 0

    def load(self):
        if self.fail_load:
            raise S.StateError("unreachable")
        return json.loads(json.dumps(self.data))

    def save(self, d):
        if self.fail_save:
            raise S.StateError("unreachable")
        self.saves += 1
        self.data = json.loads(json.dumps(d))


def client(tmp_path, store, **settings):
    from orchestrator.api import create_app
    s = {"enabled": True, "passcode": "letmein", "daily": 10, "total": 3, "origins": []}
    s.update(settings)
    return TestClient(create_app(pipeline=fake_pipeline, live_dir=tmp_path, settings=s, store=store))


def post(c):
    files = {bp: ("f.png", png(*wh), "image/png") for bp, wh in SIZES.items()}
    return c.post("/api/runs", files=files, data={"passcode": "letmein"})


def test_caps_survive_a_wiped_disk(tmp_path):
    store = MemStore()
    c = client(tmp_path / "boot1", store)
    assert post(c).status_code == 202 and post(c).status_code == 202
    c2 = client(tmp_path / "boot2", store)                       # a fresh, empty disk: Render woke up
    assert c2.get("/api/health").json()["runs_left_total"] == 1
    assert post(c2).status_code == 202 and post(c2).status_code == 429


def test_spend_survives_a_wiped_disk_and_counts_against_the_cap(tmp_path):
    from orchestrator.tf_client import Ledger
    store = MemStore({"caps": [], "spend_usd": 12.5, "spend_day": [time.strftime("%Y-%m-%d"), 2.0]})
    client(tmp_path / "boot", store, ledger=tmp_path / "boot" / "spend.jsonl")
    assert abs(Ledger(tmp_path / "boot" / "spend.jsonl").total() - 12.5) < 1e-9


def test_a_run_is_refused_when_the_store_cannot_record_it(tmp_path):
    c = client(tmp_path, MemStore(fail_save=True))
    r = post(c)
    assert r.status_code == 503 and "could not record" in r.json()["detail"]


def test_live_mode_stays_off_when_the_store_cannot_be_read(tmp_path):
    c = client(tmp_path, MemStore(fail_load=True))
    h = c.get("/api/health").json()
    assert h["live"] is False and post(c).status_code == 503


def test_spend_is_saved_after_each_run(tmp_path):
    store = MemStore()
    c = client(tmp_path, store)
    wait_done(c, post(c).json()["id"])
    assert store.saves >= 2          # at take() and when the run ends


def test_the_store_never_holds_a_visitors_raw_address(tmp_path):
    """A secret gist is readable by anyone with its URL: visitors are kept as a keyed hash, still counted per visitor."""
    store = MemStore()
    from orchestrator.api import create_app
    s = {"enabled": True, "passcode": "letmein", "daily": 10, "total": 40, "origins": [], "per_ip": 2,
         "trust_proxy": True}
    c = TestClient(create_app(pipeline=fake_pipeline, live_dir=tmp_path, settings=s, store=store))
    files = {bp: ("f.png", png(*wh), "image/png") for bp, wh in SIZES.items()}
    codes = [c.post("/api/runs", files=files, data={"passcode": "letmein"},
                    headers={"X-Forwarded-For": "198.51.100.23"}).status_code for _ in range(3)]
    assert codes == [202, 202, 429]
    dump = json.dumps(store.data) + "".join(p.read_text() for p in tmp_path.rglob("caps.json"))
    assert "198.51.100.23" not in dump and "letmein" not in dump
