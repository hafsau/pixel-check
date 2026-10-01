"""Breakpoint-scoped class edits: a change aimed at one breakpoint must not alter the others."""
import pytest

from orchestrator import jsx_edit


def classes(code, pc):
    import re
    m = re.search(rf'data-pc="{pc}" className="([^"]*)"', code)
    return m.group(1).split()


def eff(cls, bp, prop):
    chain = {"mobile": [""], "tablet": ["md:", "sm:", ""], "desktop": ["xl:", "lg:", "md:", "sm:", ""]}[bp]
    for pre in chain:
        for c in cls:
            p = c[: c.index(":") + 1] if ":" in c else ""
            if p == pre and c[len(p):].lstrip("!").lstrip("-").startswith(prop + "-"):
                return c[len(p):]
    return None


def edit(cls, bp, add):
    code, _ = jsx_edit.tag(f'export default function App(){{ return <div className="{cls}">x</div> }}')
    new, n, skipped = jsx_edit.apply(code, [{"id": 0, "bp": bp, "add": add, "remove": ""}])
    return classes(new, 0), skipped


@pytest.mark.parametrize("start", ["mt-4", "mt-4 md:mt-8", "mt-4 xl:mt-12", "mt-4 md:mt-8 xl:mt-12", "", "sm:mt-6"])
@pytest.mark.parametrize("bp", ["mobile", "tablet", "desktop"])
def test_scoped_edit_changes_only_its_breakpoint(start, bp):
    before = start.split()
    after, _ = edit(start, bp, "mt-[40px]")
    for level in ("mobile", "tablet", "desktop"):
        old, new = eff(before, level, "mt"), eff(after, level, "mt")
        if level == bp:
            assert new == "mt-[40px]", (level, before, after)
        else:
            # unchanged, or explicitly pinned to the default when there was no value before
            assert new == old or (old is None and new == "mt-0"), (level, before, after)


def test_model_supplied_prefix_is_normalised():
    after, _ = edit("mt-4", "tablet", "xl:mt-[40px]")    # model used the wrong prefix; bp wins
    assert eff(after, "tablet", "mt") == "mt-[40px]" and eff(after, "desktop", "mt") == "mt-4" and eff(after, "mobile", "mt") == "mt-4"


@pytest.mark.parametrize("start,add,prop", [("", "text-[32px]", "text"), ("text-sm", "text-[32px]", "text"), ("space-y-4", "space-y-[8px]", "space-y")])
def test_pins_for_text_and_spacing(start, add, prop):
    after, skipped = edit(start, "tablet", add)
    assert not [s for s in skipped if "could not pin" in s["why"]], skipped
    assert any(c.startswith("xl:") for c in after), after   # desktop pinned


def edit_rm(cls, bp, add, remove):
    code, _ = jsx_edit.tag(f'export default function App(){{ return <div className="{cls}">x</div> }}')
    new, n, skipped = jsx_edit.apply(code, [{"id": 0, "bp": bp, "add": add, "remove": remove}])
    return classes(new, 0)


@pytest.mark.parametrize("bp", ["tablet", "desktop"])
@pytest.mark.parametrize("start,add,remove,prop", [
    ("w-full", "w-[350px]", "w-full", "w"),                      # live-run leak: unprefixed remove
    ("h-[13px] w-full", "h-[24px]", "h-[13px]", "h"),
    ("rounded-none", "rounded-md", "rounded-none", "rounded"),
    ("text-[#f1f1f1] xl:text-[#efefef]", "text-white", "text-[#f1f1f1]", "text"),
])
def test_remove_cannot_leak_into_other_breakpoints(bp, start, add, remove, prop):
    before, after = start.split(), edit_rm(start, bp, add, remove)
    for level in ("mobile", "tablet", "desktop"):
        if level != bp:
            assert eff(after, level, prop) == eff(before, level, prop), (level, before, after)


def edit_delta(cls, bp, delta):
    code, _ = jsx_edit.tag(f'export default function App(){{ return <div className="{cls}">x</div> }}')
    new, n, skipped = jsx_edit.apply(code, [{"id": 0, "bp": bp, "delta": delta}])
    return classes(new, 0)


@pytest.mark.parametrize("start,bp,delta,expect", [
    ("mt-4", "tablet", {"mt": 14}, "mt-[30px]"),            # 16 + 14
    ("mt-4 md:mt-[52px]", "tablet", {"mt": -10}, "mt-[42px]"),
    ("", "desktop", {"mt": 8}, "mt-[8px]"),
    ("mt-2", "mobile", {"mt": -20}, "-mt-[12px]"),
    ("-mt-2 xl:mt-px", "desktop", {"mt": 3}, "mt-[4px]"),
])
def test_delta_reads_current_value(start, bp, delta, expect):
    before, after = start.split(), edit_delta(start, bp, delta)
    assert eff(after, bp, "mt") == expect, after
    for level in ("mobile", "tablet", "desktop"):
        if level != bp:
            assert eff(after, level, "mt") == eff(before, level, "mt") or (eff(before, level, "mt") is None and eff(after, level, "mt") == "mt-0"), (level, after)


def test_important_classes_replace_same_property():
    after, _ = edit("mt-4 md:mt-8", "tablet", "!mt-[40px]")
    # base keeps its value (promoted to important so the important md: value can't leak below it); desktop pinned
    assert "md:!mt-[40px]" in after and "md:mt-8" not in after and eff(after, "mobile", "mt").lstrip("!") == "mt-4", after
    assert eff(after, "desktop", "mt").lstrip("!") == "mt-8", after


def test_multiple_edits_same_element_compose():
    code, _ = jsx_edit.tag('export default function App(){ return <div className="mt-4 text-sm">x</div> }')
    new, n, skipped = jsx_edit.apply(code, [
        {"id": 0, "bp": "mobile", "add": "!-mt-[12px]"}, {"id": 0, "bp": "tablet", "add": "!-mt-[12px]"},
        {"id": 0, "bp": "desktop", "add": "!mt-[30px]"}, {"id": 0, "bp": "tablet", "add": "text-[20px]"}])
    c = classes(new, 0)
    assert not skipped, skipped
    assert eff(c, "mobile", "mt") == "!-mt-[12px]" and eff(c, "tablet", "mt") == "!-mt-[12px]" and eff(c, "desktop", "mt") == "!mt-[30px]", c
    assert eff(c, "tablet", "text") == "text-[20px]" and eff(c, "mobile", "text") == "text-sm", c


@pytest.mark.parametrize("start", ["mt-[44px]", "mt-[44px] md:mt-[20px]", "mt-[44px] xl:mt-[8px]"])
def test_important_mobile_edit_does_not_leak(start):
    before, after = start.split(), edit(start, "mobile", "!mt-[60px]")[0]
    import re
    def px(c): return int(re.search(r"\[(\d+)px\]", c).group(1)) if c and "[" in c else 0
    for level in ("tablet", "desktop"):
        # the winning class at that level must still give the old value, and be important if the base is
        winners = [c for c in after if (c.startswith({"tablet": "md:", "desktop": "xl:"}[level]) or c.startswith("md:")) ]
        assert winners, after
        assert all("!" in c for c in winners if "mt" in c), after
        assert px(eff(after, level, "mt")) == px(eff(before, level, "mt")), (level, after)


def test_explicit_pins_override_class_guesses():
    # tablet's real margin comes from a parent space-y (16px), invisible in the element's classes
    code, _ = jsx_edit.tag('export default function App(){ return <div className="space-y-4"><p>a</p><p className="text-sm">b</p></div> }')
    new, n, _ = jsx_edit.apply(code, [{"id": 2, "bp": "mobile", "add": "!mt-[30px]", "pins": {"tablet": ["!mt-[16px]"], "desktop": ["!mt-[16px]"]}}])
    c = classes(new, 2)
    assert "!mt-[30px]" in c and "md:!mt-[16px]" in c, c
