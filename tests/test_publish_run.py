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


# the card's thumbnail for an owned site shows the delivered page with its own images (display/App.jsx), not the
# scored render where every image is a grey block (Oct 12, Hafsa: "a grey box where my headshot is")
def test_owned_site_thumbnail_is_the_display_render(tmp_path):
    src = bundle(tmp_path / "src")
    (src / "display").mkdir()
    (src / "display" / "App.jsx").write_text("export default function App(){return null}")
    calls = []

    def fake_thumb(bundle_dir):
        calls.append(bundle_dir)
        (bundle_dir / "display" / "mobile.webp").write_bytes(b"RIFF....WEBP")
        return "display/mobile.webp"
    out = tmp_path / "published"
    P.publish(src, out, run_id="hafsausmani-home", title="t", label="l", source="owned:hafsausmani.com",
              thumb=fake_thumb)
    entry = json.loads((out / "index.json").read_text())[0]
    assert entry["thumb"] == "display/mobile.webp" and calls == [out / "hafsausmani-home"]


def test_without_display_code_the_scored_render_stays_the_thumbnail(tmp_path):
    src = bundle(tmp_path / "src")
    out = tmp_path / "published"
    P.publish(src, out, run_id="x-site", title="t", label="l", source="original",
              thumb=lambda d: pytest.fail("no display code, nothing to render"))
    assert json.loads((out / "index.json").read_text())[0]["thumb"] == "c/c1/mobile.webp"


def test_display_thumbnail_renders_the_page_with_its_images(tmp_path):
    src = bundle(tmp_path / "src")
    (src / "display").mkdir()
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (220, 30, 30)).save(buf, "WEBP")
    (src / "assets" / ("b" * 64 + ".webp")).write_bytes(buf.getvalue())
    (src / "display" / "App.jsx").write_text(
        'export default function App(){return <main className="p-0"><img src="/assets/' + "b" * 64 +
        '.webp" alt="" className="block w-[390px] h-[400px]" /></main>}')
    out = tmp_path / "published"
    P.publish(src, out, run_id="red-site", title="t", label="l", source="original")
    entry = json.loads((out / "index.json").read_text())[0]
    assert entry["thumb"] == "display/mobile.webp"
    im = Image.open(out / "red-site" / "display" / "mobile.webp").convert("RGB")
    r, g, b = im.getpixel((100, 100))
    assert r > 180 and g < 80 and b < 80          # the image is painted, not a grey block


# ---- check / audit bundles (Oct 13): a check of a build the owner published (check.json + build captures)

def check_bundle(d: Path, url="https://heatshot-ai.lovable.app/", mode="audit") -> Path:
    (d / "bundle" / "build").mkdir(parents=True)
    rep = {"mode": mode, "fluidity": {"pass": True, "fails": []},
           "warnings": ['1024 px: the "Edit with Lovable" badge covers "Your headshot will appear here"'],
           "vanished": {"mobile": ["Dashboard", "Generator"], "tablet": []}}
    (d / "bundle" / "check.json").write_text(json.dumps({
        "type": "check", "id": "20261013-141035-e238b7", "source": {"url": url}, "report": rep, "design": {},
        "build": {bp: f"build/{bp}.webp" for bp in ("mobile", "tablet", "desktop")}, "design_texts": {},
        "usd": 0.031, "repair": None}))
    for bp in ("mobile", "tablet", "desktop"):
        (d / "bundle" / "build" / f"{bp}.webp").write_bytes(b"RIFF....WEBP")
    (d / "status.json").write_text(json.dumps({"created": 1791925835.0, "state": "done"}))
    return d / "bundle"


def test_an_audit_bundle_is_published_with_a_check_entry(tmp_path):
    out = tmp_path / "published"
    P.publish(check_bundle(tmp_path / "r"), out, run_id="heatshot-audit", title="HeatShot AI — audit",
              label="owned app · audit", source="owned:heatshot-ai.lovable.app")
    d = out / "heatshot-audit"
    assert (d / "check.json").exists() and (d / "build" / "mobile.webp").exists() and not (d / "run.json").exists()
    chk = json.loads((d / "check.json").read_text())
    assert chk["id"] == "heatshot-audit" and chk["title"] == "HeatShot AI — audit"
    assert json.loads((out / "index.json").read_text()) == [{
        "id": "heatshot-audit", "type": "check", "mode": "audit", "title": "HeatShot AI — audit",
        "label": "owned app · audit", "url": "https://heatshot-ai.lovable.app/", "match": None, "per_bp": {},
        "created": 1791925835.0, "usd": 0.031, "fluid_pass": True, "warnings": 1, "vanished": 2,
        "thumb": "build/mobile.webp", "source": "owned:heatshot-ai.lovable.app"}]


@pytest.mark.parametrize("source", ["original", "owned:hafsausmani.com", "owned:lovable.app"])
def test_a_check_is_published_only_as_the_checked_hosts_own(tmp_path, source):
    """The declared owner must be the host that was checked: a third-party page cannot be relabelled as owned."""
    with pytest.raises(ValueError, match="host"):
        P.publish(check_bundle(tmp_path / "r"), tmp_path / "out", run_id="x", title="t", label="l", source=source)


def test_a_check_url_is_published_without_query_or_fragment(tmp_path):
    out = tmp_path / "published"
    P.publish(check_bundle(tmp_path / "r", url="https://heatshot-ai.lovable.app/app?x=1#y"), out, run_id="x",
              title="t", label="l", source="owned:heatshot-ai.lovable.app")
    assert json.loads((out / "index.json").read_text())[0]["url"] == "https://heatshot-ai.lovable.app/app"
    assert json.loads((out / "x" / "check.json").read_text())["source"] == {"url": "https://heatshot-ai.lovable.app/app"}
