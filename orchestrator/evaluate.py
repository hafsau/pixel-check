"""Evaluate one candidate App.jsx: render run (checkpoint) → disposable scoring run.

Anti-cheat by construction: the render run's VM never contains the targets. They are uploaded
only into the scoring run, which is forked from the render checkpoint and thrown away.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .sandbox import RunResult, Sandbox

RENDER_CMD = ("mkdir -p /work/out && cd /opt/pc && "
              "node lint.mjs /work/App.jsx > /work/out/lint.json; "
              "node render.mjs --in /work/App.jsx --out /work/out > /work/out/render.json; "
              "echo done")
SCORE_CMD = "cd /opt/pc && python3 evaluate.py"


@dataclass
class Evaluation:
    match: float
    report: dict
    render_run: RunResult
    score_run: RunResult | None
    renders: dict[str, bytes] = field(default_factory=dict)   # {bp}.png, {bp}.dom.json, checks.json, …

    @property
    def checkpoint(self) -> str | None:
        return self.render_run.result_image


def evaluate(sb: Sandbox, app_jsx: str, targets: dict[str, bytes], target_texts: dict[str, list] | None = None,
             *, base_image: str | None = None, fetch_renders: bool = True) -> Evaluation:
    """targets: {"mobile": png, "tablet": png, "desktop": png}; target_texts: {bp: [str|{"text":…}]}."""
    kw = {"image": base_image} if base_image else {}
    render = sb.run(RENDER_CMD, files={"/work/App.jsx": app_jsx.encode()}, disposable=False, **kw)
    if not render.ok or not render.result_image:
        return Evaluation(0.0, {"disqualified": True, "reason": f"render run failed: {render.status} {render.stderr[:300]}"}, render, None)
    files = {f"/work/targets/{bp}.png": png for bp, png in targets.items()}
    for bp, texts in (target_texts or {}).items():
        files[f"/work/targets/{bp}.text.json"] = json.dumps(texts).encode()
    scored = sb.run(SCORE_CMD, image=render.result_image, files=files, disposable=True)
    try:
        report = json.loads(scored.stdout)
    except json.JSONDecodeError:
        report = {"disqualified": True, "reason": f"score run output unreadable ({scored.status}): {scored.stderr[:300]}"}
    renders = sb.download_dir(render.result_image, "/work/out") if fetch_renders else {}
    return Evaluation(float(report.get("match", 0.0)), report, render, scored, renders)
