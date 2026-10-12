"""Publish a replay bundle for the deployed site: copies it into ui/published/<id>/ (committed) and records it in
ui/published/index.json with a declared source. The production build serves ui/published/ as /runs/ and drops the
dev replays (ui/public/runs/, third-party captures — never published).

    PYTHONPATH=. .venv/bin/python tools/publish_run.py BUNDLE_DIR --id hafsausmani-home \
        --title "hafsausmani.com — home" --label "owned site" --source owned:hafsausmani.com

--source: "owned:<host>" (a site on OWNED_HOSTS, its owner agreed) or "original" (original designs).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "ui" / "published"
ALLOWED = {".json", ".webp", ".png", ".jpg", ".gif", ".avif", ".svg", ".jsx"}
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_SOURCE = re.compile(r"^(original|owned:[a-z0-9-]+(\.[a-z0-9-]+)+)$")


def _entry(run: dict, run_id: str, source: str) -> dict:
    res = run.get("result") or {}
    best = next((c for c in run.get("candidates") or [] if c.get("id") == res.get("best")), None) or {}
    fl = best.get("fluidity") or {}
    return {"id": run_id, "type": run.get("type", "static"), "title": run.get("title"), "label": run.get("label"),
            "page": run.get("page"), "match": res.get("match"), "per_bp": res.get("per_bp"), "created": run.get("created"),
            "usd": round((res.get("spend_usd") or 0) + (res.get("spend_sandbox_usd") or 0), 4),
            "fluid_pass": fl.get("pass") if fl else None, "thumb": (best.get("renders") or {}).get("mobile"),
            "source": source}


_MIME = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".gif": "image/gif", ".avif": "image/avif",
         ".svg": "image/svg+xml"}


def render_display_thumb(bundle_dir: Path) -> str:
    """Render the delivered code (display/App.jsx, the page's own images put back) at the mobile size into
    display/mobile.webp — the card's thumbnail. Local render with sandbox/render.mjs; the bundle's images are inlined
    as data URIs (this render is never scored)."""
    from PIL import Image
    code = (bundle_dir / "display" / "App.jsx").read_text()

    def inline(m):
        f = bundle_dir / "assets" / m.group(1)
        if not f.is_file() or f.suffix.lower() not in _MIME:
            return m.group(0)
        return f"data:{_MIME[f.suffix.lower()]};base64,{base64.b64encode(f.read_bytes()).decode()}"
    code = re.sub(r"/assets/([A-Za-z0-9_-]+\.[a-z0-9]+)", inline, code)
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "App.jsx").write_text(code)
        subprocess.run(["node", "render.mjs", "--in", str(Path(tmp) / "App.jsx"), "--out", str(Path(tmp) / "out")],
                       cwd=ROOT / "sandbox", check=True, capture_output=True, timeout=180)
        Image.open(Path(tmp) / "out" / "mobile.png").convert("RGB").save(bundle_dir / "display" / "mobile.webp",
                                                                         "WEBP", quality=80)
    return "display/mobile.webp"


def publish(src: Path, out: Path, *, run_id: str, title: str, label: str, source: str,
            thumb=render_display_thumb) -> Path:
    if not _ID.match(run_id):
        raise ValueError(f"id {run_id!r}: lowercase letters, digits and dashes only")
    if not _SOURCE.match(source or ""):
        raise ValueError("source must be 'original' or 'owned:<host>'")
    run = json.loads((Path(src) / "run.json").read_text())
    if "dev capture" in (run.get("title") or "").lower() or str(run.get("page") or "").endswith("-lx"):
        raise ValueError("this bundle comes from a dev capture of a third-party page — dev replays are never published")
    dest = Path(out) / run_id
    if dest.exists():
        shutil.rmtree(dest)
    for f in sorted(Path(src).rglob("*")):
        if f.is_file() and f.suffix.lower() in ALLOWED and not f.name.startswith("."):
            t = dest / f.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, t)
    run.update(id=run_id, title=title, label=label, source=source)
    (dest / "run.json").write_text(json.dumps(run, indent=1))
    entry = _entry(run, run_id, source)
    if (dest / "display" / "App.jsx").exists():         # owned site: the thumbnail shows its own images
        entry["thumb"] = thumb(dest)
    idx_p = Path(out) / "index.json"
    idx = json.loads(idx_p.read_text()) if idx_p.exists() else []
    idx = [e for e in idx if e.get("id") != run_id] + [entry]
    idx_p.write_text(json.dumps(idx, indent=1))
    return dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--source", required=True)
    a = ap.parse_args()
    print(publish(a.bundle, PUBLISHED, run_id=a.id, title=a.title, label=a.label, source=a.source))
