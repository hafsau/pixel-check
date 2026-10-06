"""Phase 2 real images (owned sites): the scored code keeps grey blocks (exactly as the capture showed the images);
the delivered code swaps only grey blocks that sit where one of the page's own images sat, at every size it shows,
for <img src="/assets/<sha256>.<ext>">. to_scoring() undoes the swap byte for byte — the pipeline refuses to
deliver images unless it does."""
from orchestrator import assets as A

H1, H2, H3 = "a" * 64, "b" * 64, "c" * 64

CODE = """export default function App() {
  return (
    <div data-pc="0" className="flow-root min-h-screen w-full">
      <div data-pc="1" aria-hidden="true" className="w-[200px] max-w-full h-[200px] bg-[#d4d4d8] rounded-[16px] shrink-0 mt-[20px]" />
      <div data-pc="2" aria-hidden="true" className="hidden md:block w-[16px] max-w-full h-[16px] bg-[#d4d4d8] shrink-0" />
      <div data-pc="3" aria-hidden="true" className="w-[300px] h-[40px] bg-[#d4d4d8]" />
      <div data-pc="4" aria-hidden="true" className="w-[300px] h-[1px] bg-[#e5e5e5]" />
      <p data-pc="5" className="text-[16px]">Hello</p>
    </div>
  );
}
"""


def node(pc, box, v=True):
    return {"pc": str(pc), "v": v, "b": box}


NODES = {
    "mobile": [node(0, [0, 0, 390, 844]), node(1, [95, 246, 200, 200]), node(2, [0, 0, 0, 0], v=False),
               node(3, [10, 600, 300, 40]), node(4, [0, 700, 300, 1])],
    "tablet": [node(1, [284, 300, 200, 200]), node(2, [500, 40, 16, 16]), node(3, [10, 700, 300, 40])],
    "desktop": [node(1, [540, 260, 200, 200]), node(2, [900, 40, 16, 16]), node(3, [10, 700, 300, 40])],
}

MANIFEST = {"assets": [
    {"hash": H1, "ext": "png", "kind": "img", "bytes": 50000, "alt": "Portrait of Hafsa",
     "boxes": {"mobile": [[95, 246, 200, 200]], "tablet": [[286, 302, 198, 198]], "desktop": [[540, 258, 200, 200]]}},
    {"hash": H2, "ext": "svg", "kind": "svg", "bytes": 300, "alt": "",
     "boxes": {"tablet": [[502, 42, 16, 16]], "desktop": [[903, 38, 16, 16]]}},
    {"hash": H3, "ext": "jpg", "kind": "img", "bytes": 9000, "alt": "",
     "boxes": {"mobile": [[10, 600, 300, 40]]}},        # only at mobile; block 3 also shows at tablet / desktop
]}


def test_matching_blocks_become_images_with_the_same_classes():
    out, used = A.attach(CODE, NODES, MANIFEST)
    assert sorted(used) == ["1", "2"]
    assert f'<img data-pc="1" src="/assets/{H1}.png" alt="Portrait of Hafsa"' in out
    assert 'className="w-[200px] max-w-full h-[200px] bg-[#d4d4d8] rounded-[16px] shrink-0 mt-[20px] block object-cover"' in out
    assert f'<img data-pc="2" src="/assets/{H2}.svg" alt="" aria-hidden="true"' in out


def test_a_block_matched_at_only_some_of_its_sizes_stays_grey():
    out, used = A.attach(CODE, NODES, MANIFEST)
    assert "3" not in used
    assert '<div data-pc="3" aria-hidden="true" className="w-[300px] h-[40px] bg-[#d4d4d8]" />' in out


def test_non_grey_blocks_and_text_are_untouched():
    out, _ = A.attach(CODE, NODES, MANIFEST)
    assert '<div data-pc="4" aria-hidden="true" className="w-[300px] h-[1px] bg-[#e5e5e5]" />' in out
    assert '<p data-pc="5" className="text-[16px]">Hello</p>' in out


def test_to_scoring_restores_the_scored_code_exactly():
    out, _ = A.attach(CODE, NODES, MANIFEST)
    assert out != CODE
    assert A.to_scoring(out) == CODE


def test_no_manifest_or_no_match_changes_nothing():
    assert A.attach(CODE, NODES, {"assets": []}) == (CODE, [])
    assert A.attach(CODE, NODES, None) == (CODE, [])
    far = {"assets": [dict(MANIFEST["assets"][0], boxes={"mobile": [[0, 0, 50, 50]]})]}
    assert A.attach(CODE, NODES, far)[1] == []


def test_responsive_sources_use_the_largest_file():
    m = {"assets": [
        {"hash": H1, "ext": "jpg", "kind": "img", "bytes": 20000, "alt": "",
         "boxes": {"mobile": [[95, 246, 200, 200]]}},
        {"hash": H3, "ext": "jpg", "kind": "img", "bytes": 90000, "alt": "",
         "boxes": {"tablet": [[284, 300, 200, 200]], "desktop": [[540, 260, 200, 200]]}},
    ]}
    out, used = A.attach(CODE, NODES, m)
    assert "1" in used and f"/assets/{H3}.jpg" in out and f"/assets/{H1}.jpg" not in out


def test_alt_text_is_escaped():
    m = {"assets": [dict(MANIFEST["assets"][0], alt='A "quoted" <b>name</b> & co {x}')]}
    out, _ = A.attach(CODE, NODES, m)
    assert 'alt="A &quot;quoted&quot; &lt;b&gt;name&lt;/b&gt; &amp; co &#123;x&#125;"' in out
    assert A.to_scoring(out) == CODE


def test_only_safe_hashes_and_extensions_are_used():
    bad = {"assets": [dict(MANIFEST["assets"][0], hash="../../etc/passwd"),
                      dict(MANIFEST["assets"][0], hash=H2, ext="html")]}
    assert A.attach(CODE, NODES, bad)[1] == []


def test_matching_tolerates_small_offsets_on_icons_but_not_a_different_size():
    assert A.same_place([500, 40, 16, 16], [503, 43, 16, 16])
    assert not A.same_place([500, 40, 16, 16], [500, 40, 40, 40])
    assert A.same_place([95, 246, 200, 200], [100, 250, 200, 200])
    assert not A.same_place([95, 246, 200, 200], [300, 246, 200, 200])


def test_lint_view_of_the_display_code_is_the_scored_code_on_a_real_compile():
    """Round trip on real compiler output (every grey block swapped)."""
    from pathlib import Path
    import re
    fx = Path(__file__).parent / "fixtures" / "assets_app.jsx"
    code = fx.read_text()
    pcs = re.findall(r'<div data-pc="(\d+)"[^>]*bg-\[#d4d4d8\][^>]*/>', code)
    assert len(pcs) >= 5
    nodes = {"mobile": [node(p, [10, 10 + 50 * i, 30, 30]) for i, p in enumerate(pcs)]}
    man = {"assets": [{"hash": H1, "ext": "png", "kind": "img", "bytes": 1, "alt": "x",
                       "boxes": {"mobile": [[10, 10 + 50 * i, 30, 30] for i in range(len(pcs))]}}]}
    out, used = A.attach(code, nodes, man)
    assert sorted(used, key=int) == sorted(pcs, key=int)
    assert A.to_scoring(out) == code


def test_a_block_without_aria_hidden_gets_no_alt_so_the_round_trip_stays_exact():
    code = CODE.replace('<div data-pc="1" aria-hidden="true" className', '<div data-pc="1" className')
    out, used = A.attach(code, NODES, MANIFEST)
    assert "1" in used and 'alt=""' in out.split('data-pc="1"')[1][:200]
    assert A.to_scoring(out) == code


# server-side checks of what the capture sandbox returned (defence in depth: the page ran there)
import hashlib
import io
import json

from PIL import Image


def _png(rgb=(10, 20, 30)):
    b = io.BytesIO()
    Image.new("RGB", (8, 8), rgb).save(b, "PNG")
    return b.getvalue()


def _entry(data, ext, kind="img", alt=""):
    return {"hash": hashlib.sha256(data).hexdigest(), "ext": ext, "kind": kind, "bytes": len(data), "alt": alt,
            "boxes": {"mobile": [[0, 0, 8, 8]]}}


def test_verify_keeps_only_files_whose_bytes_match_hash_and_type():
    good, other = _png(), _png((200, 0, 0))
    svg_ok = b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><path d="M0 0L16 16" stroke="#000"/></svg>'
    svg_bad = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    svg_evt = b'<svg xmlns="http://www.w3.org/2000/svg" onload="x()"><rect/></svg>'
    html = b"<html>hi</html>"
    man = {"assets": [_entry(good, "png", alt="me"), dict(_entry(other, "png"), hash="f" * 64), _entry(svg_ok, "svg", "svg"),
                      _entry(svg_bad, "svg", "svg"), _entry(svg_evt, "svg", "svg"), _entry(html, "png"),
                      dict(_entry(good, "png"), hash="../../x")]}
    files = {f"assets/{a['hash']}.{a['ext']}": d for a, d in zip(man["assets"], [good, other, svg_ok, svg_bad, svg_evt, html, good])}
    files["assets/../../etc/passwd"] = b"root"
    clean, keep = A.verify(files, man)
    hashes = [a["hash"] for a in clean["assets"]]
    assert hashes == [hashlib.sha256(good).hexdigest(), hashlib.sha256(svg_ok).hexdigest()]
    assert set(keep) == {f"assets/{h}.{e}" for h, e in zip(hashes, ("png", "svg"))}
    assert clean["assets"][0]["alt"] == "me"


def test_verify_caps_count_and_total_size():
    many = [_png((i, 0, 0)) for i in range(70)]
    man = {"assets": [_entry(d, "png") for d in many]}
    files = {f"assets/{a['hash']}.png": d for a, d in zip(man["assets"], many)}
    clean, keep = A.verify(files, man, max_count=60, max_total=10 ** 9)
    assert len(clean["assets"]) == 60 == len(keep)
    clean, keep = A.verify(files, man, max_count=60, max_total=sum(len(d) for d in many[:3]))
    assert len(keep) == 3


def test_verify_without_manifest_or_files():
    assert A.verify({}, None) == ({"assets": []}, {})
    assert A.verify({"assets/x.png": b"1"}, {"assets": []}) == ({"assets": []}, {})


def _run_folder(tmp_path, best_code=CODE):
    run = tmp_path / "rid"
    cand = run / "candidates" / "c1"
    cand.mkdir(parents=True)
    (run / "result.json").write_text(json.dumps({"best": "c1"}))
    (cand / "App.jsx").write_text(best_code)
    for bp, nodes in NODES.items():
        (cand / f"{bp}.nodes.json").write_text(json.dumps(nodes))
    (tmp_path / "assets.json").write_text(json.dumps(MANIFEST))
    return run


def test_build_display_writes_the_delivered_code_and_lists_used_assets(tmp_path):
    run = _run_folder(tmp_path)
    info = A.build_display(run, tmp_path / "assets.json")
    assert info["images"] == 2 and sorted(info["assets"]) == sorted([f"{H1}.png", f"{H2}.svg"])
    disp = (run / "display.jsx").read_text()
    assert A.to_scoring(disp) == CODE and "/assets/" in disp


def test_build_display_refuses_when_the_round_trip_is_not_exact(tmp_path, monkeypatch):
    run = _run_folder(tmp_path)
    monkeypatch.setattr(A, "to_scoring", lambda c: c + " ")
    assert A.build_display(run, tmp_path / "assets.json") is None
    assert not (run / "display.jsx").exists()


def test_build_display_without_assets_or_matches_is_none(tmp_path):
    run = _run_folder(tmp_path)
    assert A.build_display(run, tmp_path / "missing.json") is None
    (tmp_path / "assets.json").write_text(json.dumps({"assets": []}))
    assert A.build_display(run, tmp_path / "assets.json") is None
