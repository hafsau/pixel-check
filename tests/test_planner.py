"""Gate B' interaction planner (Nemotron): page outline + ONE example state + designer notes → a verified plan of
sibling interactions (ids from the outline). Written before the implementation (TDD, Oct 2). Scripted client."""
import json

import pytest

from orchestrator.planner import PlanError, build_outline, plan_group, to_swap_plan, validate


def T(text, box, role="body", size=14, weight=400, color="#000000"):
    return {"text": text, "box": list(box), "role": role, "size_px": size, "weight": weight, "color": color}


BASE = {"size": [390, 844], "texts": [
    T("Tabs", (20, 80, 80, 30), "heading", 30, 700),
    T("Overview", (40, 380, 60, 14), "nav", 14, 500), T("Analytics", (128, 380, 60, 14), "nav", 14, 500, "#626262"),
    T("Reports", (200, 380, 50, 14), "nav", 14, 500, "#626262"), T("Settings", (262, 380, 50, 14), "nav", 14, 500, "#626262"),
    T("Overview", (60, 440, 80, 16), "heading", 16, 500), T("View your key metrics.", (60, 470, 240, 20)),
    T("You have 12 active projects.", (60, 500, 240, 20))]}
EXAMPLE = {"trigger": [128, 376, 77, 25],
           "appeared": ["Analytics", "Track performance.", "Page views are up 25%."],
           "disappeared": ["Overview", "View your key metrics.", "You have 12 active projects."]}
NOTES = "Reports: 'Generate reports.' / 'You have 5 reports.' Settings: 'Manage preferences.' / 'Configure themes.'"
REPLY = {"kind": "tabs", "exclusive": True, "initial": 0, "slots": [5, 6, 7],
         "members": [{"trigger": 1, "content": ["Overview", "View your key metrics.", "You have 12 active projects."]},
                     {"trigger": 2, "content": ["Analytics", "Track performance.", "Page views are up 25%."]},
                     {"trigger": 3, "content": ["Reports", "Generate reports.", "You have 5 reports."]},
                     {"trigger": 4, "content": ["Settings", "Manage preferences.", "Configure themes."]}]}


class Reply:
    def __init__(self, c):
        self.content, self.reasoning, self.usd = c, "", 0.001


class Scripted:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat(self, model, messages, **kw):
        self.calls.append((messages, kw))
        return Reply(self.replies.pop(0) if self.replies else "{}")


def test_outline_lists_texts_with_ids_and_marks_the_example_trigger():
    o = build_outline(BASE, EXAMPLE["trigger"])
    assert o[2]["id"] == 2 and o[2]["text"] == "Analytics" and o[2]["example_trigger"]
    assert not o[1]["example_trigger"] and o[5]["text"] == "Overview"
    assert o[5]["style"] == "16px 500 #000000"


def test_plan_prompt_carries_outline_example_and_notes_verbatim():
    c = Scripted([json.dumps(REPLY)])
    plan, _ = plan_group(c, BASE, EXAMPLE, NOTES)
    msgs, kw = c.calls[0]
    user = msgs[-1]["content"]
    assert "[2] \"Analytics\"" in user and "EXAMPLE TRIGGER" in user
    assert "Track performance." in user and "View your key metrics." in user
    assert NOTES in user
    assert kw.get("thinking") == "off" and plan["kind"] == "tabs"


def test_plan_reply_with_fences_and_prose_parses():
    c = Scripted(["Sure, here is the plan:\n```json\n" + json.dumps(REPLY) + "\n```"])
    plan, _ = plan_group(c, BASE, EXAMPLE, NOTES)
    assert len(plan["members"]) == 4


def test_validate_accepts_a_consistent_plan():
    assert validate(REPLY, build_outline(BASE, EXAMPLE["trigger"]), EXAMPLE) == []


@pytest.mark.parametrize("mutate,msg", [
    (lambda p: p["members"].pop(1), "example trigger"),                                 # the example must be a member
    (lambda p: p["members"][2].update(trigger=99), "no outline id 99"),
    (lambda p: p["members"][3].update(content=["Settings"]), "content"),                 # slot count mismatch
    (lambda p: p["members"][1].update(content=["Analytics", "Wrong.", "Page views are up 25%."]), "example"),
    (lambda p: p["members"][0].update(content=["Overview", "Changed.", "You have 12 active projects."]), "base"),
    (lambda p: p["members"][3].update(trigger=2), "twice"),
    (lambda p: p.update(kind="carousel"), "kind"),
])
def test_validate_names_each_problem(mutate, msg):
    import copy
    p = copy.deepcopy(REPLY)
    mutate(p)
    errs = validate(p, build_outline(BASE, EXAMPLE["trigger"]), EXAMPLE)
    assert errs and any(msg in e for e in errs), errs


def test_invalid_plan_is_revised_once_with_the_errors():
    import copy
    bad = copy.deepcopy(REPLY)
    bad["members"].pop(1)
    c = Scripted([json.dumps(bad), json.dumps(REPLY)])
    plan, info = plan_group(c, BASE, EXAMPLE, NOTES)
    assert len(c.calls) == 2 and "example trigger" in c.calls[1][0][-1]["content"]
    assert plan == REPLY and info["revisions"] == 1


def test_still_invalid_after_revision_raises():
    c = Scripted(["not json", "still not json"])
    with pytest.raises(PlanError):
        plan_group(c, BASE, EXAMPLE, NOTES)


def test_to_swap_plan_resolves_ids_to_texts_and_occurrences():
    sp = to_swap_plan(REPLY, build_outline(BASE, EXAMPLE["trigger"]))
    assert sp["slots"][0] == {"text": "Overview", "nth": 1}                              # the card title, not the tab
    assert sp["slots"][1] == {"text": "View your key metrics.", "nth": 0}
    assert sp["members"][2] == {"trigger": "Reports", "trigger_id": 3,
                                "slots": ["Reports", "Generate reports.", "You have 5 reports."]}
