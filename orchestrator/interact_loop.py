"""Stage 6 (docs/INTERACTIONS.md): the interaction agent loop — Nemotron writes, the sandbox tests, Nemotron fixes.

run_interaction compiles the static page (trigger marked, compiler's own menu toggle off) and the panel the state
frames reveal, derives the measured facts, then up to max_attempts times: write (or revise with the failures) →
assemble → lint → run the generated scenarios (runner: local node or the Token Factory sandbox) → evaluate. The
best attempt is kept; a passing attempt stops the loop. Every attempt is recorded for the trace / web app.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import config
from .acceptance import build_scenarios, evaluate
from .fluid import compile_fluid
from .panel import compile_panel
from .writer import WriterFormatError, assemble, write_interaction

ROOT = Path(__file__).resolve().parents[1]
BPS = ("mobile", "tablet", "desktop")


def build_facts(page: str, panel: dict, name: str, states: dict, triggers: dict | None = None) -> dict:
    m = re.search(r'<\w+[^<>]*data-trigger="%s"[^<>]*?/?>' % re.escape(name), page)
    comp = re.match(r"\s*function (\w+)\(", panel["jsx"] or "")
    trig_open = {}
    for bp, ch in (panel.get("trigger_changes") or {}).items():
        boxes = [{"box": b["box"], "fill": b.get("fill")} for b in ch["appeared"]["blocks"]]
        if boxes and triggers and triggers.get(bp):
            tx, ty = triggers[bp][0], triggers[bp][1]
            boxes = [{"box": [b["box"][0] - tx, b["box"][1] - ty, b["box"][2], b["box"][3]], "fill": b["fill"]} for b in boxes]
        if boxes:
            trig_open[bp] = boxes
    for bp, lk in (panel.get("trigger_look") or {}).items():   # read from the images: wins over perception
        if lk:
            trig_open[bp] = [lk]
    return {"trigger_tag": m.group(0) if m else None,
            "panel_component": (next(iter(set(panel["components"].values()))) if panel.get("components")
                                and len(set(panel["components"].values())) == 1 else panel.get("components"))
                               or (comp.group(1) if comp else None),
            "kind": {bp: d["kind"] for bp, d in panel["diff"].items() if d["kind"] != "none"},
            "panel": panel["panel"], "background": {bp: states[bp].get("background") for bp in states},
            "backdrop": panel.get("backdrop") or {}, "trigger_open": trig_open,
            "hidden_at": [bp for bp in BPS if bp not in states],
            "trigger_open_component": panel.get("trigger_component")}


def local_runner(code: str, scenarios: list, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    (out / "App.jsx").write_text(code)
    (out / "scenarios.json").write_text(json.dumps(scenarios))
    subprocess.run(["node", "render.mjs", "--interact", str((out / "scenarios.json").resolve()), "--in",
                    str((out / "App.jsx").resolve()), "--out", str(out.resolve())], cwd=ROOT / "sandbox",
                   capture_output=True, timeout=240)
    return out


class RunnerError(RuntimeError):
    """The test run itself failed (sandbox lost, no report) — says nothing about the code; never shown to the writer."""


INTERACT_CMD = ("mkdir -p /work/out && cd /opt/pc && "
                "node render.mjs --interact /work/scenarios.json --in /work/App.jsx --out /work/out "
                "> /work/out/interact.log 2>&1; echo done")
_SANDBOX = None


def sandbox_runner(code: str, scenarios: list, out: Path, sb=None) -> Path:
    """The generated scenarios run in the Token Factory sandbox (runtime image, networking off, non-disposable so the
    captures can be fetched from the checkpoint archive — stdout is capped at 64 KiB). The design images never enter
    this VM; the verdict is computed from the fetched captures (acceptance.evaluate)."""
    global _SANDBOX
    if sb is None:
        if _SANDBOX is None:
            from .sandbox import Sandbox
            _SANDBOX = Sandbox()
        sb = _SANDBOX
    out.mkdir(parents=True, exist_ok=True)
    (out / "App.jsx").write_text(code)
    (out / "scenarios.json").write_text(json.dumps(scenarios))
    r = sb.run(INTERACT_CMD, files={"/work/App.jsx": code.encode(), "/work/scenarios.json": json.dumps(scenarios).encode()},
               disposable=False, networking=False, timeout_s=config.INTERACT_TIMEOUT_S)
    (out / "sandbox.json").write_text(json.dumps({"op_id": r.op_id, "status": r.status, "exit_code": r.exit_code,
                                                  "image": r.result_image, "elapsed_s": r.elapsed_s, "wall_s": r.wall_s,
                                                  "cost": r.cost}, indent=1))
    if not r.ok or not r.result_image:
        raise RunnerError(f"sandbox run {r.status} (exit {r.exit_code}): {(r.stderr or r.error or '')[:200]}")
    files = sb.download_dir(r.result_image, "/work/out")
    root = out.resolve()
    for name, data in files.items():
        dest = (root / name).resolve()
        if root not in dest.parents:      # archive names never escape the attempt's folder
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    if "interact.json" not in files:
        raise RunnerError("the sandbox run produced no interact.json")
    return out


def _lint(code: str, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    p = out / "lint_App.jsx"
    p.write_text(code)
    r = subprocess.run(["node", "lint.mjs", str(p.resolve())], cwd=ROOT / "sandbox", capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "violations": [{"rule": "lint-crash", "detail": r.stderr[:200]}]}


def run_interaction(base_spec: dict, states: dict, triggers: dict, targets: dict, name: str, client, runner,
                    out: Path, max_attempts: int = 3) -> dict:
    page = compile_fluid(base_spec, triggers={name: triggers}, auto_menu=False)
    images = {bp: (targets["base"][bp], targets["states"][bp]) for bp in states if bp in targets.get("base", {})}
    panel = compile_panel(base_spec, states, name=f"{name.capitalize()}Panel", triggers=triggers, images=images)
    facts = build_facts(page, panel, name, states, triggers)
    scenarios = build_scenarios(list(states), name)
    targets = dict(targets, triggers=triggers)   # the acceptance check compares the trigger's open look too
    attempts, previous, failures = [], None, None
    best, best_key, retest = None, None, None
    for k in range(max_attempts):
        rec = {"attempt": k, "sections": None, "code": None}
        try:
            if retest:      # the last run failed for infrastructure reasons: test the same code again, no new write
                rec.update(retest)
                code, retest = rec["code"], None
            else:
                sections, raw = write_interaction(client, facts, name, previous=previous, failures=failures)
                rec["sections"], rec["raw"] = sections, raw
                code = assemble(page, panel["jsx"], sections, name)
                rec["code"] = code
            lint = _lint(code, out / f"attempt{k}")
            if not lint.get("ok"):
                msg = lambda v: (f"the code does not build (syntax error): {v.get('detail', '')}" if v.get("rule") == "parse-error"
                                 else f"lint: {v.get('rule')} {v.get('detail', '')}".strip())
                verdict = {"pass": False, "failures": [msg(v) for v in lint.get("violations", [])][:6], "state_scores": {}}
            else:
                try:
                    verdict = evaluate(runner(code, scenarios, out / f"attempt{k}"), targets, name)
                except RunnerError as e:
                    verdict = {"pass": False, "infra": True, "failures": [f"infrastructure: {e}"], "state_scores": {}}
                    retest = {"sections": rec["sections"], "raw": rec.get("raw"), "code": code}
        except WriterFormatError as e:
            verdict = {"pass": False, "failures": [f"format: {e}"], "state_scores": {}}
        rec["verdict"] = verdict
        attempts.append(rec)
        key = (verdict["pass"], min(verdict.get("state_scores", {}).values(), default=-1))
        if rec["code"] and (best_key is None or key > best_key):
            best, best_key = k, key
        if verdict["pass"]:
            break
        if verdict.get("infra"):
            continue
        if rec["sections"]:
            previous = rec["sections"]
        failures = verdict["failures"]
    return {"pass": bool(attempts and attempts[best]["verdict"]["pass"]) if best is not None else False,
            "attempts": attempts, "best_attempt": best, "code": attempts[best]["code"] if best is not None else None,
            "facts": facts, "kind": panel["kind"], "page": page, "panel": panel["jsx"]}
