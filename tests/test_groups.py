"""Gate B' group compiler (docs/INTERACTIONS.md): planned sibling interactions → deterministic code.
Swap groups (tabs, toggles): the swapped texts become slots whose text depends on the selected member.
Written before the implementation (TDD, Oct 2)."""
import pytest

from orchestrator.groups import find_text, substitute

CODE = '''export default function App() {
  return (
    <div className="flow-root">
      <span className="text-[14px] text-[#000000]">Overview</span>
      <span className="text-[14px] text-[#626262] ml-[6px]">Analytics</span>
      <p className="text-[16px] text-[#000000]">Overview</p>
      <p className="text-[14px] text-[#737373]">View your key metrics and{" "}<br className="md:hidden" />recent project activity.</p>
      <p className="text-[14px] text-[#737373]">You have 12 active projects &amp; 3 pending tasks.</p>
    </div>
  );
}
'''


def test_find_text_sees_through_responsive_breaks_and_entities():
    assert len(find_text(CODE, "Overview")) == 2
    assert len(find_text(CODE, "View your key metrics and recent project activity.")) == 1
    assert len(find_text(CODE, "You have 12 active projects & 3 pending tasks.")) == 1
    assert find_text(CODE, "Nope") == []


def test_substitute_replaces_the_nth_occurrence_only():
    out = substitute(CODE, "Overview", '{["Overview", "Analytics"][tab]}', nth=1)
    assert '<span className="text-[14px] text-[#000000]">Overview</span>' in out          # the tab label stays
    assert '<p className="text-[16px] text-[#000000]">{["Overview", "Analytics"][tab]}</p>' in out


def test_substitute_replaces_the_whole_inner_content_with_breaks():
    out = substitute(CODE, "View your key metrics and recent project activity.", "{SLOT[tab]}")
    assert '<p className="text-[14px] text-[#737373]">{SLOT[tab]}</p>' in out and "<br" not in out


def test_substitute_unknown_or_out_of_range_raises():
    with pytest.raises(KeyError):
        substitute(CODE, "Nope", "{x}")
    with pytest.raises(KeyError):
        substitute(CODE, "Overview", "{x}", nth=2)


SWAP_PAGE = '''export default function App() {
  return (
    <div className="flow-root">
      <button type="button" data-trigger="tabs0" className="px-[6px]"><span className="text-[14px]">Overview</span></button>
      <button type="button" data-trigger="tabs1" className="px-[6px]"><span className="text-[14px]">Analytics</span></button>
      <p className="text-[16px] text-[#000000]">Overview</p>
      <p className="text-[14px] text-[#737373]">View your key metrics and{" "}<br className="md:hidden" />recent project activity.</p>
    </div>
  );
}
'''
SWAP_PLAN = {"kind": "tabs", "initial": 0,
             "slots": [{"text": "Overview", "nth": 1}, {"text": "View your key metrics and recent project activity."}],
             "members": [{"trigger": "Overview", "slots": ["Overview", "View your key metrics and recent project activity."]},
                         {"trigger": "Analytics", "slots": ["Analytics", 'Track performance & "engagement".']}]}


def test_compile_swap_wires_selection_slots_and_aria():
    from orchestrator.groups import compile_swap
    code = compile_swap(SWAP_PAGE, SWAP_PLAN, "tabs")
    assert code.startswith('import { useState } from "react";')
    assert "const [tabsSel, setTabsSel] = useState(0);" in code
    assert 'const TABS_SLOT0 = ["Overview", "Analytics"];' in code
    assert '"Track performance & \\"engagement\\"."' in code                     # JS-escaped
    t1 = code[code.index('data-trigger="tabs1"'):code.index("<span", code.index('data-trigger="tabs1"'))]   # opening tag
    assert "onClick={() => setTabsSel(1)}" in t1 and 'role="tab"' in t1 and "aria-selected={tabsSel === 1}" in t1
    assert '<p className="text-[16px] text-[#000000]">{TABS_SLOT0[tabsSel]}</p>' in code
    assert "{TABS_SLOT1[tabsSel]}" in code and "<br" not in code
    assert '<span className="text-[14px]">Overview</span>' in code                   # the tab label is not a slot


def test_compile_swap_toggle_uses_aria_pressed():
    from orchestrator.groups import compile_swap
    page = SWAP_PAGE.replace("tabs0", "billing0").replace("tabs1", "billing1")
    code = compile_swap(page, dict(SWAP_PLAN, kind="toggle"), "billing")
    t0 = code[code.index('data-trigger="billing0"'):code.index("<span", code.index('data-trigger="billing0"'))]
    assert "aria-pressed={billingSel === 0}" in t0 and 'role="tab"' not in t0


def test_compile_swap_rejects_bad_plans():
    from orchestrator.groups import PlanError, compile_swap
    bad = dict(SWAP_PLAN, members=[SWAP_PLAN["members"][0], {"trigger": "Analytics", "slots": ["only one"]}])
    with pytest.raises(PlanError, match="slots"):
        compile_swap(SWAP_PAGE, bad, "tabs")
    with pytest.raises(PlanError, match="trigger"):
        compile_swap(SWAP_PAGE.replace('data-trigger="tabs1"', ""), SWAP_PLAN, "tabs")
    with pytest.raises(PlanError, match="not in the page"):
        compile_swap(SWAP_PAGE, dict(SWAP_PLAN, slots=[{"text": "Nope"}, SWAP_PLAN["slots"][1]]), "tabs")
