"""Text the vision model skipped (Oct 12, Hafsa's dashboard): OCR read "720 XP" and "280 to Level 5" cleanly, Gemma
listed neither, and merge() kept only Gemma's strings — the header's right side vanished. A clean OCR line no
vision text matched is kept as measured text; junk (an avatar read as "@") is not; a line a vision text already
matched is not added twice. Written before the code (TDD)."""
from orchestrator.perceive import merge


def line(text, box, words=None):
    return {"text": text, "box": box, "color": "#111111", "backdrop": "#ffffff",
            "words": words or [{"text": w, "box": box} for w in text.split()], "typo": {}}


def test_clean_ocr_lines_the_vision_model_skipped_are_kept():
    meas = {"text_lines": [line("Welcome back, m", [24, 59, 187, 22]), line("720 XP", [934, 52, 46, 11]),
                           line("280 to Level 5", [904, 72, 74, 9]), line("@", [991, 38, 56, 56]),
                           line("Show up for 15 minutes. That's", [48, 212, 300, 22])],
            "blocks": [], "size": [1071, 800], "background": "#ffffff"}
    vlm = {"texts": [{"text": "Welcome back, m", "role": "heading"},
                     {"text": "Show up for 15 minutes. That's a win.", "role": "body"}]}
    out = merge(vlm, meas)
    texts = [t["text"] for t in out["texts"]]
    assert "720 XP" in texts and "280 to Level 5" in texts and "@" not in texts
    extra = [t for t in out["texts"] if t["text"] == "720 XP"][0]
    assert extra["measured"] and extra["box"] == [934, 52, 46, 11] and extra.get("ocr_only")
    assert sum("Show up" in t for t in texts) == 1          # matched loosely by the vision text: not added again


def test_junk_from_cut_off_letters_is_not_kept():
    """hafsausmani.com desktop (own fonts): the tops of a headline cut by the fold read as "A AK" — not text."""
    l = line("A AK", [810, 731, 462, 69])
    l["conf"] = 41.0
    meas = {"text_lines": [l, line("Welcome back, m", [24, 59, 187, 22])], "blocks": [], "size": [1280, 800],
            "background": "#ffffff"}
    texts = [t["text"] for t in merge({"texts": [{"text": "Welcome back, m"}]}, meas)["texts"]]
    assert "A AK" not in texts


def test_a_clipped_headline_takes_its_text_from_the_other_frames():
    """hafsausmani.com desktop: "USMANI" is cut by the fold and the vision model did not list it; the clipped-heading
    rule took "UI/UX AND UI DESIGN" (listed, not visible). Mobile shows what follows "HAFSA": USMANI."""
    from orchestrator.perceive import clipped_from_frames
    t = lambda text, y, **k: {"text": text, "box": [0, y, 300, 60], "measured": True, "size_px": 96, **k}
    bps = {"mobile": {"size": [390, 844], "texts": [t("HAFSA", 150), t("USMANI", 450), t("UI/UX AND UI DESIGN", 700)]},
           "tablet": {"size": [768, 1024], "texts": [t("HAFSA", 150), t("USMANI", 600)]},
           "desktop": {"size": [1280, 800], "texts": [t("HAFSA", 164), t("UI/UX AND UI DESIGN", 727, clipped=True)]}}
    out = clipped_from_frames(bps)
    assert [x["text"] for x in out["desktop"]["texts"]] == ["HAFSA", "USMANI"]


def test_a_clipped_headline_takes_its_font_and_weight_from_the_other_frames():
    from orchestrator.perceive import clipped_from_frames
    t = lambda text, y, **k: {"text": text, "box": [0, y, 300, 60], "measured": True, "size_px": 96, **k}
    bps = {"mobile": {"size": [390, 844], "texts": [t("HAFSA", 150, font="Manrope", weight=800),
                                                     t("USMANI", 450, font="Manrope", weight=800)]},
           "desktop": {"size": [1280, 800], "texts": [t("HAFSA", 164, font="Manrope", weight=800),
                                                       t("USMANI", 727, clipped=True)]}}
    u = clipped_from_frames(bps)["desktop"]["texts"][1]
    assert u["font"] == "Manrope" and u["weight"] == 800


def test_a_fragment_of_a_matched_text_on_the_same_row_is_not_added_again():
    """Dashboard: OCR split "A gentle routine to wake up your | joints" at a gap; the paragraph matched the first part
    and "joints" was re-added on its own, floating beside the paragraph."""
    meas = {"text_lines": [line("A gentle routine to wake up your", [398, 687, 230, 15]), line("joints", [632, 687, 38, 15]),
                           line("and build consistent motion.", [398, 710, 190, 15])],
            "blocks": [], "size": [1071, 1177], "background": "#ffffff"}
    vlm = {"texts": [{"text": "A gentle routine to wake up your joints and build consistent motion.", "role": "body"}]}
    texts = [t["text"] for t in merge(vlm, meas)["texts"]]
    assert "joints" not in texts
