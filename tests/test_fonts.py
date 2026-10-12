"""Fonts beyond Inter (Oct 12, Hafsa: "need to replicate accurately"): a catalogue of 16 open-licence families
(sandbox/fonts/catalog.json), typography measured in each family's own glyph metrics, and the family of each text
line detected from its glyph shapes — a page can mix families (hafsausmani.com: Space Grotesk + JetBrains Mono).
Written before the code (TDD)."""
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from orchestrator import typography as T

ROOT = Path(__file__).resolve().parents[1]
CAT = json.loads((ROOT / "sandbox" / "fonts" / "catalog.json").read_text())


def test_the_catalogue_ships_its_files_and_licences():
    assert len(CAT) == 16 and {"Inter", "Lato", "Space Grotesk", "JetBrains Mono"} <= set(CAT)
    for fam, v in CAT.items():
        for w in v["weights"]:
            assert (ROOT / "sandbox" / "fonts" / f"{v['slug']}-latin-{w}-normal.woff2").exists(), (fam, w)
        key = v["slug"].split("-")[0]
        assert any(key in f.name.lower() for f in (ROOT / "sandbox" / "fonts").glob("LICENSE-*")), fam


def line_image(text, family, weight, size, bg=(255, 255, 255), ink=(20, 20, 20)):
    f = T._font(weight, size, family)
    x0, y0, x1, y1 = f.getbbox(text)
    im = Image.new("RGB", (x1 + 40, y1 + 40), bg)
    ImageDraw.Draw(im).text((20, 20), text, fill=ink, font=f)
    a = np.asarray(im, dtype=np.float32)
    ys, xs = np.nonzero(np.linalg.norm(a - np.array(bg), axis=2) > 60)
    box = [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]
    return a, box


@pytest.mark.parametrize("family,weight,size", [("Lato", 700, 22), ("Space Grotesk", 500, 18), ("Poppins", 400, 16),
                                                ("JetBrains Mono", 400, 14), ("Inter", 600, 20)])
def test_size_and_weight_are_measured_in_the_lines_own_family(family, weight, size):
    text = "Keep the momentum going today"
    img, box = line_image(text, family, weight, size)
    r = T.infer(text, box, img, family=family)
    assert abs(r["size_px"] - size) <= 1, r
    near = min(CAT[family]["weights"], key=lambda w: abs(w - weight))
    assert abs(r["weight"] - near) <= 100, r


def words_image(text, family, weight, size, bg=(255, 255, 255)):
    """A line drawn word by word, with each word's ink box (what OCR gives)."""
    f = T._font(weight, size * 4, family)               # drawn at 4× and filtered down: unhinted, like a browser
    im = Image.new("RGB", (int(f.getlength(text)) + 240, size * 12), bg)
    d = ImageDraw.Draw(im)
    x, words = 80, []
    for wd in text.split():
        d.text((x, 80), wd, fill=(20, 20, 20), font=f)
        b = d.textbbox((x, 80), wd, font=f)
        words.append({"text": wd, "box": [b[0] // 4, b[1] // 4, (b[2] - b[0]) // 4 + 1, (b[3] - b[1]) // 4 + 1]})
        x += int(f.getlength(wd + " "))
    im = im.resize((im.size[0] // 4, im.size[1] // 4), Image.BOX)
    return np.asarray(im, dtype=np.float32), words


@pytest.mark.parametrize("family", ["Lato", "Space Grotesk", "JetBrains Mono", "Poppins", "Inter"])
def test_a_lines_family_is_detected_from_its_glyph_shapes(family):
    text = "Morning Mobility gives your joints a gentle start"
    img, words = words_image(text, family, 400, 20)
    box = [words[0]["box"][0], min(w["box"][1] for w in words), words[-1]["box"][0] + words[-1]["box"][2] - words[0]["box"][0],
           max(w["box"][1] + w["box"][3] for w in words) - min(w["box"][1] for w in words)]
    scores = T.family_scores(text, box, img, words=words)
    assert max(scores, key=scores.get) == family, sorted(scores.items(), key=lambda kv: -kv[1])[:4]


def vote(winner, size, margin, others=("Space Grotesk", "Roboto", "JetBrains Mono", "Poppins", "Moche-like")):
    sc = {f: 0.5 for f in others}
    sc["Space Grotesk"] = 0.6
    if winner != "Space Grotesk":
        sc[winner] = 0.6 + margin
    return {"winner": winner, "size_px": size, "scores": sc}


def test_a_page_vote_keeps_a_mono_face_and_a_display_face_not_look_alike_sans():
    votes = ([vote("Space Grotesk", 16, 0)] * 6 + [vote("JetBrains Mono", 12, 0.12)] * 3
             + [vote("Roboto", 14, 0.01)] * 4                      # a look-alike winning by a hair: noise
             + [vote("Poppins", 14, 0.2)] + [vote("Moche-like", 96, 0.15)])
    fams = T.page_families(votes)
    assert fams["body"] == "Space Grotesk"
    assert "JetBrains Mono" in fams["kept"] and "Moche-like" in fams["kept"]       # mono labels, a display headline
    assert "Roboto" not in fams["kept"] and "Poppins" not in fams["kept"]


def test_the_body_family_is_the_best_overall_not_the_most_single_wins():
    votes = [{"winner": "Poppins", "size_px": 16, "scores": {"Inter": 0.70, "Poppins": 0.71}}] + \
            [{"winner": "Inter", "size_px": 16, "scores": {"Inter": 0.8, "Poppins": 0.5}}] * 2 + \
            [{"winner": "Roboto", "size_px": 16, "scores": {"Inter": 0.6, "Roboto": 0.61, "Poppins": 0.4}}]
    assert T.page_families(votes)["body"] == "Inter"


@pytest.mark.skipif(not (ROOT / "benchmarks" / "desktop.png").exists(), reason="Hafsa's screens not present")
def test_hafsas_dashboard_is_lato():
    from orchestrator import measure
    png = (ROOT / "benchmarks" / "desktop.png").read_bytes()
    m = measure.measure(png)
    assert m["fonts"]["body"] == "Lato", m["fonts"]


@pytest.mark.skipif(not (ROOT / "ui" / "published" / "hafsausmani-home" / "real" / "desktop.webp").exists(),
                    reason="published replay absent")
def test_the_three_frames_vote_together_hafsausmani_com():
    """One page, three frames: alone, the desktop first screen (5 lines: nav + headline) voted JetBrains Mono as its
    body face. Pooled: Space Grotesk body, JetBrains Mono nav labels, everywhere."""
    import io
    from orchestrator import measure
    pngs = {}
    for bp in ("mobile", "tablet", "desktop"):
        im = Image.open(ROOT / "ui" / "published" / "hafsausmani-home" / "real" / f"{bp}.webp").convert("RGB")
        b = io.BytesIO()
        im.save(b, "PNG")
        pngs[bp] = b.getvalue()
    meas = {bp: measure.measure(p) for bp, p in pngs.items()}
    measure.unify_fonts(meas, pngs)
    for bp, m in meas.items():
        assert m["fonts"]["body"] == "Space Grotesk" and "JetBrains Mono" in m["fonts"]["kept"], (bp, m["fonts"])
    nav = [l for l in meas["desktop"]["text_lines"] if l["text"].strip() in ("WORK", "ABOUT", "CONTACT")]
    assert nav and all(l["font"] == "JetBrains Mono" for l in nav), [(l["text"], l["font"]) for l in nav]


def test_the_compiler_names_a_family_only_where_it_differs_from_the_page():
    from orchestrator.fluid import _family
    body = "Space Grotesk"
    assert _family({bp: {"font": "Space Grotesk"} for bp in ("mobile", "tablet", "desktop")}, body) == ""
    mono = _family({bp: {"font": "JetBrains Mono"} for bp in ("mobile", "tablet", "desktop")}, body)
    assert mono == "font-['JetBrains_Mono']"
    mixed = _family({"mobile": {"font": "JetBrains Mono"}, "tablet": {"font": "Space Grotesk"},
                     "desktop": {"font": "Space Grotesk"}}, body).split()
    assert mixed == ["font-['JetBrains_Mono']", "md:font-['Space_Grotesk']"]
    from orchestrator.fluid import root_family
    assert root_family("Inter") == "font-sans" and root_family("Lato") == "font-['Lato']"


def test_the_renderer_embeds_and_uses_the_families_the_code_names(tmp_path):
    import subprocess
    app = ("export default function App(){return <main className=\"font-['Lato'] p-4\"><h1 className=\"text-[32px]\">"
           "Welcome back</h1><p className=\"font-['JetBrains_Mono'] text-[14px]\">720 XP</p></main>}")
    (tmp_path / "App.jsx").write_text(app)
    r = subprocess.run(["node", "render.mjs", "--in", str(tmp_path / "App.jsx"), "--out", str(tmp_path / "out")],
                       cwd=ROOT / "sandbox", capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-400:]
    checks = json.loads((tmp_path / "out" / "checks.json").read_text())
    assert checks["breakpoints"]["mobile"]["fonts_ok"] is True
    assert set(checks["fonts"]) == {"Inter", "IBM Plex Mono", "Lato", "JetBrains Mono"}
    dom = json.loads((tmp_path / "out" / "mobile.dom.json").read_text())
    fams = {e.get("text"): e.get("font_family", "") for e in dom}
    assert "Lato" in fams.get("Welcome back", "") and "JetBrains Mono" in fams.get("720 XP", "")
