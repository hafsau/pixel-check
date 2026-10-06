"""Re-run measurement + merge on a page's frames using the stored vision-model reading (spec["raw_vlm"]) — no model
calls. For iterating on orchestrator/measure.py.

    PYTHONPATH=. .venv/bin/python tools/remerge.py <page> [...] [--state=menu]   # rewrites out/specs/<page>[.<state>].json
"""
import json
import sys
from pathlib import Path

from orchestrator.measure import measure
from orchestrator.perceive import cross_frame_spelling, merge, ocr_fallback

ROOT = Path(__file__).resolve().parents[1]
state = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--state=")), None)
for page in [a for a in sys.argv[1:] if not a.startswith("--")]:
    sp = ROOT / "out" / "specs" / (f"{page}.{state}.json" if state else f"{page}.json")
    spec = json.loads(sp.read_text())
    out = {}
    for bp, vlm in spec["raw_vlm"].items():
        meas = measure((ROOT / "benchmarks-dev" / page / (f"{bp}.{state}.png" if state else f"{bp}.png")).read_bytes())
        out[bp] = merge(vlm or ocr_fallback(meas), meas)
    spec["breakpoints"] = cross_frame_spelling(out)
    sp.write_text(json.dumps(spec, indent=1))
    print(page, {bp: (len(f["texts"]), len(f["blocks"])) for bp, f in out.items()})
