"""Gate B baseline (council, Oct 2): a deterministic template that fills the writer's sections from the measured facts
— overlay / drawer (fixed layers per breakpoint) and inline (in-flow, measured gap). Nemotron is measured against it,
not against a straw man. Written before the implementation (TDD)."""
import re

import pytest

from orchestrator.fallback import template_sections
from orchestrator.writer import assemble, parse_sections
from test_interact_loop import DEV, inputs
from test_writer import BASE, INLINE_BASE, INLINE_PANEL, PANEL, lint


def facts(kind, panel, **kw):
    f = {"trigger_tag": "<button>", "panel_component": "MenuPanel", "kind": kind, "panel": panel,
         "background": {bp: "#0b0b0b" for bp in panel}, "backdrop": {}, "trigger_open": {}, "hidden_at": [],
         "trigger_open_component": None, "inline_gap": {}}
    f.update(kw)
    return f


def test_overlay_and_drawer_layers_per_breakpoint():
    f = facts({"mobile": "overlay", "tablet": "drawer"}, {"mobile": [0, 100, 390, 744], "tablet": [368, 100, 400, 924]},
              backdrop={"tablet": {"color": "#000000", "opacity": 0.9, "box": [0, 101, 768, 923]}},
              hidden_at=["desktop"], trigger_open_component="MenuTriggerOpen")
    s = template_sections(f, "menu")
    assert set(s) >= {"HOOKS", "TRIGGER_PROPS", "TRIGGER_OPEN", "OVERLAY"} and not s.get("INLINE")
    assert "Escape" in s["HOOKS"] and 'aria-controls="menu-panel"' in s["TRIGGER_PROPS"]
    assert s["TRIGGER_OPEN"] == "<MenuTriggerOpen />"
    o = s["OVERLAY"]
    assert "left-[0px] top-[100px] w-[390px] h-[744px]" in o
    assert "md:left-[368px] md:top-[100px] md:w-[400px] md:h-[924px]" in o
    assert "xl:hidden" in o                                              # no panel in the desktop design
    assert "bg-[#000000]/[0.9]" in o and "hidden md:block xl:hidden" in o  # backdrop only at tablet, valid syntax
    assert o.index("bg-[#000000]/[0.9]") < o.index('id="menu-panel"')    # behind the panel
    code = assemble(BASE, PANEL, parse_sections("\n".join(f"### {k}\n{v}" for k, v in s.items())), "menu")
    assert lint(code)["ok"], lint(code)


def test_inline_in_flow_with_measured_gap():
    f = facts({bp: "inline" for bp in ("mobile", "tablet", "desktop")},
              {"mobile": [20, 438, 262, 43], "tablet": [164, 399, 262, 43], "desktop": [420, 415, 262, 43]},
              inline_gap={"mobile": 15, "tablet": 15, "desktop": 15}, panel_component="HelpPanel")
    s = template_sections(f, "help")
    assert not s.get("OVERLAY") and 'id="help-panel"' in s["INLINE"]
    assert "mt-[15px]" in s["INLINE"] and "fixed" not in s["INLINE"] and "<HelpPanel />" in s["INLINE"]
    code = assemble(INLINE_BASE, INLINE_PANEL, parse_sections("\n".join(f"### {k}\n{v}" for k, v in s.items())), "help")
    assert lint(code)["ok"], lint(code)


def test_inline_gap_differs_per_breakpoint_and_hidden_where_absent():
    f = facts({"mobile": "inline", "tablet": "inline"}, {"mobile": [20, 438, 262, 43], "tablet": [164, 399, 262, 43]},
              inline_gap={"mobile": 15, "tablet": 9}, hidden_at=["desktop"], panel_component="HelpPanel")
    i = template_sections(f, "help")["INLINE"]
    assert "mt-[15px] md:mt-[9px]" in i and "xl:hidden" in i


def test_negative_gap_never_gives_a_negative_margin_class():
    f = facts({"mobile": "inline"}, {"mobile": [20, 400, 262, 43]}, inline_gap={"mobile": -3}, panel_component="P")
    assert not re.search(r"(?<![\w-])-?mt-\[-", template_sections(f, "help")["INLINE"])


@pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_template_passes_lambda_menu_locally(tmp_path):
    """The council's finding, kept as a regression: the template passes lambda's generated tests (oracle facts)."""
    from orchestrator.interact_loop import local_runner, run_template
    base, states, trig, targets = inputs()
    res = run_template(base, states, trig, targets, "menu", local_runner, out=tmp_path)
    assert res["pass"], res["attempts"][0]["verdict"]["failures"]
    assert min(res["attempts"][0]["verdict"]["state_scores"].values()) >= 75


def test_blurred_backdrop_gets_a_backdrop_blur():
    f = facts({"mobile": "drawer"}, {"mobile": [99, 0, 291, 844]},
              backdrop={"mobile": {"color": "#201e1d", "opacity": 0.12, "blur": 4, "box": [0, 0, 99, 844]}})
    o = template_sections(f, "menu")["OVERLAY"]
    assert "bg-[#201e1d]/[0.12]" in o and "backdrop-blur-[4px]" in o


def test_writer_facts_mention_the_blur():
    from orchestrator.writer import _facts_text
    f = facts({"mobile": "drawer"}, {"mobile": [99, 0, 291, 844]},
              backdrop={"mobile": {"color": "#201e1d", "opacity": 0.12, "blur": 4, "box": [0, 0, 99, 844]}})
    assert "blur 4 px" in _facts_text(f, "menu")


def test_covered_trigger_is_raised_above_the_panel_not_duplicated():
    """lennysjobs: the drawer covers the trigger. The page's trigger is raised above any panel (it stays clickable
    wherever the static layout put it — perception placed it at x 190, not the design's 349); no second control."""
    from orchestrator.interact_loop import raise_trigger
    f = facts({"mobile": "drawer"}, {"mobile": [99, 0, 291, 844]}, trigger_open_component="MenuTriggerOpen",
              trigger_box={"mobile": [349, 10, 36, 36]}, trigger_covered={"mobile": True})
    s = template_sections(f, "menu")
    assert "<button" not in s["OVERLAY"] and s["TRIGGER_OPEN"] == "<MenuTriggerOpen />"
    page = raise_trigger(BASE, "menu")
    tag = page[page.index("<button"):page.index(">", page.index("<button"))]
    assert "relative" in tag and "z-[1000]" in tag and raise_trigger(page, "menu") == page     # idempotent
    code = assemble(page, PANEL, parse_sections("\n".join(f"### {k}\n{v}" for k, v in s.items())), "menu")
    assert code.count("relative") == 1 and lint(code)["ok"]


@pytest.mark.skipif(not (DEV / "mobile.menu.oracle.json").exists(), reason="dev state capture not present")
def test_facts_say_whether_the_panel_covers_the_trigger():
    import json
    from orchestrator.fluid import compile_fluid
    from orchestrator.interact_loop import build_facts
    from orchestrator.panel import compile_panel
    ROOT = DEV.parents[1]
    L = ROOT / "benchmarks-dev" / "lennysjobs-lx"
    for d, spec, expect in ((DEV, "lambda-lx.oracle.json", {"mobile": False, "tablet": False}),
                            (L, "lennysjobs-lx.json", {"mobile": True})):
        base = json.loads((ROOT / "out" / "specs" / spec).read_text())
        trig = {bp: v["box"] for bp, v in json.loads((d / "meta-menu.json").read_text())["trigger"].items()}
        stp = ROOT / "out" / "specs" / (spec.replace(".oracle", "").replace(".json", ".menu.json"))
        if "oracle" in spec:
            from oracle_spec import frame
            states = {bp: frame(d.name, bp, state="menu") for bp in trig}
        else:
            states = json.loads(stp.read_text())["breakpoints"]
        page = compile_fluid(base, triggers={"menu": trig}, auto_menu=False)
        panel = compile_panel(base, states, name="MenuPanel", triggers=trig,
                              images={bp: (d / f"{bp}.png", d / f"{bp}.menu.png") for bp in trig})
        f = build_facts(page, panel, "menu", states, trig)
        assert f["trigger_covered"] == expect and f["trigger_box"] == trig, d.name
