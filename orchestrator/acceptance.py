"""Stage 5 (docs/INTERACTIONS.md): acceptance tests generated from state frames, and their verdict.

build_scenarios → the steps the sandbox harness runs (sandbox/render.mjs --interact) per breakpoint that has a state
frame: base · open (click trigger) · closed (click twice) · esc (open, Escape) · kbd (focus trigger, Enter).
evaluate → scores every captured frame against the design (base frame or state frame) with the same scorer as the
static pipeline, checks aria-expanded, and returns failures written for the interaction writer (Nemotron).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sandbox"))
import score  # noqa: E402

STATE_MIN = 75.0    # an opened state must match its state frame at least this well
CLOSE_TOL = 3.0     # closing must restore the base page to within this of the untouched page's score


def trigger_selector(name: str) -> str:
    return f'[data-trigger="{name}"]'


def build_scenarios(bps: list[str], name: str) -> list[dict]:
    t = trigger_selector(name)
    out = []
    for bp in bps:
        out += [
            {"name": f"{bp}.base", "bp": bp, "steps": []},
            {"name": f"{bp}.{name}", "bp": bp, "steps": [{"click": t}]},
            # closing: the user clicks the same spot again (a drawer may cover the trigger with its own close button)
            {"name": f"{bp}.{name}.closed", "bp": bp, "steps": [{"click": t}, {"click_at": t}]},
            {"name": f"{bp}.{name}.esc", "bp": bp, "steps": [{"click": t}, {"key": "Escape"}]},
            {"name": f"{bp}.{name}.kbd", "bp": bp, "steps": [{"focus": t}, {"key": "Enter"}]},
        ]
    return out


def _score_full(target: Path, out: Path, shot: str, texts: Path | None) -> dict:
    t, r = score.load(target), score.load(out / f"{shot}.png")
    tt = json.loads(texts.read_text()) if texts and texts.exists() else None
    rd = json.loads((out / f"{shot}.dom.json").read_text()) if tt is not None and (out / f"{shot}.dom.json").exists() else None
    aux = {k: score.load(out / f"{shot}.{k}.png") for k in ("notext", "coded") if (out / f"{shot}.{k}.png").exists()}
    res = score.score_pair(t, r, tt, rd, **aux) if len(aux) == 2 and tt is not None else score.score_pair(t, r, tt, rd)
    if tt:   # the scorer reports lower-case strings; give the writer the design's own spelling
        orig = {" ".join((x["text"] if isinstance(x, dict) else x).split()).lower(): (x["text"] if isinstance(x, dict) else x)
                for x in tt}
        res["missing_text"] = [orig.get(m, m) for m in res.get("missing_text") or []]
    return res


def _score(target: Path, out: Path, shot: str, texts: Path | None) -> float:
    return float(_score_full(target, out, shot, texts)["score"])


def _why(res: dict, dom: list | None = None) -> str:
    """What the scorer saw: design texts not visible in the render, and the largest differing regions — with the
    render's painted texts inside each extra/colour region (from the capture's DOM) so the writer knows what is there."""
    parts = []
    miss = res.get("missing_text") or []
    if miss:
        parts.append("not visible: " + ", ".join(repr(m) for m in miss[:6]))

    def shows(r):
        if not dom or r["kind"] == "missing":
            return ""
        x, y, w, h = r["box"]

        def overlap(b):      # DOM boxes are whole elements (a full-width <p>): overlap, not centre
            ix = max(0, min(x + w, b[0] + b[2]) - max(x, b[0]))
            iy = max(0, min(y + h, b[1] + b[3]) - max(y, b[1]))
            return ix * iy / max(1, min(w * h, b[2] * b[3]))
        inside = [t["text"] for t in dom if t.get("inked") and t.get("text") and overlap(t["box"]) >= 0.3]
        return (" shows " + ", ".join(repr(" ".join(t.split())[:40]) for t in inside[:3])) if inside else ""
    regs = [r for r in (res.get("regions") or []) if r.get("kind") in ("missing", "extra", "color")][:3]
    if regs:
        parts.append("differing regions [x, y, w, h]: " + "; ".join(f"{r['kind']} {r['box']}{shows(r)}" for r in regs))
    return (" — " + " · ".join(parts)) if parts else ""


def _dom(out: Path, shot: str) -> list | None:
    p = out / f"{shot}.dom.json"
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except json.JSONDecodeError:
        return None


def trigger_look_failure(design_base, design_state, render_open, box_d, box_r=None) -> str | None:
    """The design's open trigger look (inside box_d of the state frame) against the render's, taken inside the
    render's own trigger box box_r (aligned by centre; the static layout may have put the trigger elsewhere — that
    costs the static score, not this check). Only when the design's trigger changes when open. → message or None."""
    import numpy as np
    x, y, w, h = [int(v) for v in box_d]
    a_ = np.asarray(design_state, dtype=float)[y:y + h, x:x + w]
    b_ = np.asarray(design_base, dtype=float)[y:y + h, x:x + w]
    if box_r:
        rx = int(round(box_r[0] + box_r[2] / 2 - w / 2))
        ry = int(round(box_r[1] + box_r[3] / 2 - h / 2))
    else:
        rx, ry = x, y
    r_ = np.asarray(render_open, dtype=float)[max(0, ry):ry + h, max(0, rx):rx + w]
    if not a_.size or r_.shape != a_.shape:
        return None
    # ink = clearly off the trigger's background, in either image; thin icons are a few % of the box, so compare
    # ink, not area
    ring = np.concatenate([a_[0], a_[-1], a_[:, 0], a_[:, -1]])
    bgc = np.median(ring, axis=0)
    ia = np.linalg.norm(a_ - bgc, axis=-1) > 60
    ir = np.linalg.norm(r_ - bgc, axis=-1) > 60
    ib = np.linalg.norm(b_ - bgc, axis=-1) > 60 if b_.shape == a_.shape else ~ia
    # only when the design's trigger changes when open (hamburger → X); otherwise it is part of the static page
    if (ia ^ ib).sum() <= 0.1 * max(1, (ia | ib).sum()):
        return None
    union = (ia | ir).sum()
    if union >= 12 and (ia ^ ir).sum() / union > 0.35:
        where = f"the render's trigger box {[rx, ry, w, h]}" if box_r else f"the trigger box {[x, y, w, h]}"
        return (f"the trigger's open look does not match the design ({(ia ^ ir).sum() / union * 100:.0f} % of its ink "
                f"differs inside {where})")
    return None


def evaluate(out: Path, targets: dict, name: str, state_min: float = STATE_MIN, close_tol: float = CLOSE_TOL) -> dict:
    """targets: {"base": {bp: png}, "states": {bp: png}, optional "base_texts"/"state_texts": {bp: text.json}}.
    → {"pass", "failures": [str], "state_scores": {bp}, "base_scores": {bp}, "checks": [...]}"""
    res = json.loads((out / "interact.json").read_text())
    if res.get("build_failed"):
        return {"pass": False, "failures": [f"the code does not build: {res['build_failed'][:300]}"],
                "state_scores": {}, "base_scores": {}, "checks": []}
    sc = {s["name"]: s for s in res.get("scenarios", [])}
    failures, checks, state_scores, base_scores = [], [], {}, {}
    bt, stt = targets.get("base_texts", {}), targets.get("state_texts", {})
    for bp, state_png in targets["states"].items():
        base_png = targets["base"][bp]
        base = sc.get(f"{bp}.base")
        if not base or not base["ok"]:
            failures.append(f"{bp}: the page did not render")
            continue
        bfull = _score_full(base_png, out, f"{bp}.base", bt.get(bp))
        ref = float(bfull["score"])
        base_scores[bp] = ref
        be = (targets.get("base_expected") or {}).get(bp)
        if be is not None and ref < be - close_tol:   # the closed page must still match the design like the static page
            failures.append(f"{bp}: before any click the page does not match the design (score {ref:.1f}; the page "
                            f"without the interaction scores {be:.1f}) — nothing may open or be added until the trigger "
                            f"is clicked{_why(bfull, _dom(out, f'{bp}.base'))}")
        op = sc.get(f"{bp}.{name}")
        if not op or not op["ok"]:
            failures.append(f"{bp}: clicking the trigger failed: {(op or {}).get('error') or 'scenario missing'}")
            continue
        full = _score_full(state_png, out, f"{bp}.{name}", stt.get(bp))
        s_open = float(full["score"])
        state_scores[bp] = s_open
        checks.append({"bp": bp, "check": "opens", "score": s_open})
        if s_open < state_min:
            failures.append(f"{bp}: after clicking the trigger the page does not match the state frame "
                            f"(score {s_open:.1f} < {state_min:.0f}){_why(full, _dom(out, f'{bp}.{name}'))}")
        pv = op.get("panel")
        if pv is not None:   # accessibility: aria-controls must name the rendered panel (checked even when it looks right)
            if not pv.get("id"):
                failures.append(f"{bp}: the trigger has no aria-controls pointing at the panel's id")
            elif not pv.get("exists"):
                failures.append(f"{bp}: aria-controls=\"{pv['id']}\" but no element with that id is rendered when open")
            elif not pv.get("on_top") and s_open < state_min and pv.get("covered_by") == "(zero size)":
                failures.append(f"{bp}: the panel #{pv['id']} is rendered with zero width or height")
            elif not pv.get("on_top") and s_open < state_min:
                failures.append(f"{bp}: the panel #{pv['id']} is rendered but covered by {pv.get('covered_by')} "
                                f"(put that element before the panel in the JSX or give the panel a higher z-index)")
        tb = (targets.get("triggers") or {}).get(bp)
        if tb:   # the trigger's open look (hamburger → X) against the design, inside the render's own trigger box
            msg = trigger_look_failure(score.load(base_png), score.load(state_png), score.load(out / f"{bp}.{name}.png"),
                                       tb, op.get("trigger_box"))
            if msg:
                failures.append(f"{bp}: {msg}")
        if op.get("aria_expanded") != "true":
            failures.append(f"{bp}: aria-expanded on the trigger is {op.get('aria_expanded')!r} after opening (want \"true\")")
        cl = sc.get(f"{bp}.{name}.closed")
        if not cl or not cl["ok"]:     # a step that errors (e.g. a layer swallows the second click) is a failure
            failures.append(f"{bp}: clicking the trigger again failed: {(cl or {}).get('error') or 'scenario missing'}")
        else:
            s_cl = _score(base_png, out, f"{bp}.{name}.closed", bt.get(bp))
            checks.append({"bp": bp, "check": "closes", "score": s_cl})
            if s_cl < ref - close_tol:
                failures.append(f"{bp}: clicking the trigger again does not restore the page (score {s_cl:.1f} vs {ref:.1f})")
            elif cl.get("aria_expanded") not in ("false", None) and op.get("aria_expanded") == "true":
                failures.append(f"{bp}: aria-expanded stays {cl.get('aria_expanded')!r} after closing (want \"false\")")
        es = sc.get(f"{bp}.{name}.esc")
        if es and not es["ok"]:
            failures.append(f"{bp}: opening then pressing Escape failed: {es.get('error')}")
        elif es and s_open >= state_min:
            s_es = _score(base_png, out, f"{bp}.{name}.esc", bt.get(bp))
            checks.append({"bp": bp, "check": "escape", "score": s_es})
            if s_es < ref - close_tol:
                failures.append(f"{bp}: pressing Escape does not close it (score {s_es:.1f} vs {ref:.1f}; "
                                f"aria-expanded {es.get('aria_expanded')!r})")
        kb = sc.get(f"{bp}.{name}.kbd")
        if kb and not kb["ok"]:
            failures.append(f"{bp}: keyboard (focus the trigger, press Enter) failed: {kb.get('error')}")
        elif kb:
            s_kb = _score(state_png, out, f"{bp}.{name}.kbd", stt.get(bp))
            checks.append({"bp": bp, "check": "keyboard", "score": s_kb})
            if s_kb < state_min and s_open >= state_min:   # when clicking fails too, that failure already says it
                failures.append(f"{bp}: keyboard (focus the trigger, press Enter) does not open it (score {s_kb:.1f})")
    for i in res.get("duplicate_ids") or []:
        failures.append(f"id \"{i}\" is used by more than one element — ids must be unique (aria-controls names one "
                        f"element; give the id to a single container)")
    dead = res.get("unknown_classes") or []
    if dead:
        failures.append("these classes produce no CSS (invalid arbitrary value — Tailwind or the browser drops it), so "
                        "they have no effect: " + ", ".join(dead[:8]) + " — valid forms: bg-[#rrggbb]/[0.5], bg-[#rrggbb]/50, bg-black/50")
    for e in res.get("runtime_errors", []):
        failures.append(f"runtime error: {e}")
    return {"pass": not failures, "failures": failures, "state_scores": state_scores, "base_scores": base_scores,
            "checks": checks}
