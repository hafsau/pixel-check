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
