"""Phase 2 speed: the vision read is the slow stage (median 25 s, tail 293 s on Token Factory). A slow read gets one
backup request (first valid answer wins); a frame already read is served from a cache keyed by the frame's bytes,
the model and the prompt."""
import json
import threading
import time

import pytest

from orchestrator import perceive as P

GOOD = json.dumps({"background": "#ffffff", "texts": [{"text": "Hi", "role": "body", "box": [0, 0, 10, 10]}],
                   "blocks": [], "layout": "one line"})


class Reply:
    def __init__(self, content):
        self.content = content


class FakeClient:
    """chat() sleeps per call in order (delays[i]) and returns contents[i] (default GOOD)."""
    def __init__(self, delays, contents=None):
        self.delays, self.contents = list(delays), list(contents or [])
        self.calls, self.lock = 0, threading.Lock()

    def chat(self, model, msg, *, step, max_tokens, temperature):
        with self.lock:
            i = self.calls
            self.calls += 1
        time.sleep(self.delays[i] if i < len(self.delays) else 0)
        return Reply(self.contents[i] if i < len(self.contents) else GOOD)


def test_fast_read_sends_no_backup():
    c = FakeClient([0.01])
    out = P.hedged_read(c, "mobile", b"png", hedge_after_s=0.5)
    assert out["texts"][0]["text"] == "Hi" and out["size"] == [390, 844]
    time.sleep(0.05)
    assert c.calls == 1


def test_slow_read_gets_backup_and_first_answer_wins():
    c = FakeClient([2.0, 0.05])
    t0 = time.time()
    out = P.hedged_read(c, "desktop", b"png", hedge_after_s=0.1)
    dt = time.time() - t0
    assert out["size"] == [1280, 800]
    assert c.calls == 2
    assert dt < 1.0          # did not wait for the slow first request


def test_backup_failing_still_waits_for_first():
    # backup returns garbage twice (read_frame retries once), the slow original succeeds
    c = FakeClient([0.4, 0.0, 0.0], contents=[GOOD, "nope", "still nope"])
    out = P.hedged_read(c, "tablet", b"png", hedge_after_s=0.05)
    assert out["size"] == [768, 1024]


def test_both_failing_raises_value_error():
    c = FakeClient([0.1, 0.0, 0.0, 0.0], contents=["x", "x", "x", "x"])
    with pytest.raises(ValueError):
        P.hedged_read(c, "mobile", b"png", hedge_after_s=0.02)


def test_hedging_off_is_a_plain_read():
    c = FakeClient([0.2])
    P.hedged_read(c, "mobile", b"png", hedge_after_s=None)
    assert c.calls == 1


def test_cache_hit_skips_the_model(tmp_path):
    cache = P.VisionCache(tmp_path)
    c = FakeClient([0.0])
    a = P.cached_read(c, "mobile", b"frame-bytes", cache=cache, hedge_after_s=None)
    b = P.cached_read(c, "mobile", b"frame-bytes", cache=cache, hedge_after_s=None)
    assert a == b and c.calls == 1


def test_cache_key_covers_bytes_model_and_breakpoint(tmp_path):
    cache = P.VisionCache(tmp_path)
    k = cache.key("mobile", b"a", "m1")
    assert k != cache.key("mobile", b"b", "m1")
    assert k != cache.key("mobile", b"a", "m2")
    assert k != cache.key("tablet", b"a", "m1")
    assert len(k) == 64 and all(ch in "0123456789abcdef" for ch in k)


def test_cache_key_changes_with_the_prompt(tmp_path, monkeypatch):
    cache = P.VisionCache(tmp_path)
    k = cache.key("mobile", b"a", "m1")
    monkeypatch.setattr(P, "FRAME_PROMPT", P.FRAME_PROMPT + " extra rule")
    assert cache.key("mobile", b"a", "m1") != k


def test_failed_read_is_not_cached(tmp_path):
    cache = P.VisionCache(tmp_path)
    c = FakeClient([0, 0, 0, 0], contents=["bad", "bad", GOOD])
    with pytest.raises(ValueError):
        P.cached_read(c, "mobile", b"f", cache=cache, hedge_after_s=None)
    assert list(tmp_path.iterdir()) == []
    assert P.cached_read(c, "mobile", b"f", cache=cache, hedge_after_s=None)["texts"]


def test_corrupt_cache_entry_is_ignored(tmp_path):
    cache = P.VisionCache(tmp_path)
    (tmp_path / f"{cache.key('mobile', b'f', P.config.MODEL_VISION)}.json").write_text("{not json")
    c = FakeClient([0])
    assert P.cached_read(c, "mobile", b"f", cache=cache, hedge_after_s=None)["texts"]
    assert c.calls == 1


def test_cache_none_reads_every_time():
    c = FakeClient([0, 0])
    P.cached_read(c, "mobile", b"f", cache=None, hedge_after_s=None)
    P.cached_read(c, "mobile", b"f", cache=None, hedge_after_s=None)
    assert c.calls == 2


def test_perceive_uses_cache_and_hedge(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "measure", lambda png: {"text_lines": []})
    monkeypatch.setattr(P, "merge", lambda v, m: {"texts": v["texts"]})
    cache = P.VisionCache(tmp_path)
    c = FakeClient([0, 0, 0])
    frames = {"mobile": b"m", "tablet": b"t", "desktop": b"d"}
    s1 = P.perceive(c, frames, cache=cache, hedge_after_s=None)
    s2 = P.perceive(c, frames, cache=cache, hedge_after_s=None)
    assert c.calls == 3 and s1["breakpoints"] == s2["breakpoints"]
