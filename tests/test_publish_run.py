"""Publishable replays (tools/publish_run.py, Phase 4): the deployed site shows only bundles explicitly published
into ui/published/ (committed) with a declared source — an owned site or original designs — never the dev replays
of third-party captures (ui/public/runs/, git-ignored). Written before the tool (TDD, Oct 7)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import publish_run as P  # noqa: E402


def bundle(d: Path, **run_over) -> Path:
    (d / "c" / "c1").mkdir(parents=True)
    (d / "design").mkdir()
    (d / "assets").mkdir()
    run = {"type": "static", "id": "20261006-101740-bcabfc", "title": "Live run", "label": "live", "page": None,
           "created": 1791300000.0, "result": {"match": 87.0, "per_bp": {"mobile": 94.2, "tablet": 92.9, "desktop": 87.0},
                                               "best": "c1", "spend_usd": 0.0025, "spend_sandbox_usd": 0.05},
           "candidates": [{"id": "c1", "renders": {"mobile": "c/c1/mobile.webp"}, "fluidity": {"pass": True}}]}
    run.update(run_over)
    (d / "run.json").write_text(json.dumps(run))
    (d / "c" / "c1" / "mobile.webp").write_bytes(b"RIFF....WEBP")
    (d / "c" / "c1" / "App.jsx").write_text("export default function App(){return null}")
    (d / "design" / "mobile.webp").write_bytes(b"RIFF....WEBP")
    (d / "assets" / ("a" * 64 + ".webp")).write_bytes(b"RIFF....WEBP")
    (d / "notes.txt").write_text("not a bundle file")
    (d / "secret.env").write_text("NEBIUS_API_KEY=nope")
    return d


def test_publish_copies_the_bundle_and_writes_an_index_entry(tmp_path):
    src = bundle(tmp_path / "src")
    out = tmp_path / "published"
    P.publish(src, out, run_id="hafsausmani-home", title="hafsausmani.com — home", label="owned site",
              source="owned:hafsausmani.com")
    d = out / "hafsausmani-home"
    assert (d / "run.json").exists() and (d / "c" / "c1" / "App.jsx").exists() and (d / "assets" / ("a" * 64 + ".webp")).exists()
    assert not (d / "notes.txt").exists() and not (d / "secret.env").exists()
    run = json.loads((d / "run.json").read_text())
    assert run["id"] == "hafsausmani-home" and run["title"] == "hafsausmani.com — home"
    idx = json.loads((out / "index.json").read_text())
    assert idx == [{"id": "hafsausmani-home", "type": "static", "title": "hafsausmani.com — home", "label": "owned site",
                    "page": None, "match": 87.0, "per_bp": {"mobile": 94.2, "tablet": 92.9, "desktop": 87.0},
                    "created": 1791300000.0, "usd": 0.0525, "fluid_pass": True, "thumb": "c/c1/mobile.webp",
                    "source": "owned:hafsausmani.com"}]


def test_republishing_replaces_the_entry(tmp_path):
    out = tmp_path / "published"
    P.publish(bundle(tmp_path / "a"), out, run_id="x", title="One", label="l", source="original")
    P.publish(bundle(tmp_path / "b"), out, run_id="x", title="Two", label="l", source="original")
    idx = json.loads((out / "index.json").read_text())
    assert [e["title"] for e in idx] == ["Two"]


@pytest.mark.parametrize("source", ["", "dev", "owned:", "thirdparty:vercel.com", "owned:vercel.com/pricing"])
def test_a_source_must_be_declared_as_owned_or_original(tmp_path, source):
    with pytest.raises(ValueError):
        P.publish(bundle(tmp_path / "s"), tmp_path / "p", run_id="x", title="t", label="l", source=source)


def test_dev_capture_bundles_are_refused(tmp_path):
    src = bundle(tmp_path / "s", page="vercel-pricing-lx", title="Pricing (dev capture)")
    with pytest.raises(ValueError, match="dev"):
        P.publish(src, tmp_path / "p", run_id="x", title="t", label="l", source="original")


def test_ids_are_safe_folder_names(tmp_path):
    with pytest.raises(ValueError):
        P.publish(bundle(tmp_path / "s"), tmp_path / "p", run_id="../evil", title="t", label="l", source="original")
