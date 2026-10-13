"""OCR lines cleaned before typography (Oct 12, Hafsa's dashboard): an icon read as a character ("> Current Streak",
"4 TODAY'S FOCUS") and a big number joined with a small word ("4 Days") made one line whose box mixed sizes — the
heading came out 29 px instead of ~18, and "Days" lost its own size. Split lines whose words differ a lot in height;
drop a leading 1–2 character "word" that is a symbol, a different colour from the text or clearly taller (an icon).
Written before the code (TDD)."""
import numpy as np

from orchestrator.measure import clean_lines


def word(t, box):
    return {"text": t, "box": box}


def line(words, conf=90.0):
    x0 = min(w["box"][0] for w in words); y0 = min(w["box"][1] for w in words)
    x1 = max(w["box"][0] + w["box"][2] for w in words); y1 = max(w["box"][1] + w["box"][3] for w in words)
    return {"text": " ".join(w["text"] for w in words), "box": [x0, y0, x1 - x0, y1 - y0], "conf": conf, "words": words}


def page(paint):
    img = np.full((300, 600, 3), 255, np.float32)
    for (x, y, w, h), c in paint:
        img[y:y + h, x:x + w] = c
    return img


def test_a_big_number_and_a_small_word_are_two_lines():
    img = page([((49, 464 - 400, 22, 35), (20, 20, 20)), ((83, 478 - 400, 40, 15), (90, 90, 90))])
    out = clean_lines(img, [line([word("4", [49, 64, 22, 35]), word("Days", [83, 78, 40, 15])])])
    assert [(l["text"], l["box"]) for l in out] == [("4", [49, 64, 22, 35]), ("Days", [83, 78, 40, 15])]


def test_a_leading_icon_read_as_a_symbol_is_dropped():
    img = page([((50, 20, 14, 18), (37, 99, 235)), ((82, 22, 60, 14), (20, 20, 20)), ((148, 22, 50, 14), (20, 20, 20))])
    out = clean_lines(img, [line([word(">", [50, 20, 14, 18]), word("Current", [82, 22, 60, 14]),
                                  word("Streak", [148, 22, 50, 14])])])
    assert out[0]["text"] == "Current Streak" and out[0]["box"] == [82, 22, 116, 14]


def test_a_real_number_starting_a_line_stays():
    img = page([((40, 40, 9, 14), (20, 20, 20)), ((55, 40, 50, 14), (20, 20, 20))])
    out = clean_lines(img, [line([word("2", [40, 40, 9, 14]), word("items", [55, 40, 50, 14])])])
    assert out[0]["text"] == "2 items"


def test_an_unchanged_line_keeps_ocrs_own_box():
    img = page([((40, 40, 9, 14), (20, 20, 20)), ((55, 40, 50, 14), (20, 20, 20))])
    l = line([word("2", [40, 40, 9, 14]), word("items", [55, 40, 50, 14])])
    l["box"] = [39, 38, 68, 18]                       # Tesseract's line box is a little looser than its words'
    assert clean_lines(img, [l])[0] is l


def test_short_letters_are_not_a_size_change():
    """netflix: "ensure you're not a bot." was split at "a" (x-height only) next to "bot." (ascender)."""
    img = page([((10, 50, 60, 10), (20, 20, 20)), ((76, 53, 8, 7), (20, 20, 20)), ((90, 49, 28, 11), (20, 20, 20))])
    out = clean_lines(img, [line([word("not", [10, 50, 30, 10]), word("a", [76, 53, 8, 7]), word("bot.", [90, 49, 28, 11])])])
    assert len(out) == 1


def test_a_single_letter_with_a_tall_ocr_box_does_not_split_and_a_price_is_not_an_icon():
    img = page([((10, 50, 60, 10), (20, 20, 20)), ((76, 48, 4, 17), (20, 20, 20)), ((90, 50, 22, 10), (20, 20, 20)),
                ((10, 120, 30, 28), (20, 20, 20)), ((44, 128, 28, 18), (90, 90, 90))])
    out = clean_lines(img, [line([word("not", [10, 50, 60, 10]), word("a", [76, 48, 4, 17]), word("bot.", [90, 50, 22, 10])]),
                            line([word("$0", [10, 120, 30, 28]), word("/mo.", [44, 128, 28, 18])])])
    assert [l["text"] for l in out] == ["not a bot.", "$0 /mo."]


def test_overlapping_word_boxes_are_an_ocr_mess_not_a_size_change():
    """lennysjobs: OCR gave "in" of "Log in" a 32 px box overlapping "Log" — not a big word."""
    img = page([((219, 22, 40, 14), (20, 20, 20))])
    out = clean_lines(img, [line([word("Log", [219, 22, 40, 14]), word("in", [246, 10, 14, 32])])])
    assert len(out) == 1


def test_a_button_label_read_between_its_edges_loses_both_bars():
    """Dashboard "Start Workout": per-button OCR read "| Start Workout |" — the button's edges as bars."""
    img = page([((479, 20, 38, 13), (255, 255, 255)), ((522, 20, 71, 14), (255, 255, 255))])
    out = clean_lines(img, [line([word("|", [400, 0, 3, 56]), word("Start", [479, 20, 38, 13]), word("Workout", [522, 20, 71, 14]),
                                  word("|", [668, 0, 3, 56])])])
    assert out[0]["text"] == "Start Workout" and out[0]["box"] == [479, 20, 114, 14]


def test_a_light_label_on_a_coloured_button_is_light():
    from orchestrator.measure import label_ink
    img = np.full((80, 300, 3), (51, 102, 255), np.float32)
    img[30:44, 40:200] = (255, 255, 255)
    img[34:40, 40:200] = (51, 102, 255)                     # strokes: white with blue gaps
    assert label_ink(img, [40, 30, 160, 14], "#3366ff") == "#ffffff"


def test_a_progress_bar_is_a_track_holding_its_fill():
    """Dashboard "Time Logged": the purple fill [49, 786, 182, 12] covers the left of its grey track, so the track was
    measured as only its visible rest [228, 786, 96, 12]; partly overlapping, the compiler dropped both."""
    from orchestrator.measure import progress_bars
    blocks = [{"box": [49, 786, 182, 12], "fill": "#8a2be2", "radius": 6}, {"box": [228, 786, 96, 12], "fill": "#ebecf9"},
              {"box": [24, 633, 325, 190], "fill": "#ffffff"}]
    out = progress_bars(blocks)
    track = [b for b in out if b["fill"] == "#ebecf9"][0]
    assert track["box"] == [49, 786, 275, 12] and track.get("radius") == 6
    assert [b for b in out if b["fill"] == "#8a2be2"][0]["box"] == [49, 786, 182, 12]
