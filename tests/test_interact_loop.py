"""Stage 6 (docs/INTERACTIONS.md): write → run generated tests → revise with the failures (≤ 3 attempts).
Written before the implementation (TDD, Oct 2). Scripted writer replies; the harness runs locally."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "benchmarks-dev" / "lambda-lx"
pytestmark = pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")

GOOD = """### HOOKS
const [menuOpen, setMenuOpen] = useState(false);
useEffect(() => {
  const onKey = (e) => { if (e.key === "Escape") setMenuOpen(false); };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, []);
### TRIGGER_PROPS
onClick={() => setMenuOpen((o) => !o)} aria-expanded={menuOpen} aria-controls="menu-panel" aria-label="Toggle menu"
### TRIGGER_OPEN
<MenuTriggerOpen />
### OVERLAY
{menuOpen && (
  <>
    <div aria-hidden="true" className="hidden md:block fixed left-0 right-0 bottom-0 top-[101px] bg-[#000000]/[0.9]" />
    <div id="menu-panel" className="fixed left-0 right-0 bottom-0 top-[100px] md:left-auto md:w-[400px] bg-[#0b0b0b] overflow-y-auto">
      <MenuPanel />
    </div>
  </>
)}
"""
NO_ESCAPE = GOOD.replace("""useEffect(() => {
  const onKey = (e) => { if (e.key === "Escape") setMenuOpen(false); };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, []);
""", "")
BROKEN = GOOD.replace("{menuOpen && (", "{menuOpen && ((")


class Reply:
    def __init__(self, c):
        self.content, self.reasoning, self.usd = c, "", 0.001


class Scripted:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat(self, model, messages, **kw):
        self.calls.append(messages)
        return Reply(self.replies.pop(0) if self.replies else "no sections")


def inputs():
    sys.path.insert(0, str(ROOT / "tools"))
    from oracle_spec import frame as oracle_frame
    base = json.loads((ROOT / "out" / "specs" / "lambda-lx.oracle.json").read_text())
    meta = json.loads((DEV / "meta-menu.json").read_text())
    trig = {bp: v["box"] for bp, v in meta["trigger"].items()}
    states = {bp: oracle_frame("lambda-lx", bp, state="menu") for bp in trig}
    targets = {"base": {bp: DEV / f"{bp}.png" for bp in trig}, "states": {bp: DEV / f"{bp}.menu.png" for bp in trig},
               "base_texts": {bp: DEV / f"{bp}.text.json" for bp in trig},
               "state_texts": {bp: DEV / f"{bp}.menu.text.json" for bp in trig}}
    return base, states, trig, targets


def test_revises_after_failing_tests_and_passes(tmp_path):
    from orchestrator.interact_loop import local_runner, run_interaction
    base, states, trig, targets = inputs()
    c = Scripted([NO_ESCAPE, GOOD])
    res = run_interaction(base, states, trig, targets, "menu", c, local_runner, out=tmp_path)
    assert res["pass"] and len(res["attempts"]) == 2
    assert not res["attempts"][0]["verdict"]["pass"]
    assert any("Escape" in f for f in res["attempts"][0]["verdict"]["failures"])
    revision_prompt = c.calls[1][-1]["content"]
    assert "Escape" in revision_prompt and "FAILED" in revision_prompt
    assert "useEffect" in res["code"] and 'data-trigger="menu"' in res["code"]


def test_build_failure_is_fed_back(tmp_path):
    from orchestrator.interact_loop import local_runner, run_interaction
    base, states, trig, targets = inputs()
    c = Scripted([BROKEN, GOOD])
    res = run_interaction(base, states, trig, targets, "menu", c, local_runner, out=tmp_path)
    assert res["pass"] and len(res["attempts"]) == 2
    assert "build" in " ".join(res["attempts"][0]["verdict"]["failures"]).lower()


def test_gives_up_after_max_attempts_and_keeps_best(tmp_path):
    from orchestrator.interact_loop import local_runner, run_interaction
    base, states, trig, targets = inputs()
    c = Scripted([NO_ESCAPE, NO_ESCAPE, NO_ESCAPE])
    res = run_interaction(base, states, trig, targets, "menu", c, local_runner, out=tmp_path, max_attempts=3)
    assert not res["pass"] and len(res["attempts"]) == 3
    assert res["code"] is not None and res["best_attempt"] in (0, 1, 2)


def test_unparseable_writer_is_a_failed_attempt_not_a_crash(tmp_path):
    from orchestrator.interact_loop import local_runner, run_interaction
    base, states, trig, targets = inputs()
    c = Scripted(["nope", "nope", "nope", "nope"])
    res = run_interaction(base, states, trig, targets, "menu", c, local_runner, out=tmp_path, max_attempts=2)
    assert not res["pass"] and res["code"] is None
    assert all("format" in a["verdict"]["failures"][0] for a in res["attempts"])


def test_facts_from_compiled_page_and_panel():
    from orchestrator.interact_loop import build_facts
    from orchestrator.fluid import compile_fluid
    from orchestrator.panel import compile_panel
    base, states, trig, _ = inputs()
    page = compile_fluid(base, triggers={"menu": trig}, auto_menu=False)
    panel = compile_panel(base, states, name="MenuPanel", triggers=trig,
                          images={bp: (DEV / f"{bp}.png", DEV / f"{bp}.menu.png") for bp in trig})
    f = build_facts(page, panel, "menu", states)
    assert f["trigger_tag"].startswith("<button") and 'data-trigger="menu"' in f["trigger_tag"]
    assert f["kind"] == {"mobile": "overlay", "tablet": "drawer"} and f["hidden_at"] == ["desktop"]
    assert f["backdrop"]["tablet"]["opacity"] >= 0.8 and f["background"]["mobile"].startswith("#")
    assert f["trigger_open"]["mobile"][0]["shape"] == "x"            # read from the images (hamburger → X)
    assert f["panel_component"] == "MenuPanel"
    assert f["trigger_open_component"] == "MenuTriggerOpen" and "function MenuTriggerOpen()" in panel["jsx"]


COVERED = GOOD.replace("""    <div aria-hidden="true" className="hidden md:block fixed left-0 right-0 bottom-0 top-[101px] bg-[#000000]/[0.9]" />
    <div id="menu-panel\"""", """    <div id="menu-panel\"""").replace("""      <MenuPanel />
    </div>
  </>""", """      <MenuPanel />
    </div>
    <div aria-hidden="true" className="hidden md:block fixed left-0 right-0 bottom-0 top-[101px] bg-[#000000]/[0.9]" />
  </>""")


def test_failure_names_the_texts_that_are_not_visible(tmp_path):
    """Nemotron put the backdrop after the panel (it paints over the drawer); 'does not match' alone gave it nothing
    to fix — the failure must say which design texts are not visible in the open state."""
    from orchestrator.interact_loop import local_runner, run_interaction
    base, states, trig, targets = inputs()
    assert COVERED != GOOD
    res = run_interaction(base, states, trig, targets, "menu", Scripted([COVERED]), local_runner, out=tmp_path,
                          max_attempts=1)
    msg = " ".join(res["attempts"][0]["verdict"]["failures"])
    assert "tablet" in msg and "not visible" in msg and "AI FACTORIES" in msg


def test_revisions_use_a_higher_temperature():
    from orchestrator.writer import write_interaction

    class Rec(Scripted):
        def chat(self, model, messages, **kw):
            self.kw = kw
            return super().chat(model, messages, **kw)
    c = Rec([GOOD])
    from orchestrator.writer import parse_sections
    write_interaction(c, {"trigger_tag": "<button>", "panel_component": "MenuPanel", "kind": {}, "panel": {}}, "menu",
                      previous=parse_sections(GOOD), failures=["x"])
    assert c.kw["temperature"] >= 0.5
