"""Re-run measurement + merge on a page's frames using the stored vision-model reading (spec["raw_vlm"]) — no model
calls. For iterating on orchestrator/measure.py.

    PYTHONPATH=. .venv/bin/python tools/remerge.py <page> [...]     # rewrites out/specs/<page>.json
"""
import json
import sys
from pathlib import Path

from orchestrator.measure import measure
from orchestrator.perceive import merge, ocr_fallback

ROOT = Path(__file__).resolve().parents[1]
for page in sys.argv[1:]:
    sp = ROOT / "out" / "specs" / f"{page}.json"
    spec = json.loads(sp.read_text())
    out = {}
    for bp, vlm in spec["raw_vlm"].items():
        meas = measure((ROOT / "benchmarks-dev" / page / f"{bp}.png").read_bytes())
        out[bp] = merge(vlm or ocr_fallback(meas), meas)
    spec["breakpoints"] = out
    sp.write_text(json.dumps(spec, indent=1))
    print(page, {bp: (len(f["texts"]), len(f["blocks"])) for bp, f in out.items()})
