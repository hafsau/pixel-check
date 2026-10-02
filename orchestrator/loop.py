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
from .fluid import compile_fluid
from .scaffold import compile_scaffold
from .code import class_edits, repair, revise, structural_calls, write_initial
from .critique import auto_edits, critique, visual_checks, element_diff, feedback_text, flow_diff, visual_notes
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

    @property
    def fluid_fails(self) -> int:
        """Widths failing the in-between fluidity checks (sandbox/fluidity.py); 0 when the report predates them."""
        return len(((self.ev.report.get("fluidity") or {}).get("fails")) or []) if self.ev else 99


@dataclass
class LoopConfig:
    initial_samples: int = config.INITIAL_SAMPLES
    branches: int = config.BRANCHES
    max_rounds: int = config.MAX_ROUNDS
    stop_match: float = config.STOP_MATCH
    plateau_rounds: int = 2
    plateau_gain: float = 1.0
    scaffold: bool = True        # measured scaffold as an extra initial candidate (Hafsa, Oct 1: option 1)
    fluid: bool = True           # scaffold v2 (fluid compiler) instead of v1 (pinned) — re-plan step B
    intents: bool = True         # Nemotron responsive-intent plan → extra fluid seeds, verified (re-plan step C)
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
    """Worst breakpoint first; but a candidate within 0.5 of the parent's worst score that improves the mean by
    > 2 also wins (a −0.4 tablet wobble was blocking +11 mean from scoped mobile/desktop fixes)."""
    if b is None:
        return True
    # responsive honesty first (council, Oct 1): never trade in-between-width correctness for design-width points
    if a.fluid_fails != b.fluid_fails and a.ev and b.ev:
        return a.fluid_fails < b.fluid_fails and a.match >= b.match - 0.5
    if a.match > b.match:
        return True
    return a.match >= b.match - 0.5 and a.mean > b.mean + 2.0


def _intent_seeds(client: TFClient, spec: dict, trace) -> list[dict]:
    """One planner call → fluid seeds with the card plan, the band plan and both (identical code dropped). The plan
    is only adopted if a seed carrying it wins round 0 under _better (scores + fluidity) — logged as intent_adoption."""
    from .intent import plan_intents
    try:
        intents, raw = plan_intents(client, spec)
    except (ValueError, KeyError, TypeError) as err:
        trace({"kind": "intent_plan", "error": str(err)[:200]})
        return []
    trace({"kind": "intent_plan", "intents": intents, "raw": raw.get("raw"), "dropped": intents.get("dropped", []),
           "usd": raw.get("usd")})
    base = compile_fluid(spec)
    seeds, seen = [], {base}
    for title, it in (("scaffold+cards", {"cards": intents["cards"]}), ("scaffold+bands", {"bands": intents["bands"]}),
                      ("scaffold+plan", intents)):
        code = compile_fluid(spec, it)
        if code not in seen:
            seen.add(code)
            seeds.append({"title": title, "mode": "scaffold", "intents": it})
    return seeds


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
            if parent is None and (strategy or {}).get("mode") == "scaffold":
                # measured scaffold: deterministic geometry; v2 = fluid compiler, optionally with a verified intent plan
                code = compile_fluid(spec, strategy.get("intents")) if cfg.fluid else compile_scaffold(spec)
                from .scaffold import SEGMENTS
                from .structure import apply_semantics, semantic_tags
                try:                            # Nemotron names the regions (header / nav / section / article / footer…)
                    tags = semantic_tags(client, list(SEGMENTS))
                    code, n_tags = apply_semantics(code, tags)
                    trace({"kind": "structure_plan", "tags": tags, "applied": n_tags, "segments": len(SEGMENTS)})
                except (ValueError, KeyError) as err:
                    trace({"kind": "structure_plan", "error": str(err)[:200]})
            elif parent is None:
                code, _ = write_initial(client, spec)
            elif (strategy or {}).get("mode") == "auto":
                return auto_branch(parent, rnd, cid, title)
            elif (strategy or {}).get("mode") == "tools":
                calls, _ = structural_calls(client, parent.code, feedback, model=strategy.get("model"),
                                            temperature=strategy.get("temperature", 0.3))
                code, n_applied, skipped = jsx_edit.structural(parent.code, calls)
                trace({"kind": "tool_calls", "round": rnd, "parent": parent.id, "requested": len(calls),
                       "applied": n_applied, "calls": calls[:12], "skipped": skipped[:12]})
                if n_applied == 0:
                    return Candidate(cid, parent.id, rnd, title, None, None, "no applicable tool calls")
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

    def renders_of(ev):
        dom = {bp: json.loads(ev.renders[f"{bp}.dom.json"]) for bp in config.BREAKPOINTS if f"{bp}.dom.json" in ev.renders}
        nodes = {bp: json.loads(ev.renders[f"{bp}.nodes.json"]) for bp in config.BREAKPOINTS if f"{bp}.nodes.json" in ev.renders}
        return dom, nodes

    def auto_branch(parent: Candidate, rnd: int, cid: str, title: str) -> Candidate:
        """Deterministic measurement → margin/font fixes, up to 3 apply-evaluate iterations (no model calls).
        Rows whose step error doesn't change after a fix are 'stuck' (centring / mt-auto / space-y) and dropped."""
        code, ev, best_c = parent.code, parent.ev, None
        last: dict[tuple, int] = {}
        stuck: set[tuple] = set()
        for it in range(3):
            dom, nodes = renders_of(ev)
            _, vis_edits = visual_checks(spec, targets, ev.renders, dom, nodes)
            edits = [e for e in auto_edits(spec, dom, nodes) + vis_edits if (e["bp"], e["id"], e["why"][:3]) not in stuck]
            for e in edits:
                k = (e["bp"], e["id"], e["why"][:3])
                if k in last and e["why"] == last[k]:
                    stuck.add(k)
                last[k] = e["why"]
            edits = [e for e in edits if (e["bp"], e["id"], e["why"][:3]) not in stuck]
            if not edits:
                break
            base_code, base_ev = code, ev
            code, n_applied, skipped = jsx_edit.apply(base_code, edits)
            if n_applied == 0:
                break
            ev = evaluate(sb, code, targets, target_texts, base_image=base_ev.checkpoint)
            # per-breakpoint acceptance: scoped edits only change their own breakpoint, so a breakpoint whose
            # score dropped has its edits discarded while the others are kept (one bad tablet fix used to sink
            # good mobile + desktop fixes, because Match = worst breakpoint)
            before = {bp: v["score"] for bp, v in (base_ev.report.get("breakpoints") or {}).items()}
            after = {bp: v["score"] for bp, v in (ev.report.get("breakpoints") or {}).items()}
            worse = {bp for bp in before if after.get(bp, 0) < before[bp] - 0.3} | ({"all"} if ev.report.get("disqualified") else set())
            if worse:
                keep = [e for e in edits if e["bp"] not in worse and not (e["bp"] == "all" and worse)]
                code, n_applied, skipped = jsx_edit.apply(base_code, keep) if keep else (base_code, 0, [])
                ev = evaluate(sb, code, targets, target_texts, base_image=base_ev.checkpoint) if n_applied else base_ev
                for e in edits:
                    if e not in keep:
                        stuck.add((e["bp"], e["id"], e["why"][:3]))
            trace({"kind": "auto_edits", "round": rnd, "iter": it, "parent": parent.id, "applied": n_applied,
                   "rejected_bps": sorted(worse), "edits": [(e["id"], e["bp"], e.get("add")) for e in edits][:40],
                   "stuck": sorted(map(str, stuck))[:20], "skipped": skipped[:5]})
            if n_applied == 0:
                continue
            c = Candidate(cid, parent.id, rnd, f"{title}#{it}", code, ev)
            if best_c is None or _better(c, best_c):
                best_c = c
        return best_c or Candidate(cid, parent.id, rnd, title, None, None, "no auto edits")

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
        seeds = ([{"title": "scaffold", "mode": "scaffold"}] if cfg.scaffold else []) + [None] * cfg.initial_samples
        if cfg.scaffold and cfg.fluid and cfg.intents:
            seeds = _intent_seeds(client, spec, trace) + seeds
        for c in ex.map(lambda st: build(None, 0, st, ""), seeds):
            record(c)
            if _better(c, best):
                best = c
        history.append(best.match if best else 0.0)
        if best is not None:
            trace({"kind": "intent_adoption", "winner": best.strategy, "adopted": "+" in (best.strategy or ""),
                   "match": best.match, "fluid_fails": best.fluid_fails})
        trace({"kind": "round_end", "round": 0, "best": best.id if best else None, "match": history[-1], "spend": client.run_spend})
        for rnd in range(1, cfg.max_rounds + 1):
            if best is None or best.code is None or best.ev is None:
                stop_reason = "no valid initial candidate"
                break
            if best.match >= cfg.stop_match:
                stop_reason = f"match ≥ {cfg.stop_match}"
                break
            dom = {bp: json.loads(best.ev.renders[f"{bp}.dom.json"]) for bp in config.BREAKPOINTS if f"{bp}.dom.json" in best.ev.renders}
            diff_text = flow_diff(spec, dom)
            vis_text, _ = visual_checks(spec, targets, best.ev.renders, dom, renders_of(best.ev)[1])
            if vis_text:
                diff_text += "\n\n" + vis_text
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
                {"title": "auto", "mode": "auto", "instructions": "deterministic measurement fixes"},
                {"title": "edit-all", "mode": "edit", "temperature": 0.7,
                 "instructions": "every breakpoint's largest measured errors (positions, widths, font sizes, colours)"},
                {"title": "nemotron-tools", "mode": "tools", "temperature": 0.3,
                 "instructions": "structural fixes as tool calls"},
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
