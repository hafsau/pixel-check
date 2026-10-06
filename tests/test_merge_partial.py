"""perceive.merge on reads OCR splits or clips (Oct 6, a portfolio page): a tagline split at "·" into two OCR lines
on one row, a button label read as "SEE MY" (the vision model reads "SEE MY WORK"), a nav run read as "ORK ABOUT
CONTACT". Each fell back to the vision model's box (~100 px off, measured=False) and the compiler misplaced it.
Same-row OCR lines may join; an OCR read that is clearly part of the string counts, its box extended by the
missing characters. Written before the change (TDD)."""
from orchestrator.perceive import merge


def line(text, box, words=None):
    ws = words or []
    if not ws:          # words spread evenly over the box
        parts, x = text.split(), box[0]
        cw = box[2] / max(1, len(text))
        for p in parts:
            w = round(len(p) * cw)
            ws.append({"text": p, "box": [round(x), box[1], w, box[3]]})
            x += w + cw
    return {"text": text, "box": list(box), "color": "#111111", "backdrop": "#ffffff", "words": ws, "typo": {}}


def meas(lines, blocks=()):
    return {"size": [390, 844], "background": "#ffffff", "text_lines": lines, "blocks": list(blocks)}


def vlm(*texts):
    return {"texts": [{"text": t, "role": "body", "size_px": 14} for t in texts]}


def by_text(spec):
    return {t["text"]: t for t in spec["texts"]}


def test_same_row_lines_join_into_one_text():
    m = meas([line("Product Designer", [42, 621, 120, 13]), line("San Francisco Bay Area", [180, 621, 168, 13])])
    t = by_text(merge(vlm("Product Designer · San Francisco Bay Area"), m))["Product Designer · San Francisco Bay Area"]
    assert t["measured"] and t["box"] == [42, 621, 306, 13]


def test_lines_far_apart_on_a_row_do_not_join():
    m = meas([line("Pricing", [20, 30, 60, 12]), line("Sign in", [300, 30, 50, 12])])
    out = by_text(merge(vlm("Pricing Sign in"), m))["Pricing Sign in"]
    assert not out["measured"]


def test_a_clipped_read_is_extended_by_the_missing_characters():
    m = meas([line("SEE MY", [126, 684, 58, 10])])
    t = by_text(merge(vlm("SEE MY WORK"), m))["SEE MY WORK"]
    assert t["measured"] and t["box"][0] == 126 and t["box"][1] == 684
    assert 100 <= t["box"][2] <= 112                     # 58 px for 6 chars → ~106 px for 11
    assert t.get("extended")


def test_a_word_missing_its_first_letter_is_extended_left():
    m = meas([line("ORK ABOUT CONTACT", [496, 38, 302, 10],
                   words=[{"text": "ORK", "box": [496, 38, 34, 10]}, {"text": "ABOUT", "box": [596, 38, 56, 10]},
                          {"text": "CONTACT", "box": [720, 38, 78, 10]}])])
    out = by_text(merge(vlm("WORK", "ABOUT", "CONTACT"), m))
    assert out["ABOUT"]["box"] == [596, 38, 56, 10] and out["CONTACT"]["box"] == [720, 38, 78, 10]
    w = out["WORK"]
    assert w["measured"] and w["box"][1] == 38 and 482 <= w["box"][0] <= 488 and 44 <= w["box"][2] <= 48


def test_a_short_unrelated_read_is_not_taken_as_part():
    m = meas([line("MY", [126, 684, 20, 10])])
    out = by_text(merge(vlm("SEE MY WORK"), m))["SEE MY WORK"]
    assert not out["measured"]                            # 2 of 11 characters is not enough


def test_exact_matches_are_unchanged():
    m = meas([line("Hello world", [10, 10, 100, 14])])
    t = by_text(merge(vlm("Hello world"), m))["Hello world"]
    assert t["box"] == [10, 10, 100, 14] and not t.get("extended")


# a giant headline cut by the fold: OCR fails, its strokes are measured as dark blocks along the bottom edge, and the
# vision model misreads it ("LISMANI"); the other frames measured it ("USMANI")
from orchestrator.perceive import fold_headings, cross_frame_spelling

H = 800


def frame(texts, blocks, w=1280):
    return {"size": [w, H], "background": "#fff4e4", "texts": texts, "blocks": blocks}


def strokes():
    return [{"box": [98, 709, 388, 91], "fill": "#1a1a1a"}, {"box": [520, 751, 60, 49], "fill": "#1a1a1a"},
            {"box": [937, 710, 101, 90], "fill": "#1a1a1a"}, {"box": [1072, 710, 42, 90], "fill": "#1a1a1a"},
            {"box": [1147, 710, 41, 90], "fill": "#191919"}]


def heading(text, box, measured=True, approx=False):
    return {"text": text, "role": "heading", "box": list(box), "size_px": 72, "weight": 700, "color": "#1a1a1a",
            "measured": measured, **({"approx": True} if approx else {})}


def test_strokes_along_the_bottom_edge_become_the_clipped_headings_box():
    f = frame([dict(heading("HAFSA", (184, 150, 930, 208)), size_px=270), heading("LISMANI", (184, 571, 200, 16), False, True)],
              strokes())
    fold_headings(f)
    t = f["texts"][1]
    assert t["box"][0] == 98 and t["box"][1] == 709 and t["box"][2] == 1090
    assert t.get("clipped") and t["measured"]
    assert 210 <= t["size_px"] <= 300     # from width per character (scaled by the measured headline), not the clipped height
    assert f["blocks"] == []                              # the strokes are the text, not blocks


def test_no_unplaced_heading_means_blocks_stay():
    f = frame([heading("HAFSA", (184, 150, 930, 208))], strokes())
    fold_headings(f)
    assert len(f["blocks"]) == 5


def test_ordinary_dark_blocks_at_the_bottom_are_not_a_heading():
    """A footer bar touching the bottom edge, one block: not strokes of a headline."""
    f = frame([heading("Get started", (40, 300, 200, 16), False, True)], [{"box": [0, 740, 1280, 60], "fill": "#111111"}])
    fold_headings(f)
    assert len(f["blocks"]) == 1 and not f["texts"][0].get("clipped")


def test_cross_frame_spelling_fixes_a_misread_clipped_text():
    bps = {"mobile": frame([heading("USMANI", (60, 446, 272, 52))], [], 390),
           "tablet": frame([heading("USMANI", (88, 580, 595, 114))], [], 768),
           "desktop": frame([dict(heading("HAFSA", (184, 150, 930, 208)), size_px=270),
                             dict(heading("LISMANI", (98, 709, 1090, 91)), clipped=True, size_px=226)], [])}
    cross_frame_spelling(bps)
    t = bps["desktop"]["texts"][1]
    assert t["text"] == "USMANI" and 255 <= t["size_px"] <= 275      # size re-estimated for 6 characters


def test_cross_frame_spelling_leaves_measured_text_alone():
    bps = {"mobile": frame([heading("Pricing", (10, 10, 60, 14))], [], 390),
           "desktop": frame([heading("Prices", (10, 10, 60, 14))], [])}
    cross_frame_spelling(bps)
    assert bps["desktop"]["texts"][0]["text"] == "Prices"


def test_unread_ocr_junk_along_the_edge_joins_the_strokes():
    f = frame([dict(heading("HAFSA", (184, 150, 930, 208)), size_px=270), heading("USMANI", (184, 571, 200, 16), False, True)],
              strokes()[2:])                                   # only the right-hand strokes are blocks
    fold_headings(f, loose=[[98, 709, 388, 91], [517, 751, 10, 34]])    # "Brey" at the edge; "\\" not at the edge
    assert f["texts"][1]["box"][0] == 98 and f["texts"][1]["box"][2] == 1090


def test_clip_size_uses_a_measured_headline_of_a_nearby_colour():
    f = frame([dict(heading("HAFSA", (184, 150, 930, 208)), size_px=278, color="#191919"),
               dict(heading("USMANI", (184, 571, 200, 16), False, True), color="#000000")], strokes())
    fold_headings(f)
    assert 260 <= f["texts"][1]["size_px"] <= 280
