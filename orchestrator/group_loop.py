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


def _n(t) -> str:
    return " ".join(((t["text"] if isinstance(t, dict) else t) or "").split())


def slot_accuracy(gt_base: list, gt_state: list, dom: list) -> tuple[float, list[str]]:
    """Exact content check against the held-out frame itself: the strings the state shows that the base frame does
    not (multiset) must be painted in the render, and the strings it no longer shows must be gone. Fuzzy scoring let
    '9 reports' pass for '5 reports' (council, Oct 5). → (fraction right, what is missing / stale)."""
    from collections import Counter
    b, st = Counter(_n(t) for t in gt_base), Counter(_n(t) for t in gt_state)
    shown = Counter(_n(d) for d in dom if d.get("inked") and d.get("onscreen", True) and _n(d))
    added, removed = st - b, b - st
    miss = [f"missing {t!r}" for t in added if shown[t] < st[t]]
    stale = [f"still shown {t!r}" for t, k in removed.items() if shown[t] > st.get(t, 0)]
    total = sum(added.values()) + sum(removed.values())
    return (1.0 if total == 0 else round(1 - (len(miss) + len(stale)) / max(1, len(added) + len(removed)), 3)), miss + stale


def example_of(base_spec: dict, given: dict, bp: str = "mobile") -> dict:
    """The example as text: what the given state frame changed (state_diff), with the trigger box."""
    d = state_diff(base_spec["breakpoints"][bp], given["frames"][bp], given["trigger"].get(bp))
    order = lambda ts: [t["text"] for t in sorted(ts, key=lambda t: (t["box"][1], t["box"][0]))]
    return {"trigger": given["trigger"].get(bp), "kind": d["kind"],
            "appeared": order(d["appeared"]["texts"]), "disappeared": order(d["disappeared"]["texts"])}


def _slots(outline: list[dict], example: dict, exclude: set = frozenset()) -> list[int]:
    gone = [" ".join(t.split()).lower() for t in example["disappeared"]]
    out, used = [], set(exclude)      # never a member's own control (the Overview tab label is not the card title)
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
    slots = _slots(outline, example, {m["id"] for m in members})
    base_txt = [outline[s]["text"] for s in slots]
    appeared = list(example["appeared"])
    # the member selected in the base frame: its label is one of the replaced texts (a tab titles its card)
    init = next((i for i, m in enumerate(members) if m["text"].lower() in {t.lower() for t in base_txt}), 0)
    ex_content = appeared[:len(slots)] + base_txt[len(appeared):]
    return {"kind": "tabs" if len(members) > 2 else "toggle", "exclusive": True, "initial": init, "slots": slots,
            "members": [{"trigger": m["id"], "content": ex_content if m["id"] == ex["id"] else list(base_txt)}
                        for m in members]}


def regex_plan(outline: list[dict], example: dict, notes: str) -> dict:
    """The honest non-model baseline (council, Oct 5): repeat-detector members, and for each member the quoted
    strings that follow its first mention in the notes fill its slots in order (a tab titles its card with its own
    name). Without quotes nothing changes — what is left for a model is notes that do not quote the copy."""
    import re
    p = repeat_plan(outline, example)
    base_txt = [outline[s]["text"] for s in p["slots"]]
    labels = [outline[m["trigger"]]["text"] for m in p["members"]]
    init_label = labels[p["initial"]] if p["members"] else ""
    title = 0 if base_txt and base_txt[0].lower() == init_label.lower() else None
    known = {p["initial"]} | {i for i, m in enumerate(p["members"]) if outline[m["trigger"]]["example_trigger"]}
    marks = sorted((m.start(), i) for i, lab in enumerate(labels)
                   for m in [re.search(r"\b%s\b" % re.escape(lab), notes or "", re.I)] if m)
    quotes = [(q.start(), (q.group(1) or q.group(2)).strip()) for q in re.finditer(r'"([^"]+)"|\u201c([^\u201d]+)\u201d', notes or "")]
    for k, (start, i) in enumerate(marks):
        if i in known:
            continue
        end = marks[k + 1][0] if k + 1 < len(marks) else len(notes)
        qs = [q for at, q in quotes if start <= at < end]
        if not qs:
            continue
        content = list(base_txt)
        if title is not None:
            content[title] = labels[i]
        for j, q in zip([j for j in range(len(base_txt)) if j != title], qs):
            content[j] = q
        p["members"][i]["content"] = content
    return p


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
    if planner not in ("nemotron", "regex", "repeat", "template"):
        raise ValueError(f"unknown planner {planner!r} (nemotron | regex | repeat | template)")
    out.mkdir(parents=True, exist_ok=True)
    example = example_of(base_spec, given)
    outline = build_outline(base_spec["breakpoints"]["mobile"], example["trigger"])
    info = {"usd": 0.0}
    if planner == "nemotron":
        plan, info = plan_group(client, base_spec["breakpoints"]["mobile"], example, notes)
    elif planner == "repeat":
        plan = repeat_plan(outline, example)
    elif planner == "regex":
        plan = regex_plan(outline, example, notes)
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
        if plan["kind"] == "tabs":     # keyboard: from the selected tab, ArrowRight selects the next one
            i0 = plan.get("initial") or 0
            nxt = (i0 + 1) % len(sp["members"])
            scen.append({"name": f"{bp}.{name}.kbd", "bp": bp, "steps": [{"focus": f'[data-trigger="{name}{i0}"]'},
                                                                          {"key": "ArrowRight"},
                                                                          {"check": f'[data-trigger="{name}{nxt}"]'}]})
    static = runner(compile_fluid(base_spec, auto_menu=False), [{"name": f"{bp}.base", "bp": bp, "steps": []} for bp in bps],
                    out / "static")
    res_dir = runner(code, scen, out / "run")
    res = json.loads((res_dir / "interact.json").read_text())
    sc = {x["name"]: x for x in res.get("scenarios", [])}
    verdict = {"members": {}, "base_failures": [], "failures": [], "base_scores": {}, "keyboard": {}}
    for bp in bps:
        ref = float(_score_full(targets["base"][bp], static, f"{bp}.base", targets["base_texts"].get(bp))["score"])
        got = float(_score_full(targets["base"][bp], res_dir, f"{bp}.base", targets["base_texts"].get(bp))["score"])
        verdict["base_scores"][bp] = round(got, 2)
        if got < ref - 3:
            verdict["base_failures"].append(f"{bp}: before any click {got:.1f} vs static {ref:.1f}")
    if plan["kind"] == "tabs":
        for bp in bps:
            k = sc.get(f"{bp}.{name}.kbd")
            verdict["keyboard"][bp] = bool(k and k["ok"] and k.get("aria_selected") == "true")
            if not verdict["keyboard"][bp]:
                verdict["failures"].append(f"{bp}: ArrowRight from the selected tab does not select the next one")
    given_name = given["name"]
    for s, i in want.items():
        m = verdict["members"].setdefault(s, {"scores": {}, "delta": {}, "pass": False, "held_out": s != given_name,
                                              "planned": i is not None, "slot_accuracy": 0.0, "content_errors": []})
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
            gt_b = json.loads(targets["base_texts"][bp].read_text()) if targets["base_texts"].get(bp) else []
            gt_s = json.loads(targets["members"][s]["texts"][bp].read_text()) if targets["members"][s]["texts"].get(bp) else []
            dom_p = res_dir / f"{bp}.{s}.dom.json"
            acc, errs = slot_accuracy(gt_b, gt_s, json.loads(dom_p.read_text()) if dom_p.exists() else [])
            m.setdefault("acc", {})[bp] = acc
            m["content_errors"] += [f"{bp}: {e}" for e in errs]
            ok = ok and m["delta"][bp] >= -DELTA_TOL and sel == "true" and acc == 1.0 and verdict["keyboard"].get(bp, True)
        m["slot_accuracy"] = min(m.get("acc", {}).values(), default=0.0)
        m["pass"] = ok and bool(m["scores"])
    held = [v for v in verdict["members"].values() if v["held_out"]]
    score_of = lambda v: min(v["scores"].values()) if v["scores"] else 0.0
    verdict["held_out_pass"] = sum(1 for v in held if v["pass"])
    verdict["held_out_mean"] = round(sum(score_of(v) for v in held) / max(1, len(held)), 2)
    verdict["held_out_delta"] = round(sum(min(v["delta"].values()) if v["delta"] else -100.0 for v in held)
                                      / max(1, len(held)), 2)
    return {"plan": plan, "code": code, "verdict": verdict, "usd": info.get("usd", 0.0), "planner": planner}
