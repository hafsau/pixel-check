"""Gate B' end to end for swap groups (docs/INTERACTIONS.md): plan (Nemotron / repeat-detector / template) → compiled
group → generated scenarios → scored against the given AND held-out state frames. Written before the implementation
(TDD, Oct 2). Real dev capture (skipped when absent); scripted Nemotron reply."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "benchmarks-dev" / "shadcn-tabs-lx"
pytestmark = pytest.mark.skipif(not (D / "mobile.reports.png").exists(), reason="dev captures not present")
sys.path.insert(0, str(ROOT / "tools"))


def inputs(which="oracle"):
    from oracle_spec import frame
    from orchestrator.group_loop import load_targets
    base = json.loads((ROOT / "out" / "specs" / f"shadcn-tabs-lx{'.oracle' if which == 'oracle' else ''}.json").read_text())
    meta = json.loads((D / "meta-analytics.json").read_text())
    given = {"name": "analytics", "trigger": {bp: v["box"] for bp, v in meta["trigger"].items()},
             "frames": {bp: frame("shadcn-tabs-lx", bp, state="analytics") for bp in meta["trigger"]}}
    targets = load_targets(D, ["analytics", "reports", "settings"])
    return base, given, targets


def test_targets_hold_given_and_held_out_states():
    _, _, t = inputs()
    assert set(t["members"]) == {"analytics", "reports", "settings"} and set(t["base"]) == {"mobile", "tablet", "desktop"}
    assert t["members"]["reports"]["states"]["mobile"].name == "mobile.reports.png"


def test_repeat_and_template_baselines_plan_deterministically():
    from orchestrator.group_loop import example_of, repeat_plan, template_plan
    from orchestrator.planner import build_outline, validate
    base, given, _ = inputs()
    ex = example_of(base, given)
    assert ex["kind"] == "swap" and "Track performance and user engagement metrics. Monitor trends and identify growth opportunities." in ex["appeared"]
    o = build_outline(base["breakpoints"]["mobile"], ex["trigger"])
    rp = repeat_plan(o, ex)
    assert [o[m["trigger"]]["text"] for m in rp["members"]] == ["Overview", "Analytics", "Reports", "Settings"]
    assert rp["initial"] == 0 and len(rp["slots"]) == 3 and validate(rp, o, ex) == []
    assert rp["members"][2]["content"] == [o[s]["text"] for s in rp["slots"]]          # unknown → the base texts
    tp = template_plan(o, ex)
    assert [o[m["trigger"]]["text"] for m in tp["members"]] == ["Overview", "Analytics"] and validate(tp, o, ex) == []


def nemotron_reply(base, given):
    """What a correct plan looks like (content from the frozen notes) — scripted, no model call."""
    from orchestrator.group_loop import example_of
    from orchestrator.planner import build_outline
    ex = example_of(base, given)
    o = build_outline(base["breakpoints"]["mobile"], ex["trigger"])
    tid = {x["text"]: x["id"] for x in o if x["style"].startswith("14px 500")}
    slots = [x["id"] for x in o if x["box"][1] > 420 and x["box"][1] < 600][:3]
    notes = {"Overview": [o[s]["text"] for s in slots],
             "Analytics": ["Analytics", "Track performance and user engagement metrics. Monitor trends and identify growth opportunities.", "Page views are up 25% compared to last month."],
             "Reports": ["Reports", "Generate and download your detailed reports. Export data in multiple formats for analysis.", "You have 5 reports ready and available to export."],
             "Settings": ["Settings", "Manage your account preferences and options. Customize your experience to fit your needs.", "Configure notifications, security, and themes."]}
    return json.dumps({"kind": "tabs", "exclusive": True, "initial": 0, "slots": slots,
                       "members": [{"trigger": tid[k], "content": v} for k, v in notes.items()]})


class Scripted:
    def __init__(self, replies):
        self.replies = list(replies)

    def chat(self, model, messages, **kw):
        class R:
            pass
        r = R()
        r.content, r.reasoning, r.usd = self.replies.pop(0), "", 0.001
        return r


def test_nemotron_plan_passes_held_out_tabs_and_repeat_baseline_does_not(tmp_path):
    from orchestrator.group_loop import run_group
    from orchestrator.interact_loop import local_runner
    base, given, targets = inputs()
    notes = (D / "notes.md").read_text()
    nem = run_group(base, given, targets, notes, "nemotron", Scripted([nemotron_reply(base, given)]), local_runner,
                    tmp_path / "n", name="tabs")
    v = nem["verdict"]
    # relative criterion: after the click the page matches that member's state frame as well as the untouched page
    # matches the base frame (the static page's own fidelity is not the interaction's to fix)
    assert v["members"]["reports"]["pass"] and v["members"]["settings"]["pass"], v
    assert v["members"]["analytics"]["pass"] and not v["base_failures"], v
    assert v["held_out_pass"] == 2 and v["held_out_delta"] >= -3
    assert v["keyboard"] and all(v["keyboard"].values()), v["keyboard"]        # ArrowRight moves the selection
    rep = run_group(base, given, targets, notes, "repeat", None, local_runner, tmp_path / "r", name="tabs")
    assert rep["verdict"]["members"]["analytics"]["pass"] and rep["verdict"]["held_out_pass"] == 0
    assert rep["verdict"]["held_out_delta"] < v["held_out_delta"] - 3


def test_unknown_planner_is_an_error_not_the_template(tmp_path):
    """A mistyped planner ("nemotron --notes=notes" from a shell quoting slip) silently ran the template."""
    from orchestrator.group_loop import run_group
    from orchestrator.interact_loop import local_runner
    base, given, targets = inputs()
    with pytest.raises(ValueError, match="planner"):
        run_group(base, given, targets, "", "nemotron --notes=notes", None, local_runner, tmp_path, name="tabs")


def test_repeat_baseline_swaps_the_card_title_not_the_tab_label():
    """Council (Oct 5): _slots picked the Overview tab label (a trigger) instead of the card title."""
    from orchestrator.group_loop import example_of, repeat_plan
    from orchestrator.planner import build_outline
    base, given, _ = inputs()
    ex = example_of(base, given)
    o = build_outline(base["breakpoints"]["mobile"], ex["trigger"])
    rp = repeat_plan(o, ex)
    triggers = {m["trigger"] for m in rp["members"]}
    assert not set(rp["slots"]) & triggers
    assert o[rp["slots"][0]]["style"].startswith("16px")                     # the card title, not a 14 px tab label


def test_slot_accuracy_counts_exact_strings_added_and_removed():
    from orchestrator.group_loop import slot_accuracy
    gt_base = ["Overview", "Analytics", "Reports", "Overview", "View your key metrics.", "You have 12 active projects."]
    gt_state = ["Overview", "Analytics", "Reports", "Reports", "Generate reports.", "You have 5 reports."]
    good = [{"text": t, "inked": True, "onscreen": True} for t in gt_state]
    acc, miss = slot_accuracy(gt_base, gt_state, good)
    assert acc == 1.0 and miss == []
    wrong = [dict(d) for d in good]
    wrong[-1]["text"] = "You have 9 reports."                                  # a wrong fact, fuzzy-close
    acc, miss = slot_accuracy(gt_base, gt_state, wrong)
    assert acc < 1.0 and any("You have 5 reports." in m for m in miss)
    stale = good + [{"text": "View your key metrics.", "inked": True, "onscreen": True}]   # old copy still shown
    acc, miss = slot_accuracy(gt_base, gt_state, stale)
    assert acc < 1.0 and any("View your key metrics." in m for m in miss)
    hidden = [dict(d, inked=False) if d["text"] == "Generate reports." else d for d in good]  # in the DOM, not painted
    assert slot_accuracy(gt_base, gt_state, hidden)[0] < 1.0


def test_wrong_facts_fail_the_held_out_state(tmp_path):
    """Council: '5 reports' → '9 reports', 'download' → 'delete', 'security' → 'billing' still passed 2/2."""
    from orchestrator.group_loop import run_group
    from orchestrator.interact_loop import local_runner
    base, given, targets = inputs()
    reply = json.loads(nemotron_reply(base, given))
    for m in reply["members"]:
        m["content"] = [c.replace("5 reports", "9 reports").replace("security", "billing") for c in m["content"]]
    res = run_group(base, given, targets, "", "nemotron", Scripted([json.dumps(reply)]), local_runner, tmp_path, name="tabs")
    v = res["verdict"]["members"]
    assert not v["reports"]["pass"] and not v["settings"]["pass"]
    assert v["reports"]["slot_accuracy"] < 1.0 and v["analytics"]["slot_accuracy"] == 1.0


@pytest.mark.parametrize("notes_file", ["notes.md", "notes_prose.md"])
def test_regex_baseline_reads_quoted_notes(notes_file):
    """Council (Oct 5): ~30 lines of regex reproduce Nemotron's plan from these notes (they quote the copy). It is the
    honest non-model baseline: repeat-detector members + quoted strings after each member's name."""
    from orchestrator.group_loop import example_of, regex_plan
    from orchestrator.planner import build_outline, validate
    base, given, _ = inputs()
    ex = example_of(base, given)
    o = build_outline(base["breakpoints"]["mobile"], ex["trigger"])
    rp = regex_plan(o, ex, (D / notes_file).read_text())
    by = {o[m["trigger"]]["text"]: m["content"] for m in rp["members"]}
    assert by["Reports"] == ["Reports", "Generate and download your detailed reports. Export data in multiple formats for analysis.",
                             "You have 5 reports ready and available to export."]
    assert by["Settings"][2] == "Configure notifications, security, and themes."
    assert validate(rp, o, ex) == []


def test_regex_baseline_without_quotes_keeps_base_texts():
    from orchestrator.group_loop import example_of, regex_plan, repeat_plan
    from orchestrator.planner import build_outline
    base, given, _ = inputs()
    ex = example_of(base, given)
    o = build_outline(base["breakpoints"]["mobile"], ex["trigger"])
    assert regex_plan(o, ex, "Reports lets people generate their reports.")["members"] == repeat_plan(o, ex)["members"]
