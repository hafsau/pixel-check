"""Fix brief (Oct 20, judging-criteria review): Nemotron turns a check's measurements into what to do next — a short
summary and a message to paste into an AI builder — and a verifier outside the model drops every claim the
measurements don't back. Facts, verifier and template are pure (no model). Written before orchestrator/brief.py."""
import json

import pytest

from orchestrator import brief as B

# the Lovable check (Oct 13), as saved in check.json
LOVABLE = {
    "source": {"url": "https://adaptable-hub-central.lovable.app/"},
    "report": {"mode": "check", "match": 38.49, "worst": "mobile",
               "per_bp": {"mobile": 38.49, "tablet": 61.13, "desktop": 64.54},
               "warnings": ['mobile: the "Edit with Lovable" badge covers "Weekly Activity" (a platform badge, not your layout)'],
               "fluidity": {"pass": True, "fails": [], "widths": {"360": {"overflow": 0, "ok": True}}}},
    "diagnostics": {
        "mobile": {"text": [{"text": "1h 20m", "status": "moved", "dy": -152, "dx": 94}],
                   "drift": {"bands": [{"y0": 0, "y1": 144, "dy": -14}, {"y0": 724, "y1": 870, "dy": -150}], "scale": 0.803},
                   "lost": {"layout": 42.5}, "font": {"design": "Lato", "build": "Roboto"}, "text_size": 0.89},
        "tablet": {"text": [{"text": "minutes moved each day", "status": "below", "dy": 28, "dx": 72}],
                   "drift": {"bands": [{"y0": 0, "y1": 170, "dy": 6}, {"y0": 850, "y1": 1024, "dy": 26}], "scale": 1.024},
                   "lost": {}, "font": {"design": "Lato", "build": "Roboto"}, "text_size": 1.0},
        "desktop": {"text": [], "drift": {"bands": [{"y0": 0, "y1": 196, "dy": 6}], "scale": 1.004},
                    "lost": {}, "font": {"design": "Lato", "build": "Roboto"}, "text_size": 1.0},
    },
}

AUDIT = {"source": {"url": "https://interview-sage--hafsausmani.replit.app/"},
         "report": {"mode": "audit", "warnings": ['mobile: the Replit badge covers "Generate Questions" (a platform badge, not your layout)'],
                    "vanished": {"mobile": ["Dashboard", "Question Bank"], "tablet": []},
                    "fluidity": {"pass": False, "fails": ["360"], "widths": {"360": {"overflow": 220, "overlaps": 0, "ok": False}}}},
         "diagnostics": {}}


def by_kind(facts, kind):
    return [f for f in facts if f["kind"] == kind]


# ---------------------------------------------------------------- facts

def test_facts_are_numbered_plain_sentences_with_their_numbers():
    facts = B.facts(LOVABLE)
    assert [f["id"] for f in facts] == [f"F{i}" for i in range(1, len(facts) + 1)]
    font = by_kind(facts, "font")
    assert len(font) == 1 and font[0]["bp"] is None                 # the same finding at every size: said once
    assert "Roboto" in font[0]["text"] and "Lato" in font[0]["text"]
    size = by_kind(facts, "text_size")
    assert len(size) == 1 and size[0]["bp"] == "mobile" and 11 in size[0]["nums"]
    drift = {f["bp"]: f for f in by_kind(facts, "drift")}
    assert set(drift) == {"mobile"}                                  # tablet 2.4 %, desktop 0.4 %: too small to act on
    assert {20, 150} <= set(drift["mobile"]["nums"]) and "tighter" in drift["mobile"]["text"]
    moved = by_kind(facts, "moved")[0]
    assert moved["quote"] == "1h 20m" and 152 in moved["nums"] and "higher" in moved["text"]
    assert by_kind(facts, "below")[0]["quote"] == "minutes moved each day"
    assert by_kind(facts, "warning")[0]["text"] == 'On mobile, the "Edit with Lovable" badge covers "Weekly Activity".'
    assert B.facts({"report": {"warnings": ['585 px: the "Edit with Lovable" badge covers "Weekly Activity" (a platform badge, not your layout)']}})[0]["text"] \
        == 'At 585 px, the "Edit with Lovable" badge covers "Weekly Activity".'
    assert B.facts({"report": {"warnings": ["media query at exactly 768 px"]}})[0]["text"] == "media query at exactly 768 px."


def test_audit_facts_cover_width_failures_and_vanished_text():
    facts = B.facts(AUDIT)
    width = by_kind(facts, "width")[0]
    assert {360, 220} <= set(width["nums"]) and "sideways" in width["text"]
    gone = by_kind(facts, "vanished")[0]
    assert gone["bp"] == "mobile" and "Dashboard" in gone["text"] and "Question Bank" in gone["text"]
    assert by_kind(facts, "warning")


def test_a_clean_check_has_no_facts():
    clean = {"report": {"mode": "check", "warnings": [], "fluidity": {"pass": True, "fails": [], "widths": {}}},
             "diagnostics": {"mobile": {"text": [], "drift": {"bands": [], "scale": 1.0}, "font": None, "text_size": 1.0}}}
    assert B.facts(clean) == []
    assert B.facts({}) == []


# ---------------------------------------------------------------- verifier

def test_items_citing_measured_facts_are_kept():
    facts = B.facts(LOVABLE)
    f = {k: by_kind(facts, k)[0]["id"] for k in ("font", "text_size", "drift")}
    raw = {"summary": [{"text": "On phones the build is about 20% tighter than the design.", "facts": [f["drift"]]}],
           "fix_prompt": [{"text": "Use Lato instead of Roboto.", "facts": [f["font"]]},
                          {"text": "On mobile, make the text about 12% larger.", "facts": [f["text_size"]]}]}
    out = B.verify(raw, facts)
    assert [i["text"] for i in out["summary"]] == ["On phones the build is about 20% tighter than the design."]
    assert len(out["fix"]) == 2 and out["dropped"] == 0


@pytest.mark.parametrize("item", [
    {"text": "Make the header sticky.", "facts": []},                                   # no citation
    {"text": "Use Lato instead of Roboto.", "facts": ["F99"]},                          # unknown fact
    {"text": "On mobile, increase spacing by 45%.", "facts": ["DRIFT"]},                # number not in the fact
    {"text": "On mobile, move “Start Workout” up.", "facts": ["MOVED"]},       # quoted text not in the fact
    {"text": "", "facts": ["FONT"]},                                                    # empty
    "Use Lato.",                                                                        # not an object
])
def test_unbacked_items_are_dropped(item):
    facts = B.facts(LOVABLE)
    ids = {"DRIFT": by_kind(facts, "drift")[0]["id"], "MOVED": by_kind(facts, "moved")[0]["id"], "FONT": by_kind(facts, "font")[0]["id"]}
    if isinstance(item, dict):
        item = {**item, "facts": [ids.get(x, x) for x in item["facts"]]}
    out = B.verify({"summary": [], "fix_prompt": [item]}, facts)
    assert out["fix"] == [] and out["dropped"] == 1


def test_numbers_within_tolerance_and_px_widths_pass():
    facts = B.facts(AUDIT)
    w = by_kind(facts, "width")[0]["id"]
    out = B.verify({"summary": [], "fix_prompt": [{"text": "At 360 px the page scrolls sideways by about 220 px; make it fit.", "facts": [w]}]}, facts)
    assert len(out["fix"]) == 1


def test_duplicates_and_overflow_are_trimmed():
    facts = B.facts(LOVABLE)
    fid = by_kind(facts, "font")[0]["id"]
    item = {"text": "Use Lato instead of Roboto.", "facts": [fid]}
    out = B.verify({"summary": [], "fix_prompt": [item] * 3 + [{"text": f"Use Lato ({i}).", "facts": [fid]} for i in range(20)]}, facts)
    assert len(out["fix"]) <= B.MAX_FIX and sum(i["text"] == item["text"] for i in out["fix"]) == 1


def test_garbage_model_output_verifies_to_nothing():
    facts = B.facts(LOVABLE)
    for raw in (None, [], "text", {"summary": "x"}, {"fix_prompt": None}):
        out = B.verify(raw, facts)
        assert out["summary"] == [] and out["fix"] == []


# ---------------------------------------------------------------- template

def test_template_turns_every_fact_into_a_backed_instruction():
    facts = B.facts(LOVABLE)
    t = B.template(facts)
    assert t["summary"] and t["fix"]
    assert B.verify({"summary": t["summary"], "fix_prompt": t["fix"]}, facts)["dropped"] == 0   # it passes its own verifier
    text = " ".join(i["text"] for i in t["fix"])
    assert "Lato" in text and "larger" in text and "spacing" in text
    assert any("badge" in n["text"].lower() for n in t["notes"])          # badges are a note, never an instruction


def test_template_for_an_audit():
    t = B.template(B.facts(AUDIT))
    text = " ".join(i["text"] for i in t["fix"])
    assert "360 px" in text and "Dashboard" in text


# ---------------------------------------------------------------- the brief

class FakeClient:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def chat(self, model, messages, **kw):
        self.calls.append({"model": model, "messages": messages, **kw})
        if self.error:
            raise self.error
        return type("R", (), {"content": json.dumps(self.reply) if not isinstance(self.reply, str) else self.reply,
                              "model": model, "usd": 0.001})()


def test_brief_uses_nemotron_and_keeps_only_backed_claims():
    facts = B.facts(LOVABLE)
    fid, did = by_kind(facts, "font")[0]["id"], by_kind(facts, "drift")[0]["id"]
    client = FakeClient({"summary": [{"text": "Same layout; phones drift about 20% tighter.", "facts": [did]}],
                         "fix_prompt": [{"text": "Use Lato instead of Roboto.", "facts": [fid]},
                                        {"text": "Add a dark mode toggle.", "facts": []}]})
    out = B.brief(LOVABLE, client=client)
    assert out["source"] == "nemotron" and out["dropped"] == 1
    assert out["fix"][0] == {"text": "Use Lato instead of Roboto.", "facts": [fid]}       # Nemotron's line first
    assert all(i.get("added") for i in out["fix"][1:]) and out["added"] == len(out["fix"]) - 1
    assert out["facts"] == facts and out["intro"].startswith("Please")
    call = client.calls[0]
    assert call["model"] == B.config.MODEL_BRIEF and call["step"] == "brief" and call.get("thinking", "off") == "off"
    prompt = json.dumps(call["messages"])
    assert "Roboto" in prompt and "image_url" not in prompt        # facts as text; no image ever enters the prompt


@pytest.mark.parametrize("client", [FakeClient(error=RuntimeError("429")), FakeClient("not json"),
                                    FakeClient({"summary": [], "fix_prompt": [{"text": "Make it pop.", "facts": []}]})])
def test_brief_falls_back_to_the_template_when_nemotron_fails_or_nothing_survives(client):
    out = B.brief(LOVABLE, client=client)
    assert out["source"] == "template" and out["fix"]
    assert B.verify({"summary": out["summary"], "fix_prompt": out["fix"]}, out["facts"])["dropped"] == 0


def test_nothing_to_fix_calls_no_model():
    client = FakeClient({"summary": [], "fix_prompt": []})
    out = B.brief({"report": {"mode": "check", "warnings": [], "fluidity": {"widths": {}}}, "diagnostics": {}}, client=client)
    assert out["source"] == "none" and out["fix"] == [] and client.calls == []


def test_code_builds_get_tailwind_wording():
    out = B.brief({**LOVABLE, "source": {"code": True}}, client=None)
    assert "App.jsx" in out["intro"]


# ---- after the first real brief (Oct 20): per-text moves on a drifting size, single quotes, the missing font fix

def test_moves_explained_by_spacing_drift_are_dropped():
    """'move days down 113 px' on a size whose spacing is 20 % tighter would push the builder to pixel hacks"""
    facts = B.facts(LOVABLE)
    moved = by_kind(facts, "moved")[0]["id"]
    out = B.verify({"summary": [], "fix_prompt": [{"text": "On mobile, move “1h 20m” down about 152 px.", "facts": [moved]}]}, facts)
    assert out["fix"] == [] and out["dropped"] == 1
    no_drift = {**LOVABLE, "diagnostics": {"mobile": {**LOVABLE["diagnostics"]["mobile"], "drift": None}}}
    f2 = B.facts(no_drift)
    m2 = by_kind(f2, "moved")[0]["id"]
    assert B.verify({"summary": [], "fix_prompt": [{"text": "On mobile, move “1h 20m” down about 152 px.", "facts": [m2]}]}, f2)["fix"]


def test_single_quoted_text_must_be_in_the_cited_facts_too():
    facts = B.facts(LOVABLE)
    fid = by_kind(facts, "warning")[0]["id"]
    bad = B.verify({"summary": [{"text": "On mobile, the badge covers 'Start Workout'.", "facts": [fid]}]}, facts)
    good = B.verify({"summary": [{"text": "On mobile, the badge covers 'Weekly Activity'; don't miss it.", "facts": [fid]}]}, facts)
    assert bad["summary"] == [] and len(good["summary"]) == 1


def test_a_font_missing_text_or_width_fact_no_instruction_covers_is_added_from_the_template():
    facts = B.facts(LOVABLE)
    did = by_kind(facts, "drift")[0]["id"]
    client = FakeClient({"summary": [], "fix_prompt": [{"text": "On mobile, increase the spacing by about 25%.", "facts": [did]}]})
    out = B.brief(LOVABLE, client=client)
    assert out["source"] == "nemotron"
    font = [i for i in out["fix"] if "Lato" in i["text"]]
    assert len(font) == 1 and font[0].get("added") is True
    assert not any(i.get("added") for i in out["fix"] if "spacing" in i["text"])


def test_the_prompt_tells_nemotron_about_drift_consequences_and_positioning():
    assert "consequence" in B.SYSTEM and "absolute" in B.SYSTEM


# ---- council on the first real briefs (Oct 20): every flagged claim got through the verifier — now each is dropped

def _ids(facts, kind, n=0):
    return by_kind(facts, kind)[n]["id"]


def _kept(text, facts, ids, where="fix_prompt"):
    out = B.verify({"summary": [], "fix_prompt": [], where: [{"text": text, "facts": ids}]}, facts)
    return bool(out["summary"] or out["fix"])


def test_numbers_carry_units_and_must_match_the_cited_unit():
    facts = B.facts(LOVABLE)
    d = _ids(facts, "drift")
    assert _kept("On mobile, increase the spacing by about 25%.", facts, [d])
    assert not _kept("On mobile, set the card padding to 25 px.", facts, [d])          # 25 % ≠ 25 px
    assert not _kept("On mobile, increase the spacing by 150%.", facts, [d])           # 150 px ≠ 150 %
    for junk in ("line height 1.25", "weight 600", "26 rem", "2 percent tighter", "colour #7c3aed"):
        assert not _kept(f"On mobile, use {junk}.", facts, [d]), junk


def test_small_numbers_have_a_tight_tolerance():
    facts = B.facts(LOVABLE)
    t = _ids(facts, "text_size")                                                        # 11 % / 12 %
    assert _kept("On mobile, make the text about 12% larger.", facts, [t])
    assert _kept("On mobile, make the text about 13% larger.", facts, [t])
    assert not _kept("On mobile, make the text about 16% larger.", facts, [t])


def test_an_item_may_only_name_sizes_its_facts_cover():
    facts = B.facts(LOVABLE)
    t = _ids(facts, "text_size")                                                        # a mobile fact
    assert not _kept("On desktop, make the text about 12% larger.", facts, [t])
    assert not _kept("Make the text about 12% larger at all sizes.", facts, [t])
    f = _ids(facts, "font")                                                             # every size
    assert _kept("Use Lato instead of Roboto at all sizes.", facts, [f])


def test_any_drift_explained_move_drops_the_item_and_positioning_words_are_banned():
    facts = B.facts(LOVABLE)
    f, m = _ids(facts, "font"), _ids(facts, "moved")
    assert not _kept("Use Lato and move “1h 20m” lower.", facts, [f, m])
    for bad in ("use absolute positioning for the header", "set top: 150px", "raise its z-index", "make the nav fixed"):
        assert not _kept(f"On mobile, {bad}.", facts, [_ids(facts, "drift")]), bad


def test_overclaim_and_causal_words_are_dropped():
    facts = B.facts(LOVABLE)
    w = _ids(facts, "warning")
    for text in ('The "Edit with Lovable" badge obscures key text like "Weekly Activity" and other labels.',
                 'On mobile, the badge covers "Weekly Activity", making it inaccessible.',
                 "This makes the whole dashboard unusable on every device."):
        assert not _kept(text, facts, [w], where="summary"), text
    assert _kept('On mobile, the "Edit with Lovable" badge covers "Weekly Activity".', facts, [w], where="summary")


def test_platform_badges_become_a_note_never_a_layout_instruction():
    facts = B.facts(LOVABLE)
    w = _ids(facts, "warning")
    assert not _kept('Keep "Weekly Activity" clear of the badge.', facts, [w])          # no fix item may act on a badge
    t = B.template(facts)
    assert not any("badge" in i["text"].lower() for i in t["fix"])
    assert t["notes"] and all("badge" in n["text"].lower() for n in t["notes"])
    out = B.brief(LOVABLE, client=None)
    assert out["notes"] and not any("badge" in i["text"].lower() for i in out["fix"])


def test_lost_text_always_uses_the_template_line():
    facts = B.facts(AUDIT)
    v = _ids(facts, "vanished")
    assert not _kept("On mobile, make sure “Dashboard” is visible.", facts, [v])
    client = FakeClient({"summary": [], "fix_prompt": [{"text": "On mobile, show “Dashboard”.", "facts": [v]}]})
    out = B.brief(AUDIT, client=client)
    gone = [i for i in out["fix"] if "Dashboard" in i["text"]]
    assert len(gone) == 1 and "not intended" in gone[0]["text"]


def test_spacing_under_five_percent_is_not_a_fact():
    facts = B.facts(LOVABLE)
    assert {f["bp"] for f in by_kind(facts, "drift")} == {"mobile"}                      # tablet 2.4 % dropped


def test_the_three_real_briefs_flagged_items_are_now_dropped():
    """verbatim items from the Oct 20 runs that the council marked overclaim / wrong / risky"""
    facts = B.facts(LOVABLE)
    w = [f["id"] for f in by_kind(facts, "warning")]
    flagged = [("summary", "On mobile, text is too small and vertical spacing is too tight, causing content to sit higher than "
                           "intended, while the 'Edit with Lovable' badge obscures key text like 'Weekly Activity', 'Minutes moved "
                           "each day', and other labels.", [_ids(facts, "text_size"), _ids(facts, "drift")] + w),
               ("fix_prompt", "Ensure the 'Edit with Lovable' badge does not cover any content, especially 'Weekly Activity' and "
                              "'Minutes moved each day', by keeping content clear of the badge area at all sizes.", w)]
    for where, text, ids in flagged:
        assert not _kept(text, facts, ids, where=where), text
    af = B.facts(AUDIT)
    assert not _kept('On mobile, the Replit badge overlaps and obscures the button labeled "Generate Questions", making it '
                     "inaccessible.", af, [_ids(af, "warning")], where="summary")
    assert not _kept("Ensure the Replit badge does not overlap any interactive or textual content on mobile by adjusting "
                     "layout or positioning so it stays clear of UI elements.", af, [_ids(af, "warning")])


def test_an_instruction_from_size_specific_facts_must_name_the_size():
    """'Increase the font size by about 12%' from a mobile-only fact would change every size when pasted"""
    facts = B.facts(LOVABLE)
    t, f = _ids(facts, "text_size"), _ids(facts, "font")
    assert not _kept("Increase the font size by about 12%.", facts, [t])
    assert _kept("On mobile, increase the font size by about 12%.", facts, [t])
    assert _kept("On phones, increase the font size by about 12%.", facts, [t])
    assert _kept("Change the font from Roboto to Lato.", facts, [f])                   # a whole-page fact needs no size
    assert _kept("Increase the font size by about 12%.", facts, [t], where="summary")  # only instructions must say where


# ---- real run 3 (Oct 20): Nemotron's mobile lines lacked "on mobile", were rightly dropped, and the brief lost its point

def test_every_actionable_fact_no_instruction_covers_gets_its_template_line():
    facts = B.facts(LOVABLE)
    f = _ids(facts, "font")
    client = FakeClient({"summary": [], "fix_prompt": [{"text": "Change the font from Roboto to Lato.", "facts": [f]},
                                                       {"text": "Increase the font size by about 12%.", "facts": [_ids(facts, "text_size")]}]})
    out = B.brief(LOVABLE, client=client)
    texts = [i["text"] for i in out["fix"]]
    assert texts[0] == "Change the font from Roboto to Lato."                          # Nemotron's kept lines first
    assert any(t.startswith("On mobile, make the text about 12% larger") for t in texts)
    assert any(t.startswith("On mobile, increase the vertical spacing") for t in texts)
    assert out["added"] == 2 and out["dropped"] == 1


def test_dropped_claims_are_listed_with_the_reason():
    facts = B.facts(LOVABLE)
    out = B.verify({"summary": [{"text": "It is completely broken.", "facts": [_ids(facts, "font")]}],
                    "fix_prompt": [{"text": "Increase the font size by about 12%.", "facts": [_ids(facts, "text_size")]},
                                   {"text": "Add a hero video.", "facts": []},
                                   {"text": "On mobile, use 26 rem.", "facts": [_ids(facts, "drift")]}]}, facts)
    why = {d["text"]: d["why"] for d in out["dropped_items"]}
    assert out["dropped"] == 4 == len(out["dropped_items"])
    assert why["It is completely broken."] == "says more than the measurements (overclaim or cause)"
    assert why["Increase the font size by about 12%."] == "does not say which size it applies to"
    assert why["Add a hero video."] == "cites no measured fact"
    assert why["On mobile, use 26 rem."] == "a number the measurements do not contain"


def test_the_prompt_asks_for_the_size_first():
    assert "On mobile" in B.SYSTEM


def test_an_instruction_must_not_narrow_a_whole_page_finding_to_one_size():
    """real run 4: 'On mobile, use the Lato font instead of Roboto' — the font is wrong at every size"""
    facts = B.facts(LOVABLE)
    f = _ids(facts, "font")
    assert not _kept("On mobile, use the Lato font instead of Roboto.", facts, [f])
    assert _kept("Use the Lato font instead of Roboto.", facts, [f])
    out = B.verify({"fix_prompt": [{"text": "On mobile, use the Lato font instead of Roboto.", "facts": [f]}]}, facts)
    assert out["dropped_items"][0]["why"] == "narrows a whole-page finding to one size"
