"""Repair agent (orchestrator/repair.py, Phase 3 step 2): someone else's App.jsx + PixelCheck's measured check
report → Nemotron class edits scoped to one size (it cannot add, move or delete elements, so the author's code
stays) → re-check → best round kept, ≤ 3 rounds. Fake check, fake model; the real JSX tool applies the edits.
Written before the module (TDD, Oct 7). The benchmark bar is docs/REPAIR.md."""
import re

from orchestrator import repair as R

CODE = """export default function App() {
  return (
    <main className="w-[1280px] p-8">
      <h1 className="text-[48px] font-bold">Plan your week</h1>
      <p className="mt-2 text-[18px]">One calm list.</p>
      <button className="mt-6 px-4 py-2">Start</button>
    </main>
  );
}
"""

SPEC = {"breakpoints": {
    "mobile": {"size": [390, 844], "texts": [
        {"text": "Plan your week", "role": "heading", "box": [16, 40, 300, 34], "size_px": 30, "measured": True},
        {"text": "One calm list.", "role": "body", "box": [16, 90, 140, 20], "size_px": 16, "measured": True},
        {"text": "Start", "role": "button", "box": [16, 130, 40, 18], "size_px": 16, "measured": True}], "blocks": [], "background": "#ffffff"},
    "tablet": {"size": [768, 1024], "texts": [{"text": "Plan your week", "role": "heading", "box": [32, 40, 380, 50],
                                              "size_px": 44, "measured": True}], "blocks": [], "background": "#ffffff"},
    "desktop": {"size": [1280, 800], "texts": [{"text": "Plan your week", "role": "heading", "box": [32, 32, 380, 58],
                                               "size_px": 48, "measured": True}], "blocks": [], "background": "#ffffff"},
}}


def dom(texts):
    return [{"pc": pc, "text": t, "box": b, "font_size": f"{fs}px", "inked": True} for pc, t, b, fs in texts]


def report(worst, fails):
    return {"match": worst, "per_bp": {"mobile": worst, "tablet": 90.0, "desktop": 95.0},
            "breakpoints": {"mobile": {"score": worst, "missing_text": []}, "tablet": {"score": 90.0}, "desktop": {"score": 95.0}},
            "fluidity": {"pass": not fails, "fails": fails,
                         "widths": {str(w): {"overflow": 890 if w in fails else 0, "overlaps": 0, "ok": w not in fails} for w in (360, 375, 500, 1024, 1600)}}}


FIXED = re.compile(r"(?<![-\w])w-\[1280px\]")     # the class itself, not max-w-[1280px]


class FakeCheck:
    """Scores the code by whether the fixes are present: no fixed width → +20 and no overflow; small mobile heading → +10."""
    def __init__(self):
        self.seen = []

    def __call__(self, code):
        self.seen.append(code)
        fixed_w = bool(FIXED.search(code))
        small = "text-[30px]" in code
        worst = 50.0 + (0 if fixed_w else 20) + (10 if small else 0)
        fails = [360, 375, 500, 1024] if fixed_w else []
        pcs = dict(re.findall(r'data-pc="(\d+)"[^>]*>([^<]+)<', code))
        by_text = {v.strip(): k for k, v in pcs.items()}
        doms = {"mobile": dom([(by_text.get("Plan your week"), "Plan your week", [32, 32, 380, 58], 30 if small else 48),
                               (by_text.get("One calm list."), "One calm list.", [32, 100, 140, 22], 18),
                               (by_text.get("Start"), "Start", [32, 150, 40, 18], 16)]),
                "tablet": dom([]), "desktop": dom([])}
        return {"report": report(worst, fails), "dom": doms}


class FakeClient:
    """Round 1: unpin the width (all sizes); round 2: shrink the mobile heading; then nothing."""
    def __init__(self):
        self.calls = []
        self.run_spend = 0.0

    def edits(self, tagged, feedback):
        self.calls.append(feedback)
        pcs = re.findall(r'data-pc="(\d+)"', tagged)
        main, h1 = int(pcs[0]), int(pcs[1])
        if len(self.calls) == 1:
            return [{"id": main, "bp": "all", "add": "w-full max-w-[1280px]", "remove": "w-[1280px]", "why": "overflow"}]
        if len(self.calls) == 2:
            return [{"id": h1, "bp": "mobile", "add": "text-[30px]", "remove": "", "why": "font 48→30"}]
        return []


def run(**kw):
    chk, cl = FakeCheck(), FakeClient()
    out = R.repair(CODE, spec=SPEC, check=chk, propose=cl.edits, **{"candidates": 1, **kw})
    return out, chk, cl


def test_repair_improves_and_keeps_the_best_round():
    out, chk, cl = run()
    assert out["start"]["worst"] == 50.0 and out["best"]["worst"] == 80.0
    assert out["start"]["fluid_fails"] == 4 and out["best"]["fluid_fails"] == 0
    assert [h["worst"] for h in out["history"]] == [50.0, 70.0, 80.0]
    assert not FIXED.search(out["code"]) and "text-[30px]" in out["code"]


def test_the_delivered_code_has_no_tracking_ids_and_keeps_the_authors_lines():
    out, _, _ = run()
    assert "data-pc" not in out["code"]
    assert "Plan your week" in out["code"] and out["code"].count("<") == CODE.count("<")
    assert 0.5 <= out["lines_kept"] < 1.0


def test_feedback_is_measured_text_naming_ids_and_width_failures():
    out, chk, cl = run()
    fb = cl.calls[0]
    assert "sideways scroll" in fb and "360" in fb
    assert re.search(r"\[\d+\] 'Plan your week' mobile", fb) and "font 48→30" in fb
    assert "data:image" not in fb and "png" not in fb.lower()


def test_rounds_are_capped_and_stop_when_nothing_is_proposed():
    out, chk, cl = run(rounds=1)
    assert len(out["history"]) == 2 and len(cl.calls) == 1
    out, chk, cl = run(rounds=5)
    assert len(cl.calls) == 3 and len(out["history"]) == 3       # third proposal empty → stop


def test_a_worse_round_is_not_kept():
    chk = FakeCheck()

    def bad(tagged, feedback):
        pcs = re.findall(r'data-pc="(\d+)"', tagged)
        return [{"id": int(pcs[1]), "bp": "mobile", "add": "hidden", "remove": "", "why": "oops"}]

    def check(code):
        r = chk(code)
        if "hidden" in code:
            r["report"] = report(20.0, [360])
        return r
    out = R.repair(CODE, spec=SPEC, check=check, propose=bad, rounds=1, candidates=1)
    assert out["best"]["worst"] == 50.0 and "hidden" not in out["code"] and out["code"] == CODE


def test_lines_kept_counts_unchanged_original_lines():
    assert R.lines_kept("a\nb\nc\nd", "a\nb\nc\nd") == 1.0
    assert R.lines_kept("a\nb\nc\nd", "a\nB\nc\nd") == 0.75
    assert R.lines_kept("a\n  b\n", "a\nb\n") == 1.0            # whitespace-insensitive


def test_one_shot_arm_gets_no_measurements_and_is_checked_once():
    chk, cl = FakeCheck(), FakeClient()
    out = R.one_shot(CODE, spec=SPEC, check=chk, propose=cl.edits)
    assert len(chk.seen) == 2 and len(cl.calls) == 1             # before + after, one proposal
    assert "sideways scroll" not in cl.calls[0] and "Plan your week" in cl.calls[0]
    assert out["start"]["worst"] == 50.0 and "data-pc" not in out["code"]


# round structure v2 (Oct 7, after the first dev run: every round asked the same question and one bad edit sank the
# good ones): several candidates per round (temperatures), per-size acceptance (edits are scoped to one size, so each
# size keeps the edits of the candidate that improved it), notes on what failed, structure hints by parent element
class SizeCheck:
    """mobile +15 with "mob-fix"; tablet +15 with "tab-fix", −20 with "tab-bad"; desktop fixed."""
    def __init__(self):
        self.n = 0

    def __call__(self, code):
        self.n += 1
        m = 40 + (15 if "mob-fix" in code else 0)
        t = 40 + (15 if "tab-fix" in code else 0) - (20 if "tab-bad" in code else 0)
        rep = {"match": min(m, t, 90), "per_bp": {"mobile": m, "tablet": t, "desktop": 90},
               "breakpoints": {}, "fluidity": {"pass": True, "fails": [], "widths": {}}}
        return {"report": rep, "dom": {}}


def _ids(tagged):
    return [int(x) for x in re.findall(r'data-pc="(\d+)"', tagged)]


def mixed_propose(calls):
    def propose(tagged, fb, temperature=0.4):
        calls.append((temperature, fb))
        h1 = _ids(tagged)[1]
        if temperature < 0.5:      # good for mobile, bad for tablet
            return [{"id": h1, "bp": "mobile", "add": "mob-fix", "remove": "", "why": ""},
                    {"id": h1, "bp": "tablet", "add": "tab-bad", "remove": "", "why": ""}]
        if temperature < 0.9:      # good for tablet
            return [{"id": h1, "bp": "tablet", "add": "tab-fix", "remove": "", "why": ""}]
        return []
    return propose


def test_each_size_keeps_the_edits_of_the_candidate_that_improved_it():
    calls = []
    out = R.repair(CODE, spec=SPEC, check=SizeCheck(), propose=mixed_propose(calls), rounds=1, candidates=3)
    assert out["best"]["per_bp"] == {"mobile": 55, "tablet": 55, "desktop": 90}
    assert "mob-fix" in out["code"] and "tab-fix" in out["code"] and "tab-bad" not in out["code"]
    assert sorted(t for t, _ in calls) == [0.3, 0.7, 1.0]


def test_the_next_round_is_told_what_failed():
    calls = []

    def propose(tagged, fb, temperature=0.4):
        calls.append(fb)
        h1 = _ids(tagged)[1]
        return [{"id": h1, "bp": "tablet", "add": "tab-bad", "remove": "", "why": ""}]
    R.repair(CODE, spec=SPEC, check=SizeCheck(), propose=propose, rounds=2, candidates=1, feedback_fn=lambda *a: "rows")
    assert len(calls) == 2 and "made tablet worse" in calls[1] and "tab-bad" not in calls[0]


def test_structure_hint_names_the_parent_and_the_designs_columns():
    code = """export default function App() {
  return (
    <footer className="flex flex-row gap-4">
      <a className="text-sm">FAQ</a>
      <a className="text-sm">Help Centre</a>
      <a className="text-sm">Terms of Use</a>
      <a className="text-sm">Privacy</a>
    </footer>
  );
}
"""
    from orchestrator import jsx_edit
    tagged, els = jsx_edit.tag(code)
    ids = {e["text"]: e["id"] for e in els if e["tag"] == "a"}
    spec = {"breakpoints": {"tablet": {"size": [768, 1024], "texts": [
        {"text": "FAQ", "box": [32, 880, 40, 14], "size_px": 14, "measured": True},
        {"text": "Help Centre", "box": [390, 880, 90, 14], "size_px": 14, "measured": True},
        {"text": "Terms of Use", "box": [32, 914, 100, 14], "size_px": 14, "measured": True},
        {"text": "Privacy", "box": [390, 914, 60, 14], "size_px": 14, "measured": True}]}}}
    dom = {"tablet": [{"pc": str(ids[t]), "text": t, "box": [32 + 120 * k, 620, 80, 14], "font_size": "14px"}
                      for k, t in enumerate(["FAQ", "Help Centre", "Terms of Use", "Privacy"])]}
    fb = R.feedback({"fluidity": {}}, dom, spec, els)
    assert re.search(r"STRUCTURE \[0\] tablet: .*2 columns × 2 rows", fb)


def test_a_centred_single_column_is_not_reported_as_columns():
    """Heading left, button label centred: different x, one item per row → no structure hint (the first dev run
    called this '2 columns' and the model turned the form into a grid)."""
    from orchestrator import jsx_edit
    code = """export default function App() {
  return (
    <div className="w-full">
      <h1 className="text-[24px]">Sign in</h1>
      <p className="text-[16px]">Welcome back</p>
      <button className="w-full">Continue</button>
      <a className="block">Get help</a>
    </div>
  );
}
"""
    tagged, els = jsx_edit.tag(code)
    ids = {e["text"]: e["id"] for e in els}
    spec = {"breakpoints": {"mobile": {"size": [390, 844], "texts": [
        {"text": "Sign in", "box": [37, 40, 120, 28], "size_px": 24, "measured": True},
        {"text": "Welcome back", "box": [37, 90, 140, 16], "size_px": 16, "measured": True},
        {"text": "Continue", "box": [157, 300, 80, 18], "size_px": 16, "measured": True},
        {"text": "Get help", "box": [37, 400, 60, 16], "size_px": 16, "measured": True}]}}}
    dom = {"mobile": [{"pc": str(ids[t]), "text": t, "box": [21, 40 + 60 * k, 100, 16], "font_size": "16px"}
                      for k, t in enumerate(["Sign in", "Welcome back", "Continue", "Get help"])]}
    fb = R.feedback({"fluidity": {}}, dom, spec, els)
    assert "STRUCTURE" not in fb


def test_items_under_a_structure_hint_get_no_position_rows_and_far_offsets_are_flagged():
    from orchestrator import jsx_edit
    code = """export default function App() {
  return (
    <main>
      <h1 className="text-[40px]">Title</h1>
      <footer className="flex flex-row gap-4">
        <a>FAQ</a>
        <a>Help Centre</a>
        <a>Terms of Use</a>
        <a>Privacy</a>
      </footer>
    </main>
  );
}
"""
    tagged, els = jsx_edit.tag(code)
    ids = {e["text"]: e["id"] for e in els if e["tag"] in ("a", "h1")}
    spec = {"breakpoints": {"tablet": {"size": [768, 1024], "texts": [
        {"text": "Title", "box": [32, 300, 200, 48], "size_px": 40, "measured": True},
        {"text": "FAQ", "box": [32, 880, 40, 14], "size_px": 14, "measured": True},
        {"text": "Help Centre", "box": [390, 880, 90, 14], "size_px": 14, "measured": True},
        {"text": "Terms of Use", "box": [32, 914, 100, 14], "size_px": 14, "measured": True},
        {"text": "Privacy", "box": [390, 914, 60, 14], "size_px": 14, "measured": True}]}}}
    dom = {"tablet": [{"pc": str(ids["Title"]), "text": "Title", "box": [32, 40, 200, 48], "font_size": "40px"}] +
                     [{"pc": str(ids[t]), "text": t, "box": [32 + 120 * k, 620, 80, 14], "font_size": "14px"}
                      for k, t in enumerate(["FAQ", "Help Centre", "Terms of Use", "Privacy"])]}
    fb = R.feedback({"fluidity": {}}, dom, spec, els)
    assert "STRUCTURE" in fb and "'FAQ'" not in fb and "'Privacy'" not in fb
    assert re.search(r"'Title' tablet: far off .*\+260", fb) and "not with margins" in fb


def test_the_repair_prompt_states_the_rules():
    assert "relative to the CURRENT value" in R.REPAIR_SYSTEM and "64" in R.REPAIR_SYSTEM
    assert "mx-auto" in R.REPAIR_SYSTEM and "cannot move, add or delete" in R.REPAIR_SYSTEM


def test_new_width_failures_need_a_real_gain():
    """A +0.6 worst-size gain that adds two width-sweep failures is not progress; +3 can be."""
    base = {"worst": 21.27, "fluid_fails": 0}
    assert not R.better({"worst": 21.9, "fluid_fails": 2}, base)
    assert R.better({"worst": 24.5, "fluid_fails": 1}, base)
    assert R.better({"worst": 22.0, "fluid_fails": 0}, base)
    assert R.better({"worst": 21.3, "fluid_fails": 0}, {"worst": 21.27, "fluid_fails": 3})


def test_the_repair_prompt_carries_the_design_spec_and_the_measurements():
    """The repair arm = the design spec (what the one-shot arm gets) + the sandbox's measurements."""
    calls = []

    def propose(tagged, fb, temperature=0.4):
        calls.append(fb)
        return []
    R.repair(CODE, spec=SPEC, check=FakeCheck(), propose=propose, rounds=1, candidates=1)
    assert "MEASURED" in calls[0] and "DESIGN" in calls[0] and "| Plan your week |" in calls[0]
