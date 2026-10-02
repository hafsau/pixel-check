"""Dev-only: capture pages inside the scoring runtime image (Linux Chromium) so targets and renders share a
rasteriser (Oct 1: macOS-captured targets cost sandbox renders 2–4.5 % of pixels on text rows alone).

    PYTHONPATH=. .venv/bin/python tools/capture_linux.py <slug> [<slug> ...]

Reads each page's URL from benchmarks-dev/<slug>/meta.json, runs tools/capture/capture.mjs --oracle in the sandbox
(networking on — capture only), and writes benchmarks-dev/<slug>-lx/ (PNG, text.json, oracle.json, notext.png).
Output is git-ignored third-party material: never commit, publish or report it.
"""
import json
import sys
from pathlib import Path

from orchestrator.sandbox import Sandbox

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "tools/capture/capture.mjs").read_bytes()


def capture(sb: Sandbox, slug: str) -> Path:
    meta = json.loads((ROOT / "benchmarks-dev" / slug / "meta.json").read_text())
    hide = f' --hide "{meta["hide"]}"' if meta.get("hide") else ""
    cmd = (f'cd /opt/pc && node /opt/pc/capture.mjs {slug}-lx "{meta["url"]}" --out /work/cap --fonts /opt/pc/fonts '
           f'--oracle --wait 2000{hide}')
    r = sb.run(cmd, files={"/opt/pc/capture.mjs": SCRIPT}, timeout_s=420, networking=True)
    print(slug, r.status, r.exit_code, f"${r.cost}", r.stdout[-400:], r.stderr[-600:])
    if r.exit_code != 0 or not r.result_image:
        raise RuntimeError(f"capture failed for {slug}")
    out = ROOT / "benchmarks-dev" / f"{slug}-lx"
    out.mkdir(parents=True, exist_ok=True)
    for name, data in sb.download_dir(r.result_image, f"/work/cap/{slug}-lx").items():
        (out / Path(name).name).write_bytes(data)
    return out


if __name__ == "__main__":
    sb = Sandbox()
    for s in sys.argv[1:]:
        print(capture(sb, s))
