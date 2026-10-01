"""Structural tool calls: deterministic, safe (no text insertion), parse-preserving."""
from orchestrator import jsx_edit

SRC = '''export default function App(){ return (<main className="p-4">
  <h1 className="text-2xl">Title</h1>
  <a className="text-sm">FAQ</a><a className="text-sm">Help</a><a className="text-sm">Privacy</a>
  <p className="mt-2">Body</p>
</main>) }'''


def tagged():
    return jsx_edit.tag(SRC)[0]


def test_wrap_siblings_and_grid():
    code = tagged()
    new, n, sk = jsx_edit.structural(code, [{"op": "wrap", "ids": [2, 3, 4], "classes": "md:grid md:grid-cols-2"}])
    assert n == 1 and not sk and '<div className="md:grid md:grid-cols-2"><a data-pc="2"' in new


def test_insert_rejects_text_and_accepts_rule():
    code = tagged()
    _, n, sk = jsx_edit.structural(code, [{"op": "insert", "after": 1, "jsx": "<p>Fake design text</p>"}])
    assert n == 0 and "text-free" in sk[0]["why"]
    new, n, sk = jsx_edit.structural(code, [{"op": "insert", "after": 1, "jsx": '<div className="h-px w-full bg-[#1a1a1a]" />'}])
    assert n == 1 and 'bg-[#1a1a1a]' in new


def test_move_remove_set_tag_set_layout():
    code = tagged()
    new, n, sk = jsx_edit.structural(code, [{"op": "move", "id": 5, "before": 2}, {"op": "remove", "id": 4},
                                            {"op": "set_tag", "id": 1, "tag": "h2"}, {"op": "set_layout", "id": 0, "bp": "tablet", "layout": "grid", "cols": 3, "gap_x": 24}])
    assert n == 4, sk
    assert new.index("Body") < new.index("FAQ") and "Privacy" not in new and "<h2" in new and "md:grid" in new and "md:gap-x-[24px]" in new


def test_bad_ops_are_skipped_not_fatal():
    code = tagged()
    new, n, sk = jsx_edit.structural(code, [{"op": "wrap", "ids": [1, 99]}, {"op": "explode"}, {"op": "remove", "id": 5}])
    assert n == 1 and len(sk) == 2 and "Body" not in new
