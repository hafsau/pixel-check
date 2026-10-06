"""Replay-bundle exporter (tools/export_run.py): a live run exports into its own folder, not ui/public/runs/, and
does not touch the replay index. Written before the change (TDD, Oct 5)."""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def fake_run(d: Path) -> Path:
    run = d / "trace"
    (run / "candidates" / "c1").mkdir(parents=True)
    ev = [{"kind": "run_start", "t": 1.0, "cfg": {"fluid": True}, "models": {"coder": "x"}},
          {"kind": "candidate", "id": "c1", "round": 0, "t": 2.0, "strategy": "scaffold#1", "match": 80.0,
           "per_bp": {"mobile": 80.0, "tablet": 81.0, "desktop": 82.0}},
          {"kind": "round_end", "round": 0, "best": "c1", "match": 80.0, "spend": 0.01}]
    (run / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in ev))
    (run / "result.json").write_text(json.dumps({"match": 80.0, "per_bp": {"mobile": 80.0}, "best": "c1",
                                                 "spend_usd": 0.01, "stop_reason": "done", "history": [80.0]}))
    for bp, wh in {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}.items():
        Image.new("RGB", wh, "white").save(run / "candidates" / "c1" / f"{bp}.png")
    (run / "candidates" / "c1" / "App.jsx").write_text("export default function App(){return null}")
    frames = d / "frames"
    frames.mkdir()
    for bp, wh in {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}.items():
        Image.new("RGB", wh, "white").save(frames / f"{bp}.png")
    return run


def test_export_into_a_given_folder_leaves_the_replay_index_alone(tmp_path, monkeypatch):
    import export_common
    import export_run
    monkeypatch.setattr(export_common, "RUNS", tmp_path / "replays")
    run = fake_run(tmp_path)
    out = export_run.export(run, tmp_path / "frames", title="Live run", index=False, out_root=tmp_path / "bundle")
    assert out == tmp_path / "bundle"
    r = json.loads((out / "run.json").read_text())
    assert r["result"]["match"] == 80.0 and r["candidates"][0]["renders"]["mobile"].startswith("c/c1/mobile")
    assert (out / r["candidates"][0]["renders"]["mobile"]).exists() and (out / "c" / "c1" / "App.jsx").exists()
    assert not (tmp_path / "replays").exists()                                 # nothing written to the replay set


def test_export_adds_the_delivered_code_its_images_and_the_real_screenshots(tmp_path, monkeypatch):
    """Owned sites: display.jsx (grey blocks → the page's own images) + the assets it uses + real screenshots."""
    import export_common
    import export_run
    monkeypatch.setattr(export_common, "RUNS", tmp_path / "replays")
    run = fake_run(tmp_path)
    h = "a" * 64
    (run / "display.jsx").write_text(f'export default function App(){{return <img data-pc="1" src="/assets/{h}.png" alt="" />}}')
    owned = tmp_path / "owned"
    (owned / "assets").mkdir(parents=True)
    (owned / "assets" / f"{h}.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    (owned / "assets" / ("b" * 64 + ".png")).write_bytes(b"\x89PNG\r\n\x1a\n" + b"1" * 20)   # not used → not copied
    (owned / "real").mkdir()
    Image.new("RGB", (390, 844), "red").save(owned / "real" / "mobile.png")
    out = export_run.export(run, tmp_path / "frames", index=False, out_root=tmp_path / "bundle", owned=owned)
    r = json.loads((out / "run.json").read_text())
    assert r["display"] == {"code": "display/App.jsx", "assets": [f"assets/{h}.png"], "images": 1, "candidate": "c1"}
    assert (out / "display" / "App.jsx").read_text().startswith("export default")
    assert (out / "assets" / f"{h}.png").exists() and not (out / "assets" / ("b" * 64 + ".png")).exists()
    assert r["real"] == {"mobile": "real/mobile.webp"} and (out / "real" / "mobile.webp").exists()


def test_export_without_owned_material_has_no_display_or_real(tmp_path, monkeypatch):
    import export_common
    import export_run
    monkeypatch.setattr(export_common, "RUNS", tmp_path / "replays")
    run = fake_run(tmp_path)
    out = export_run.export(run, tmp_path / "frames", index=False, out_root=tmp_path / "bundle")
    r = json.loads((out / "run.json").read_text())
    assert r.get("display") is None and r.get("real") is None
