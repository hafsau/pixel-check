"""The Pixel-Check loop: initial samples → (critique → 3 forked revisions → keep best) × rounds.

Every candidate's render run is forked from its PARENT's sandbox checkpoint, so the branch tree in
the trace is the checkpoint tree in Token Factory Sandboxes.
"""
from __future__ import annotations

import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from . import jsx_edit
from .code import class_edits, repair, revise, write_initial
from .critique import critique, element_diff, feedback_text, visual_notes
from .evaluate import Evaluation, evaluate
from .sandbox import Sandbox
from .tf_client import SpendCapExceeded, TFClient


@dataclass
class Candidate:
    id: str
    parent: str | None
    round: int
    strategy: str
    code: str | None
    ev: Evaluation | None
    error: str | None = None

    @property
    def match(self) -> float:
        return self.ev.match if self.ev else 0.0

    @property
    def mean(self) -> float:
        return float(self.ev.report.get("mean", 0.0)) if self.ev else 0.0


@dataclass
class LoopConfig:
    initial_samples: int = config.INITIAL_SAMPLES
    branches: int = config.BRANCHES
    max_rounds: int = config.MAX_ROUNDS
    stop_match: float = config.STOP_MATCH
    plateau_rounds: int = 2
    plateau_gain: float = 1.0
    visual_notes: bool = False   # Gemma's diff notes hallucinated in the first runs; opt-in until an A/B shows value
    run_budget_usd: float = config.RUN_BUDGET_USD


class Trace:
    def __init__(self, run_dir: Path):
        self.dir = run_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.f = (run_dir / "trace.jsonl").open("a")

    def __call__(self, event: dict):
        self.f.write(json.dumps({"t": round(time.time(), 3), **event}) + "\n")
        self.f.flush()

    def save_candidate(self, c: Candidate):
        d = self.dir / "candidates" / c.id
        d.mkdir(parents=True, exist_ok=True)
        if c.code:
            (d / "App.jsx").write_text(c.code)
        if c.ev:
            (d / "report.json").write_text(json.dumps(c.ev.report, indent=1))
            for k, v in c.ev.renders.items():
                if k.endswith(".png") or k.endswith(".json"):
                    (d / k).write_bytes(v)


def _better(a: Candidate, b: Candidate | None) -> bool:
    return b is None or (a.match, a.mean) > (b.match, b.mean)


def run_loop(targets: dict[str, bytes], spec: dict, target_texts: dict | None, *, run_id: str | None = None,
             cfg: LoopConfig | None = None, out_root: Path = Path("out/runs")) -> dict:
    cfg = cfg or LoopConfig()
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    trace = Trace(out_root / run_id)
    client = TFClient(run_id=run_id, run_budget_usd=cfg.run_budget_usd, trace=trace)
    sb = Sandbox()
    trace({"kind": "run_start", "run": run_id, "cfg": cfg.__dict__, "models": {
        "coder": config.MODEL_CODER, "critic": config.MODEL_CRITIC, "vision": config.MODEL_VISION}})
    (trace.dir / "spec.json").write_text(json.dumps(spec, indent=1))
    t_start = time.time()

    def build(parent: Candidate | None, rnd: int, strategy: dict | None, feedback: str) -> Candidate:
        cid = uuid.uuid4().hex[:8]
        title = (strategy or {}).get("title", "initial")
        try:
            if parent is None:
                code, _ = write_initial(client, spec)
            elif (strategy or {}).get("mode") == "edit":
                edits, _ = class_edits(client, parent.code, feedback, strategy["instructions"],
                                       temperature=strategy.get("temperature", 0.4))
                code, n_applied, skipped = jsx_edit.apply(parent.code, edits)
                trace({"kind": "edits", "round": rnd, "parent": parent.id, "requested": len(edits),
                       "applied": n_applied, "skipped": skipped[:10], "edits": edits[:40]})
                if n_applied == 0:
                    return Candidate(cid, parent.id, rnd, title, None, None, "no applicable class edits")
            elif (strategy or {}).get("mode") == "rewrite":
                code, _ = write_initial(client, spec, lessons=f"{strategy['instructions']}\n\nMeasured errors of that attempt:\n{feedback}")
            else:
                instr = f"{strategy['title']} (target: {strategy.get('target_breakpoint')}): {strategy['instructions']}"
                code, _ = revise(client, spec, parent.code, instr, feedback, step=f"code r{rnd}")
            if not code:
                return Candidate(cid, parent and parent.id, rnd, title, None, None, "no code block in reply")
            try:
                code, _ = jsx_edit.tag(code)   # stable data-pc ids: the edit tool and the element diff refer to them
            except ValueError:
                pass                           # unparseable: evaluate → build error → repair, tagged after
            base = parent.ev.checkpoint if parent and parent.ev and parent.ev.checkpoint else None   # fork parent's checkpoint
            ev = evaluate(sb, code, targets, target_texts, base_image=base)
            lint_bad = [f"{v['rule']}: {v['detail']} (line {v.get('line')})" for v in ev.report.get("lint", {}).get("violations", [])]
            if ev.report.get("reason") == "build failed" or (lint_bad and "parse-error" not in str(lint_bad)):
                err = ev.report.get("build_log") or ("Lint violations (forbidden; remove or replace with plain divs):\n" + "\n".join(lint_bad))
                fixed, _ = repair(client, code, err)
                if fixed:
                    try:
                        code, _ = jsx_edit.tag(fixed)
                    except ValueError:
                        code = fixed
                    ev = evaluate(sb, code, targets, target_texts, base_image=base)
            return Candidate(cid, parent and parent.id, rnd, title, code, ev)
        except SpendCapExceeded:
            raise
        except Exception as e:  # a failed branch is not a failed run
            return Candidate(cid, parent and parent.id, rnd, title, None, None, f"{type(e).__name__}: {e}"[:300])

    def record(c: Candidate):
        trace.save_candidate(c)
        r = c.ev.report if c.ev else {}
        trace({"kind": "candidate", "id": c.id, "parent": c.parent, "round": c.round, "strategy": c.strategy,
               "match": c.match, "mean": c.mean, "worst": r.get("worst"),
               "per_bp": {bp: v["score"] for bp, v in (r.get("breakpoints") or {}).items()},
               "disqualified": r.get("disqualified"), "error": c.error,
               "checkpoint": c.ev.checkpoint if c.ev else None,
               "sandbox_cost": (c.ev.render_run.cost or 0) + ((c.ev.score_run.cost or 0) if c.ev and c.ev.score_run else 0) if c.ev else 0})

    best: Candidate | None = None
    history = []
    stop_reason = "max rounds"
    ex = ThreadPoolExecutor(max(cfg.initial_samples, cfg.branches, len(config.BREAKPOINTS)))
    try:
        for c in ex.map(lambda _: build(None, 0, None, ""), range(cfg.initial_samples)):
            record(c)
            if _better(c, best):
                best = c
        history.append(best.match if best else 0.0)
        trace({"kind": "round_end", "round": 0, "best": best.id if best else None, "match": history[-1], "spend": client.run_spend})
        for rnd in range(1, cfg.max_rounds + 1):
            if best is None or best.code is None or best.ev is None:
                stop_reason = "no valid initial candidate"
                break
            if best.match >= cfg.stop_match:
                stop_reason = f"match ≥ {cfg.stop_match}"
                break
            dom = {bp: json.loads(best.ev.renders[f"{bp}.dom.json"]) for bp in config.BREAKPOINTS if f"{bp}.dom.json" in best.ev.renders}
            diff_text = element_diff(spec, dom)
            notes = {}
            if cfg.visual_notes and not best.ev.report.get("disqualified"):
                bps = list(config.BREAKPOINTS)
                notes = dict(zip(bps, ex.map(lambda bp: visual_notes(client, bp, targets[bp], best.ev.renders[f"{bp}.png"]), bps)))
            crit = critique(client, best.code, best.ev.report, diff_text, notes)
            trace({"kind": "critique", "round": rnd, "parent": best.id, "diagnosis": crit.get("diagnosis"),
                   "strategies": crit["strategies"], "visual_notes": notes, "element_diff": diff_text})
            fb = feedback_text(best.ev.report, diff_text, notes)
            rewrite = next((st for st in crit["strategies"] if "rewrite" in (st.get("title") or "").lower()), crit["strategies"][-1])
            worst = best.ev.report.get("worst", "mobile")
            strategies = [
                {"title": "edit-worst", "mode": "edit", "temperature": 0.3,
                 "instructions": f"the worst breakpoint ({worst}): fix its measured errors"},
                {"title": "edit-all", "mode": "edit", "temperature": 0.7,
                 "instructions": "every breakpoint's largest measured errors (positions, widths, font sizes, colours)"},
                {"title": "rewrite", "mode": "rewrite", "instructions": rewrite.get("instructions", "")},
            ][: cfg.branches]
            parent = best
            for c in ex.map(lambda s: build(parent, rnd, s, fb), strategies):
                record(c)
                if _better(c, best):
                    best = c
            history.append(best.match)
            trace({"kind": "round_end", "round": rnd, "best": best.id, "match": best.match, "spend": client.run_spend})
            if best.match >= cfg.stop_match:
                stop_reason = f"match ≥ {cfg.stop_match}"
                break
            if len(history) > cfg.plateau_rounds and history[-1] - history[-1 - cfg.plateau_rounds] < cfg.plateau_gain:
                stop_reason = f"plateau: < {cfg.plateau_gain} pt gain in {cfg.plateau_rounds} rounds"
                break
    except SpendCapExceeded as e:
        stop_reason = f"budget: {e}"
    finally:
        ex.shutdown(wait=True)
    result = {"run": run_id, "stop_reason": stop_reason, "history": history,
              "best": best.id if best else None, "match": best.match if best else 0.0,
              "per_bp": {bp: v["score"] for bp, v in ((best.ev.report.get("breakpoints") or {}) if best and best.ev else {}).items()},
              "spend_usd": round(client.run_spend, 4), "wall_s": round(time.time() - t_start, 1)}
    if best and best.code:
        (trace.dir / "best.jsx").write_text(best.code)
    trace({"kind": "run_end", **result})
    (trace.dir / "result.json").write_text(json.dumps(result, indent=1))
    return result
