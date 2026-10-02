"""Stage 4 (docs/INTERACTIONS.md): the interaction writer's output format and its deterministic assembly into the
compiled page. Written before the implementation (TDD, Oct 2). The model writes code in sections; parse_sections
reads them, assemble() places them (hooks in App, props on the trigger, open-state trigger look, overlay)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator.writer import WriterFormatError, assemble, parse_sections

ROOT = Path(__file__).resolve().parents[1]

BASE = '''export default function App() {
  return (
    <div className="flow-root min-h-screen w-full font-sans bg-[#0b0b0b]">
      <div className="flex flex-row w-full">
        <div aria-hidden="true" className="w-[159px] h-[37px] bg-[#d4d4d8]" />
        <button type="button" data-trigger="menu" className="w-[40px] h-[34px] shrink-0">
          <div aria-hidden="true" className="w-[24px] h-[2px] bg-[#e7e6d9]" />
        </button>
      </div>
      <p className="text-[40px] text-white">Hero</p>
    </div>
  );
}
'''
PANEL = '''function MenuPanel() {
  return (
    <div className="w-full">
      <a href="#" className="block text-white">AI FACTORIES</a>
    </div>
  );
}
'''
REPLY = '''Here is the interaction.
### HOOKS
```jsx
const [menuOpen, setMenuOpen] = useState(false);
useEffect(() => {
  const onKey = (e) => { if (e.key === "Escape") setMenuOpen(false); };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, []);
```
### TRIGGER_PROPS
onClick={() => setMenuOpen((o) => !o)} aria-expanded={menuOpen} aria-controls="menu-panel" aria-label="Toggle menu"
### TRIGGER_OPEN
<div aria-hidden="true" className="relative w-[22px] h-[22px]"><div className="absolute left-0 top-1/2 w-full h-[2px] rotate-45 bg-[#e7e6d9]" /><div className="absolute left-0 top-1/2 w-full h-[2px] -rotate-45 bg-[#e7e6d9]" /></div>
### OVERLAY
{menuOpen && (
  <div id="menu-panel" className="fixed inset-x-0 top-[100px] bottom-0 bg-[#0b0b0b] overflow-y-auto">
    <MenuPanel />
  </div>
)}
'''


def lint(code: str) -> dict:
    p = ROOT / "out" / "tmp_writer_test.jsx"
    p.parent.mkdir(exist_ok=True)
    p.write_text(code)
    return json.loads(subprocess.run(["node", "lint.mjs", str(p)], cwd=ROOT / "sandbox", capture_output=True, text=True).stdout)


def test_parse_sections_with_fences_and_prose():
    s = parse_sections(REPLY)
    assert s["HOOKS"].startswith("const [menuOpen") and "```" not in s["HOOKS"]
    assert s["TRIGGER_PROPS"].startswith("onClick=")
    assert s["TRIGGER_OPEN"].startswith("<div") and s["OVERLAY"].startswith("{menuOpen &&")


def test_parse_sections_optional_trigger_open():
    s = parse_sections(REPLY.split("### TRIGGER_OPEN")[0] + "### OVERLAY" + REPLY.split("### OVERLAY")[1])
    assert s.get("TRIGGER_OPEN", "") == ""


@pytest.mark.parametrize("missing", ["HOOKS", "TRIGGER_PROPS", "OVERLAY"])
def test_parse_sections_missing_required(missing):
    parts = REPLY.split("### ")
    bad = "### ".join(p for p in parts if not p.startswith(missing))
    with pytest.raises(WriterFormatError):
        parse_sections(bad)


def test_assemble_places_everything_and_lints():
    code = assemble(BASE, PANEL, parse_sections(REPLY), "menu")
    assert code.count("function MenuPanel()") == 1
    assert code.startswith('import { useState, useEffect } from "react";')
    app_at = code.index("export default function App() {")
    head = code[app_at:code.index("  return (", app_at)]
    assert "useState(false)" in head and "keydown" in head
    trig = code[code.index('data-trigger="menu"') - 40:code.index('data-trigger="menu"') + 400]
    assert "onClick={() => setMenuOpen" in trig and "aria-expanded={menuOpen}" in trig
    assert "{menuOpen ? (" in code and "rotate-45" in code
    assert code.index('id="menu-panel"') > code.index(">Hero<"), "overlay sits at the end of the page"
    assert code.rstrip().endswith("}")
    r = lint(code)
    assert r["ok"], r


def test_assemble_keeps_static_markup_outside_the_edits():
    code = assemble(BASE, PANEL, parse_sections(REPLY), "menu")
    for line in ['<p className="text-[40px] text-white">Hero</p>', '<div aria-hidden="true" className="w-[159px] h-[37px] bg-[#d4d4d8]" />']:
        assert line in code


def test_assemble_self_closing_trigger():
    base = BASE.replace('''<button type="button" data-trigger="menu" className="w-[40px] h-[34px] shrink-0">
          <div aria-hidden="true" className="w-[24px] h-[2px] bg-[#e7e6d9]" />
        </button>''', '<button type="button" data-trigger="menu" className="w-[40px] h-[34px] shrink-0" />')
    code = assemble(base, PANEL, parse_sections(REPLY), "menu")
    assert lint(code)["ok"]
    assert "{menuOpen ? (" in code


def test_assemble_merges_existing_react_import():
    base = 'import { useState } from "react";\n\n' + BASE
    code = assemble(base, PANEL, parse_sections(REPLY), "menu")
    assert code.count('from "react"') == 1 and "useEffect" in code.splitlines()[0]


def test_assemble_without_trigger_fails_clearly():
    with pytest.raises(WriterFormatError, match="trigger"):
        assemble(BASE.replace('data-trigger="menu"', ""), PANEL, parse_sections(REPLY), "menu")


DEV = ROOT / "benchmarks-dev" / "lambda-lx"


@pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_real_lambda_with_handwritten_sections_passes_acceptance(tmp_path):
    """The whole pipeline minus the model: compiled base + compiled panel + hand-written sections → sandbox harness
    → acceptance. Proves the plumbing before Nemotron writes anything."""
    sys.path.insert(0, str(ROOT / "tools"))
    from oracle_spec import frame as oracle_frame
    from orchestrator.acceptance import build_scenarios, evaluate
    from orchestrator.fluid import compile_fluid
    from orchestrator.panel import compile_panel
    base = json.loads((ROOT / "out" / "specs" / "lambda-lx.oracle.json").read_text())
    meta = json.loads((DEV / "meta-menu.json").read_text())
    trig = {bp: v["box"] for bp, v in meta["trigger"].items()}
    states = {bp: oracle_frame("lambda-lx", bp, state="menu") for bp in trig}
    page = compile_fluid(base, triggers={"menu": trig}, auto_menu=False)
    panel = compile_panel(base, states, name="MenuPanel", triggers=trig,
                          images={bp: (DEV / f"{bp}.png", DEV / f"{bp}.menu.png") for bp in trig})
    # mobile: full-screen overlay below the header; tablet: a drawer on the right (lambda, measured)
    m, t = panel["panel"]["mobile"], panel["panel"]["tablet"]
    pos = (f"left-0 right-0 top-[{m[1]}px] md:left-auto md:w-[{t[2]}px] md:top-[{t[1]}px]")
    reply = REPLY.replace("inset-x-0 top-[100px]", pos)
    bd = panel["backdrop"]["tablet"]   # tablet dims the page behind the drawer
    reply = reply.replace("{menuOpen && (\n", "{menuOpen && (\n  <>\n  <div aria-hidden=\"true\" className=\"hidden md:block fixed left-0 right-0 bottom-0 "
                          f"top-[{bd['box'][1]}px] bg-[{bd['color']}]/[{bd['opacity']}]\" />\n", 1)
    reply = reply.replace("  </div>\n)}", "  </div>\n  </>\n)}", 1)
    code = assemble(page, panel["jsx"], parse_sections(reply), "menu")
    app = tmp_path / "App.jsx"
    app.write_text(code)
    scen = tmp_path / "scenarios.json"
    scen.write_text(json.dumps(build_scenarios(list(trig), "menu")))
    subprocess.run(["node", "render.mjs", "--interact", str(scen), "--in", str(app), "--out", str(tmp_path)],
                   cwd=ROOT / "sandbox", capture_output=True, timeout=180)
    targets = {"base": {bp: DEV / f"{bp}.png" for bp in trig}, "states": {bp: DEV / f"{bp}.menu.png" for bp in trig},
               "base_texts": {bp: DEV / f"{bp}.text.json" for bp in trig},
               "state_texts": {bp: DEV / f"{bp}.menu.text.json" for bp in trig}}
    v = evaluate(tmp_path, targets, "menu")
    assert v["pass"], v
    assert v["state_scores"]["mobile"] >= 80


# ---- the model call (fake client: records prompts, returns canned replies) ----

class FakeReply:
    def __init__(self, content):
        self.content, self.reasoning, self.usd = content, "", 0.0


class FakeClient:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat(self, model, messages, **kw):
        self.calls.append({"model": model, "messages": messages, **kw})
        return FakeReply(self.replies.pop(0))


FACTS = {"trigger_tag": '<button type="button" data-trigger="menu" className="w-[40px] h-[34px]">',
         "panel_component": "MenuPanel", "kind": {"mobile": "overlay", "tablet": "drawer"},
         "panel": {"mobile": [0, 100, 390, 744], "tablet": [368, 100, 400, 924]},
         "background": {"mobile": "#0b0b0b", "tablet": "#0b0b0b"},
         "backdrop": {"mobile": None, "tablet": {"color": "#000000", "opacity": 0.9, "box": [0, 101, 768, 923]}},
         "trigger_open": {"mobile": [{"box": [10, 5, 22, 22], "fill": "#e7e6d9"}]},
         "hidden_at": ["desktop"]}


def test_writer_prompt_carries_the_measured_facts():
    from orchestrator.writer import write_interaction
    c = FakeClient([REPLY])
    sections, _ = write_interaction(c, FACTS, "menu")
    prompt = c.calls[0]["messages"][-1]["content"]
    for needle in ['data-trigger="menu"', "MenuPanel", "overlay", "drawer", "[368, 100, 400, 924]", "0.9", "desktop",
                   "#0b0b0b", "[10, 5, 22, 22]"]:
        assert needle in prompt, needle
    assert sections["HOOKS"].startswith("const [menuOpen")
    assert "nemotron" in c.calls[0]["model"].lower()


def test_writer_prompt_names_per_breakpoint_components():
    from orchestrator.writer import write_interaction
    c = FakeClient([REPLY])
    write_interaction(c, dict(FACTS, panel_component={"mobile": "MenuPanelMobile", "tablet": "MenuPanelTablet"}), "menu")
    prompt = c.calls[0]["messages"][-1]["content"]
    assert "mobile: <MenuPanelMobile />" in prompt and "tablet: <MenuPanelTablet />" in prompt


def test_writer_retries_once_on_malformed_reply():
    from orchestrator.writer import write_interaction
    c = FakeClient(["sorry, here is some prose without sections", REPLY])
    sections, _ = write_interaction(c, FACTS, "menu")
    assert len(c.calls) == 2 and "### HOOKS" in c.calls[1]["messages"][-1]["content"]
    assert sections["OVERLAY"]


def test_writer_gives_up_after_two_malformed_replies():
    from orchestrator.writer import write_interaction
    c = FakeClient(["nope", "still nope"])
    with pytest.raises(WriterFormatError):
        write_interaction(c, FACTS, "menu")


def test_writer_revision_includes_failures_and_previous_code():
    from orchestrator.writer import write_interaction
    c = FakeClient([REPLY])
    prev = parse_sections(REPLY)
    write_interaction(c, FACTS, "menu", previous=prev, failures=["tablet: pressing Escape does not close it"])
    prompt = c.calls[0]["messages"][-1]["content"]
    assert "pressing Escape does not close it" in prompt and "setMenuOpen" in prompt


def test_trigger_becomes_positioning_context_for_its_open_look():
    """Nemotron draws the X with absolute bars; without `relative` on the trigger they land at the page's top-left."""
    code = assemble(BASE, PANEL, parse_sections(REPLY), "menu")
    tag = code[code.rindex("<button", 0, code.index('data-trigger="menu"')):code.index(">", code.index('data-trigger="menu"'))]
    cls = tag.split('className="')[1].split('"')[0].split()
    assert "relative" in cls


def test_no_open_look_leaves_trigger_classes_alone():
    reply = REPLY.split("### TRIGGER_OPEN")[0] + "### OVERLAY" + REPLY.split("### OVERLAY")[1]
    code = assemble(BASE, PANEL, parse_sections(reply), "menu")
    tag = code[code.rindex("<button", 0, code.index('data-trigger="menu"')):code.index(">", code.index('data-trigger="menu"'))]
    assert " relative" not in tag


def test_revisions_do_not_reason_by_default():
    """Measured Oct 2: thinking=low on revisions cost 3-4x, 2/4 replies came back without the sections and one used
    banned JS width detection — no gain. Default off; configurable (config.WRITER_REVISION_THINKING)."""
    from orchestrator.writer import write_interaction
    c = FakeClient([REPLY, REPLY])
    write_interaction(c, FACTS, "menu")
    write_interaction(c, FACTS, "menu", previous=parse_sections(REPLY), failures=["x"])
    assert c.calls[0]["thinking"] == "off" and c.calls[1]["thinking"] == "off"


def test_prompt_offers_compiled_trigger_look_component():
    from orchestrator.writer import write_interaction
    c = FakeClient([REPLY])
    write_interaction(c, dict(FACTS, trigger_open_component="MenuTriggerOpen"), "menu")
    prompt = c.calls[0]["messages"][-1]["content"]
    assert "<MenuTriggerOpen />" in prompt


# Gate B: inline interactions (a disclosure / accordion) — the panel is mounted in the page flow right after the
# trigger's row, so the content below moves down by itself (netflix "Get help")
INLINE_BASE = '''export default function App() {
  return (
    <div className="flow-root min-h-screen w-full font-sans bg-[#000000]">
      <div data-seg="S5" className="flow-root w-full mt-[48px]">
        <div className="w-full pl-[20px]">
          <div className="flex flex-row flex-wrap w-full">
            <button type="button" data-trigger="help" className="flex w-[83px] h-[20px]">
              <span className="text-[16px] text-[#ffffff]">Get help</span>
            </button>
          </div>
        </div>
      </div>
      <div data-seg="S6" className="flow-root w-full mt-[38px]">
        <p className="text-[13px] text-[#808080]">This page is protected</p>
      </div>
    </div>
  );
}
'''
INLINE_PANEL = '''function HelpPanel({ className = "" }) {
  return (
    <div className={`w-full ${className}`}>
      <a href="#" className="text-[14px] text-[#ffffff] underline">Forgot email?</a>
    </div>
  );
}
'''
INLINE_REPLY = '''### HOOKS
const [helpOpen, setHelpOpen] = useState(false);
### TRIGGER_PROPS
onClick={() => setHelpOpen((o) => !o)} aria-expanded={helpOpen} aria-controls="help-panel"
### TRIGGER_OPEN
### INLINE
{helpOpen && (<div id="help-panel" className="mt-[15px]"><HelpPanel /></div>)}
'''


def test_parse_sections_inline_without_overlay():
    s = parse_sections(INLINE_REPLY)
    assert s["INLINE"].startswith("{helpOpen &&") and not s.get("OVERLAY")


def test_parse_sections_needs_overlay_or_inline():
    with pytest.raises(WriterFormatError, match="OVERLAY or INLINE"):
        parse_sections(INLINE_REPLY.split("### INLINE")[0])


def test_assemble_inline_goes_right_after_the_triggers_row():
    code = assemble(INLINE_BASE, INLINE_PANEL, parse_sections(INLINE_REPLY), "help")
    i_row_end = code.index("</div>", code.index("</button>"))           # the trigger's row closes here
    i_panel = code.index('id="help-panel"')
    assert i_row_end < i_panel < code.index('data-seg="S6"')            # inside S5's container, before the next band
    between = code[i_row_end + len("</div>"):i_panel]
    assert "</div>" not in between                                       # not after the container / band closed
    assert code.count('id="help-panel"') == 1 and lint(code)["ok"], lint(code)


def test_assemble_inline_and_overlay_together():
    reply = INLINE_REPLY + '### OVERLAY\n{helpOpen && <div aria-hidden="true" className="fixed inset-0 bg-[#000000]/50" />}\n'
    code = assemble(INLINE_BASE, INLINE_PANEL, parse_sections(reply), "help")
    assert code.index('id="help-panel"') < code.index('data-seg="S6"') < code.index("fixed inset-0")
    assert lint(code)["ok"]


def test_prompt_explains_inline_kind_with_the_measured_gap():
    from orchestrator.writer import WRITER_SYSTEM, _facts_text
    f = {"trigger_tag": '<button type="button" data-trigger="help">', "panel_component": "HelpPanel",
         "kind": {"mobile": "inline"}, "panel": {"mobile": [20, 438, 262, 43]}, "background": {"mobile": "#000000"},
         "inline_gap": {"mobile": 15}, "hidden_at": []}
    t = _facts_text(f, "help")
    assert "kind inline" in t and "gap below the trigger's row 15 px" in t
    assert "### INLINE" in WRITER_SYSTEM and "inline" in WRITER_SYSTEM.lower()


def test_assemble_inline_when_the_trigger_sits_directly_in_the_root():
    base = '''export default function App() {
  return (
    <div className="flow-root min-h-screen w-full">
      <button type="button" data-trigger="help" className="w-[83px] h-[20px]">Get help</button>
      <p className="text-[13px]">Below</p>
    </div>
  );
}
'''
    code = assemble(base, INLINE_PANEL, parse_sections(INLINE_REPLY), "help")
    assert code.index("</button>") < code.index('id="help-panel"') < code.index(">Below<") or \
        code.index(">Below<") < code.index('id="help-panel"') < code.rindex("</div>")
    assert lint(code)["ok"], lint(code)


def test_prompt_tells_the_writer_when_the_panel_covers_the_trigger():
    from orchestrator.writer import WRITER_SYSTEM, _facts_text
    f = {"trigger_tag": "<button>", "panel_component": "MenuPanel", "kind": {"mobile": "drawer"},
         "panel": {"mobile": [99, 0, 291, 844]}, "background": {"mobile": "#ffffff"}, "hidden_at": [],
         "trigger_box": {"mobile": [349, 10, 36, 36]}, "trigger_covered": {"mobile": True}}
    t = _facts_text(f, "menu")
    assert "the open panel covers the trigger (box [349, 10, 36, 36])" in t
    assert "covers the trigger" in WRITER_SYSTEM and "z-[1000]" in WRITER_SYSTEM


@pytest.mark.parametrize("filler", ["(empty)", "empty", "(none)", "None", "N/A", "-", "(leave empty)", "```\n```"])
def test_placeholder_section_bodies_are_empty(filler):
    """Nemotron wrote '### INLINE\\n(empty)' (copying the prompt's 'or empty'): the literal text was mounted in the
    page and showed before any click (lennysjobs, 3 attempts)."""
    s = parse_sections(REPLY + f"\n### INLINE\n{filler}\n")
    assert s.get("INLINE", "") == ""
    s2 = parse_sections(REPLY.replace("### TRIGGER_OPEN\n", f"### TRIGGER_OPEN\n{filler}\n### IGNORE\n").split("### IGNORE")[0]
                        + "### OVERLAY" + REPLY.split("### OVERLAY")[1])
    assert s2.get("TRIGGER_OPEN", "") == ""
