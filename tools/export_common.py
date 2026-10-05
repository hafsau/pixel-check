"""Shared helpers for the replay-bundle exporters (export_run.py, export_interaction.py, export_group.py).

Bundles live in ui/public/runs/<id>/ (git-ignored; the production build strips them unless PC_INCLUDE_RUNS=1,
see ui/vite.config.ts). Screenshots are stored as lossless WebP: ~3x smaller than PNG and pixel-exact, so the UI's
difference view (mix-blend-mode: difference) still shows black for identical pixels.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "ui" / "public" / "runs"
BPS = [("mobile", 390, 844), ("tablet", 768, 1024), ("desktop", 1280, 800)]
BP_SIZE = {n: (w, h) for n, w, h in BPS}

try:                                  # Pillow is in the project venv; fall back to plain copies without it
    from PIL import Image
except ImportError:                   # pragma: no cover
    Image = None


def image(src: Path, out_dir: Path, rel: str) -> str | None:
    """Copy screenshot `src` into the bundle at `rel` (no extension) as lossless WebP. → bundle-relative path."""
    if not src.exists():
        return None
    # rel is a stem that may contain dots ("design/mobile.menu.closed"): append, never with_suffix()
    (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    if Image is None:
        shutil.copy(src, out_dir / f"{rel}.png")
        return f"{rel}.png"
    with Image.open(src) as im:
        im.convert("RGB").save(out_dir / f"{rel}.webp", "WEBP", lossless=True, method=6)
    return f"{rel}.webp"


def fresh_bundle(bundle_id: str) -> Path:
    out = RUNS / bundle_id
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    return out


def mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else time.time()


def update_index(entry: dict, reset: bool = False) -> None:
    """Add / replace one entry in ui/public/runs/index.json (keyed by id). Entries carry "type": static|interaction|group."""
    path = RUNS / "index.json"
    idx = [] if reset or not path.exists() else json.loads(path.read_text())
    idx = [r for r in idx if r.get("id") != entry["id"]] + [entry]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(idx, indent=1))


def sandbox_summary(records: list[dict]) -> dict:
    """Totals over sandbox.json records: runs, VM seconds (elapsed_s), wall seconds, cost."""
    return {"runs": len(records),
            "vm_s": round(sum(r.get("elapsed_s") or 0 for r in records), 2),
            "wall_s": round(sum(r.get("wall_s") or 0 for r in records), 2),
            "usd": round(sum(r.get("cost") or 0 for r in records), 4)}
