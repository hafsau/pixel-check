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
            if p == pre and c[len(p):].startswith(prop + "-"):
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
