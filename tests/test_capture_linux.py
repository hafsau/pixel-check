"""tools/capture_linux.py: a re-capture must refresh the raw ground-truth text and re-filter it to visible ink (Oct 2:
re-capturing lambda's menu left a stale text.raw.json and an unfiltered text.json → state scores fell 87 → 58 on
identical pixels). Written before the fix (TDD). Fake sandbox — no network."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class R:
    status, exit_code, cost, stdout, stderr, result_image = "SUCCESS", 0, 0.01, "", "", "img"


class FakeSB:
    def __init__(self, files):
        self.files = files

    def run(self, cmd, **kw):
        return R()

    def download_dir(self, image, path):
        return self.files


def test_recapture_refreshes_raw_text_and_refilters(tmp_path, monkeypatch):
    import capture_linux as cl
    (tmp_path / "benchmarks-dev" / "pg").mkdir(parents=True)
    (tmp_path / "benchmarks-dev" / "pg" / "meta.json").write_text(json.dumps({"url": "https://example.com"}))
    out = tmp_path / "benchmarks-dev" / "pg-lx"
    out.mkdir()
    (out / "mobile.menu.text.raw.json").write_text('["stale"]')
    (out / "mobile.menu.text.json").write_text('["stale filtered"]')
    calls = []
    monkeypatch.setattr(cl, "ROOT", tmp_path)
    monkeypatch.setattr(cl, "visible_gt", lambda slug, bp, state=None: calls.append((slug, bp, state)))
    new = json.dumps([{"text": "NEW"}]).encode()
    cl.capture(FakeSB({"mobile.menu.text.json": new, "mobile.menu.png": b"png", "meta-menu.json": b"{}"}), "pg",
               state="menu", click="button")
    assert (out / "mobile.menu.text.raw.json").read_bytes() == new
    assert calls == [("pg-lx", "mobile", "menu")]


def test_base_capture_refilters_without_state(tmp_path, monkeypatch):
    import capture_linux as cl
    (tmp_path / "benchmarks-dev" / "pg").mkdir(parents=True)
    (tmp_path / "benchmarks-dev" / "pg" / "meta.json").write_text(json.dumps({"url": "https://example.com"}))
    calls = []
    monkeypatch.setattr(cl, "ROOT", tmp_path)
    monkeypatch.setattr(cl, "visible_gt", lambda slug, bp, state=None: calls.append((slug, bp, state)))
    cl.capture(FakeSB({"tablet.text.json": b"[]", "tablet.png": b"x"}), "pg")
    assert calls == [("pg-lx", "tablet", None)]
    assert (tmp_path / "benchmarks-dev" / "pg-lx" / "tablet.text.raw.json").read_bytes() == b"[]"
