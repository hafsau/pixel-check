"""Per-text position error of a compiled page vs the oracle spec (where does vertical drift start?).

    PYTHONPATH=. .venv/bin/python tools/drift.py <slug-lx> <bp> [out/fluid-oracle]
"""
import json
import re
import sys
from pathlib import Path

from orchestrator.scaffold import _elem_box, Item

norm = lambda s: re.sub(r"\s+", " ", s or "").strip().lower()
slug, bp = sys.argv[1], sys.argv[2]
root = Path(sys.argv[3] if len(sys.argv) > 3 else "out/fluid-oracle") / slug
spec = json.loads(Path(f"out/specs/{slug}.oracle.json").read_text())["breakpoints"][bp]
nodes = json.loads((root / f"{bp}.nodes.json").read_text())
rendered = {}
for n in nodes:
    if n.get("t"):
        rendered.setdefault(norm(n["t"]), []).append(n["b"])
rows = []
for t in sorted(spec["texts"], key=lambda t: (t["box"][1], t["box"][0])):
    r = rendered.get(norm(t["text"]))
    if not r:
        rows.append((t["box"][1], t["text"][:40], None, None))
        continue
    b = r.pop(0)
    # rendered node box is the element box; compare tops via the ink-to-element offset of v1's calibration
    it = Item("x", "text")
    it.at[bp] = {"ink": t["box"], "fs": t["size_px"], "lines": t["lines"], "leading": None, "top_em": t["top_em"]}
    e = _elem_box(it, bp)
    rows.append((t["box"][1], t["text"][:40], b[1] - e[1], b[0] - e[0]))
for y, txt, dy, dx in rows:
    print(f"{y:5} {'MISSING' if dy is None else f'dy {dy:+5} dx {dx:+5}'}  {txt}")
