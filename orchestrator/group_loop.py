"""Gate B' end to end (docs/INTERACTIONS.md): sibling interactions from ONE example state.

planner "nemotron": orchestrator/planner.plan_group (outline + example + designer notes);
        "repeat":   deterministic repeat-detector — controls of the example trigger's size/weight in its row; content
                    the frames do not show stays the base texts (it cannot read notes);
        "template": the example member only (plus the member selected in the base frame).
All three plans go through the same compile (orchestrator/groups.py) and tests; scored against the given state frame
and the held-out ones neither planner saw.
"""
from __future__ import annotations

import json
from pathlib import Path

from .acceptance import _score_full
from .fluid import compile_fluid
from .groups import PlanError as GroupError
from .groups import compile_swap
from .interact_loop import RunnerError, _lint
from .planner import PlanError, build_outline, plan_group, to_swap_plan
from .states import state_diff

BPS = ("mobile", "tablet", "desktop")
STATE_MIN = 75.0      # reported; the verdict is relative (DELTA_TOL)
DELTA_TOL = 3.0


def load_targets(d: Path, states: list[str]) -> dict:
    """{"base": {bp: png}, "base_texts": {bp: json}, "members": {state: {"states": {bp: png}, "texts": {bp: json}}}}"""
    bps = [bp for bp in BPS if (d / f"{bp}.png").exists()]
    return {"base": {bp: d / f"{bp}.png" for bp in bps}, "base_texts": {bp: d / f"{bp}.text.json" for bp in bps},
            "members": {s: {"states": {bp: d / f"{bp}.{s}.png" for bp in bps if (d / f"{bp}.{s}.png").exists()},
                            "texts": {bp: d / f"{bp}.{s}.text.json" for bp in bps if (d / f"{bp}.{s}.text.json").exists()}}
                        for s in states}}


def example_of(base_spec: dict, given: dict, bp: str = "mobile") -> dict:
    """The example as text: what the given state frame changed (state_diff), with the trigger box."""
    d = state_diff(base_spec["breakpoints"][bp], given["frames"][bp], given["trigger"].get(bp))
    order = lambda ts: [t["text"] for t in sorted(ts, key=lambda t: (t["box"][1], t["box"][0]))]
    return {"trigger": given["trigger"].get(bp), "kind": d["kind"],
            "appeared": order(d["appeared"]["texts"]), "disappeared": order(d["disappeared"]["texts"])}


def _slots(outline: list[dict], example: dict) -> list[int]:
    gone = [" ".join(t.split()).lower() for t in example["disappeared"]]
    out, used = [], set()
    for g in gone:          # the base frame's text the example replaced (not the trigger's own label)
        hit = next((o["id"] for o in outline if o["id"] not in used and not o["example_trigger"] and
                    " ".join(o["text"].split()).lower() == g and (not out or o["box"][1] >= outline[out[-1]]["box"][1] - 4)), None)
        if hit is not None:
            out.append(hit)
            used.add(hit)
    return out


def repeat_plan(outline: list[dict], example: dict) -> dict:
    ex = next(o for o in outline if o["example_trigger"])
    size_w = " ".join(ex["style"].split()[:2])
    members = [o for o in outline if " ".join(o["style"].split()[:2]) == size_w and abs(o["box"][1] - ex["box"][1]) <= 8]
    slots = _slots(outline, example)
    base_txt = [outline[s]["text"] for s in slots]
    appeared = list(example["appeared"])
    # the member selected in the base frame: its label is one of the replaced texts (a tab titles its card)
    init = next((i for i, m in enumerate(members) if m["text"].lower() in {t.lower() for t in base_txt}), 0)
    ex_content = appeared[:len(slots)] + base_txt[len(appeared):]
    return {"kind": "tabs" if len(members) > 2 else "toggle", "exclusive": True, "initial": init, "slots": slots,
            "members": [{"trigger": m["id"], "content": ex_content if m["id"] == ex["id"] else list(base_txt)}
                        for m in members]}


def template_plan(outline: list[dict], example: dict) -> dict:
    p = repeat_plan(outline, example)
    ex_id = next(o["id"] for o in outline if o["example_trigger"])
    keep = [i for i, m in enumerate(p["members"]) if i == p["initial"] or m["trigger"] == ex_id]
    return dict(p, members=[p["members"][i] for i in keep], initial=keep.index(p["initial"]) if p["initial"] in keep else 0)


def _member_boxes(base_spec: dict, outline: list[dict], tid: int) -> dict:
    """The member's trigger box at every breakpoint: the same text, same occurrence in reading order."""
    t = " ".join(outline[tid]["text"].split()).lower()
    nth = sum(1 for o in outline if o["id"] < tid and " ".join(o["text"].split()).lower() == t)
    out = {}
    for bp, f in base_spec["breakpoints"].items():
        same = sorted([x for x in f.get("texts", []) if x.get("box") and " ".join(x["text"].split()).lower() == t],
                      key=lambda x: (x["box"][1], x["box"][0]))
        if nth < len(same):
            out[bp] = same[nth]["box"]
    return out


def run_group(base_spec: dict, given: dict, targets: dict, notes: str, planner: str, client, runner, out: Path,
              name: str = "group") -> dict:
    if planner not in ("nemotron", "repeat", "template"):
        raise ValueError(f"unknown planner {planner!r} (nemotron | repeat | template)")
    out.mkdir(parents=True, exist_ok=True)
    example = example_of(base_spec, given)
    outline = build_outline(base_spec["breakpoints"]["mobile"], example["trigger"])
    info = {"usd": 0.0}
    if planner == "nemotron":
        plan, info = plan_group(client, base_spec["breakpoints"]["mobile"], example, notes)
    elif planner == "repeat":
        plan = repeat_plan(outline, example)
    else:
        plan = template_plan(outline, example)
    if plan["kind"] not in ("tabs", "toggle"):
        raise PlanError(f"group kind {plan['kind']} not compiled yet")
    sp = to_swap_plan(plan, outline)
    triggers = {f"{name}{i}": _member_boxes(base_spec, outline, m["trigger_id"]) for i, m in enumerate(sp["members"])}
    page = compile_fluid(base_spec, triggers=triggers, auto_menu=False)
    code = compile_swap(page, sp, name)
    (out / "plan.json").write_text(json.dumps({"planner": planner, "plan": plan, "swap": sp}, indent=1))
    lint = _lint(code, out / "run")
    if not lint.get("ok"):
        raise GroupError(f"compiled group does not lint: {lint.get('violations')}")
    # which member each target state belongs to (state name = the member's label, case-insensitive)
    label = {i: " ".join(m["trigger"].split()).lower() for i, m in enumerate(sp["members"])}
    want = {s: next((i for i, l in label.items() if l == s.lower()), None) for s in targets["members"]}
    bps = list(targets["base"])
    scen = []
    for bp in bps:
        scen.append({"name": f"{bp}.base", "bp": bp, "steps": []})
        for s, i in want.items():
            if i is not None:
                scen.append({"name": f"{bp}.{s}", "bp": bp, "steps": [{"click": f'[data-trigger="{name}{i}"]'}]})
    static = runner(compile_fluid(base_spec, auto_menu=False), [{"name": f"{bp}.base", "bp": bp, "steps": []} for bp in bps],
                    out / "static")
    res_dir = runner(code, scen, out / "run")
    res = json.loads((res_dir / "interact.json").read_text())
    sc = {x["name"]: x for x in res.get("scenarios", [])}
    verdict = {"members": {}, "base_failures": [], "failures": [], "base_scores": {}}
    for bp in bps:
        ref = float(_score_full(targets["base"][bp], static, f"{bp}.base", targets["base_texts"].get(bp))["score"])
        got = float(_score_full(targets["base"][bp], res_dir, f"{bp}.base", targets["base_texts"].get(bp))["score"])
        verdict["base_scores"][bp] = round(got, 2)
        if got < ref - 3:
            verdict["base_failures"].append(f"{bp}: before any click {got:.1f} vs static {ref:.1f}")
    given_name = given["name"]
    for s, i in want.items():
        m = verdict["members"].setdefault(s, {"scores": {}, "delta": {}, "pass": False, "held_out": s != given_name,
                                              "planned": i is not None})
        if i is None:
            continue
        ok = True
        for bp in bps:
            if bp not in targets["members"][s]["states"]:
                continue
            r = sc.get(f"{bp}.{s}")
            if not r or not r["ok"]:
                ok = False
                verdict["failures"].append(f"{bp}.{s}: {(r or {}).get('error') or 'scenario missing'}")
                continue
            full = _score_full(targets["members"][s]["states"][bp], res_dir, f"{bp}.{s}", targets["members"][s]["texts"].get(bp))
            m["scores"][bp] = round(float(full["score"]), 2)
            # as faithful as the untouched page is to the base frame (the static page's fidelity is not the
            # interaction's to fix); wrong content loses the text match and falls below
            m["delta"][bp] = round(m["scores"][bp] - verdict["base_scores"][bp], 2)
            sel = r.get("aria_selected") if plan["kind"] == "tabs" else r.get("aria_pressed")
            ok = ok and m["delta"][bp] >= -DELTA_TOL and sel == "true"
        m["pass"] = ok and bool(m["scores"])
    held = [v for v in verdict["members"].values() if v["held_out"]]
    score_of = lambda v: min(v["scores"].values()) if v["scores"] else 0.0
    verdict["held_out_pass"] = sum(1 for v in held if v["pass"])
    verdict["held_out_mean"] = round(sum(score_of(v) for v in held) / max(1, len(held)), 2)
    verdict["held_out_delta"] = round(sum(min(v["delta"].values()) if v["delta"] else -100.0 for v in held)
                                      / max(1, len(held)), 2)
    return {"plan": plan, "code": code, "verdict": verdict, "usd": info.get("usd", 0.0), "planner": planner}
