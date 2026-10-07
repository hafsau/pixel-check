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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oracle_spec import visible_gt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
from orchestrator.api import capture_files  # noqa: E402  (capture.mjs + the modules it imports)


def capture(sb: Sandbox, slug: str, state: str | None = None, click: str | None = None, bps: str | None = None) -> Path:
    """state/click/bps: capture an interaction state frame (tools/capture/capture.mjs --state)."""
    meta = json.loads((ROOT / "benchmarks-dev" / slug / "meta.json").read_text())
    hide = f' --hide "{meta["hide"]}"' if meta.get("hide") else ""
    st = f' --state {state} --click \'{click}\'' + (f" --bps {bps}" if bps else "") if state else ""
    cmd = (f'cd /opt/pc && node /opt/pc/capture.mjs {slug}-lx "{meta["url"]}" --out /work/cap --fonts /opt/pc/fonts '
           f'--oracle --wait 2000{hide}{st}')
    for attempt in range(2):     # live pages time out now and then (lambda.ai ~1 in 4): one retry
        r = sb.run(cmd, files=capture_files(), timeout_s=420, networking=True)
        print(slug, r.status, r.exit_code, f"${r.cost}", r.stdout[-400:], r.stderr[-600:] if r.exit_code else "")
        if r.exit_code == 0 and r.result_image:
            break
    if r.exit_code != 0 or not r.result_image:
        raise RuntimeError(f"capture failed for {slug}")
    out = ROOT / "benchmarks-dev" / f"{slug}-lx"
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for name, data in sb.download_dir(r.result_image, f"/work/cap/{slug}-lx").items():
        n = Path(name).name
        (out / n).write_bytes(data)
        if n.endswith(".text.json"):
            # the fresh capture is the new raw ground truth; text.json = its visible-ink subset (oracle_spec)
            (out / n.replace(".text.json", ".text.raw.json")).write_bytes(data)
            parts = n[:-len(".text.json")].split(".", 1)
            frames.append((parts[0], parts[1] if len(parts) > 1 else None))
    for bp, st in frames:
        visible_gt(f"{slug}-lx", bp, st)
    return out


if __name__ == "__main__":
    sb = Sandbox()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = lambda k: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(k + "=")), None)
    for s in args:
        print(capture(sb, s, opt("--state"), opt("--click"), opt("--bps")))
