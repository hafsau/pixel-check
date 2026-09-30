# Scoring (v4, 2026-09-29 — after council red-team rounds 1 and 2)

Source of truth: `sandbox/score.py` (docstring has the formula and the reason for each choice). Tests: `tests/test_score.py` (thresholds fixed before measuring; never loosened to pass).

## Formula

Per breakpoint, all components in [0, 1]:

**S = 100 × (0.25 + 0.75·colour) × (0.5 + 0.5·text) × (0.57·structure + 0.43·layout)**, also computed at the best global offset (≤ 32 px per axis, vertical, horizontal and both) × (1 − 0.006·(|dy|+|dx|)); the highest wins.
**Match = min(S_mobile, S_tablet, S_desktop)** — the mean is reported, never used to rank.

| Component | What | Why this, not the obvious thing |
|---|---|---|
| structure | Edge-energy F1 (Sobel, half-res), **horizontal and vertical gradients separately**, averaged over tolerances ±2/±4/±8/±16 px | Plan v4 used SSIM. SSIM calls flat regions "similar": a **blank render scored 0.57** even with SSIM masked to content |
| layout | min(precision, recall) of 8 px content cells, 1-cell tolerance, × (0.5 + 0.5·ink-coverage agreement per 3×3-cell neighbourhood) | F1 turned "56 % of content area missing" into 0.70; min() keeps missing and extra content both fully costly — same logic as Match = min |
| colour (multiplier) | 0.5 × background match + 0.5 × content colour; per 16 px cell content colour = min(content-pixel ΔE, whole-cell ΔE) vs best 3×3 neighbour, scale 40 | As an additive 15 % term, an **inverted (dark-mode) render scored 71**. Whole-cell colour averages rewarded blank pages |
| text | Share of target strings (with ink in the target) found as **readable** render text: on-screen, ≥ 8 px, not transparent, ≥ 3 % ink in its box; fuzzy ≥ 0.85, whole-word for < 4 chars | Invisible text dumps farmed credit (red-team #1). Production always has target text (spec) |

Content = pixels > 24 RGB from **that image's own** background. (Measuring the render against the target's background made a solid wrong-colour fill "content everywhere".)

## Calibration (dev captures, text component off)

| Case (5 pages × 3 breakpoints) | min | median | max |
|---|---|---|---|
| identical | 100.0 | 100.0 | 100.0 |
| shift 2px | 98.2 | 99.8 | 99.9 |
| shift 6px | 89.1 | 91.5 | 94.3 |
| shift 12px | 72.6 | 77.3 | 79.0 |
| shift 24px | 48.1 | 58.7 | 63.9 |
| lower 25% removed | 48.8 | 84.8 | 100.0 |
| lower 50% removed | 46.8 | 66.5 | 93.1 |
| inverted | 25.1 | 25.9 | 27.0 |
| blank (own bg) | 0.0 | 0.0 | 0.0 |
| blank (black/white opposite) | 0.0 | 0.0 | 0.0 |
| a different page, same breakpoint | 0.9 | 10.7 | 49.7 |

"Lower N % removed" varies by page because it removes different amounts of content (100 = that page's lower quarter was already empty).

## Changes from plan v4 (and what failed first)

| v1 behaviour (measured) | Test that caught it | Fix |
|---|---|---|
| Blank page 26.7 (synthetic), 22–31 (real, opposite colour) | blank < 20 | Edge-F1 instead of SSIM; own-background content masks |
| Inverted 70–72 | inverted < 40 | Colour is a multiplier; area-weighted with background |
| 2 px shift 91–95 | 2 px shift ≥ 95 | Colour compared against best neighbouring cell, content-weighted |
| 12 px offset < "lower half missing" | monotonic | Multi-tolerance structure. Test narrowed to *within* one damage family; cross-family order is a judgement (see council review) |
| 56 % of content area missing → 77 | half removed < 75 | layout = min(p, r) |
| Mobile crash (844 px not a multiple of 16) | every mobile case | Grids aligned by padding |

## Council review, round 1 (red-team agent, 2026-09-29) → v3

Attack renders: `out/redteam/` (local only). Rescored under v3: `out/redteam/v3_scores.json`. Regression tests: `tests/test_score_redteam.py`.

| Finding (v2) | v2 | v3 |
|---|---|---|
| Invisible text dump (transparent / opacity 0.01 / below fold) on a close render | +2.4 → 99.9 | +0.0 (95.6 = close) |
| "Dust" (3 px dot per content cell), best page | 93.4 | 50.3 |
| All 103 pure hacks (dust, blobs, thin lines, bg lines, heading-only…) max Match | 93.4 | **50.3** |
| Fake responsive diluted with 200 junk spans | passed integrity | **DQ** (duplicate ratio over readable text + invisible-text cap) |
| netflix rough / decent / close (Match) | 23.0 / 58.6 / 97.5 (desktop tie) | 17.6 / 68.0 / 95.6 |
| calcom rough / decent / close | 12.4 / 57.6 / 91.0 | 12.8 / 53.6 / 86.8 |
| netflix close with blue CTA | 93.9 (−3.6) | 81.6 (−14.1) |
| netflix close, 20 px lower | 69.2 (below junk) | 73.8 (above every hack) |
| Transparent-PNG target | honest render 15.7 | composited on white |

Accepted residuals: typeface is weakly scored (Arial ≈ Inter) — irrelevant in practice because the sandbox only has Inter/Plex; a 10 % font-size error that re-wraps text is scored hard (calcom tablet 62) — intended, re-wrapping is a visible layout change.

## Council review, round 2 (red-team agent) → v4

Round-2 attacks: `out/redteam/round2/` (local only). Full-pipeline regression (lint + render + pixel integrity + score) over **389** candidates: `tools/rescore_attacks.py` → `out/redteam/rescore.json`; asserted by `tests/test_attack_regression.py`.

| v3 hole (round 2) | v3 | v4 fix | v4 |
|---|---|---|---|
| Design copy hidden **behind** an opaque element + lorem visible copy | 94.1, passed gates | **Readability by pixels**: render.mjs takes a text-transparent screenshot and a per-element colour-coded screenshot; a string is readable only if ITS OWN glyph pixels are visible (honest text ≥ 12.2 px/char, threshold 3) | DQ (hidden copies of design text) |
| 6 other hiding vectors (clip-path, filter, h-0, same colour, blend…) | passed | same mechanism | no credit; DQ when ≥ 2 design strings hidden |
| `sr-only` a11y labels | **DQ** (honest page → 0) | hidden text that matches no design string is allowed | 92.7 = close |
| Input placeholder / gradient heading | lost text credit | placeholder/value extracted; bg-clip text counted as painted | 92.7 = close |
| Traced layout (every element pinned in one grid cell) | 70–73, passed | integrity: readable text inside stacked-grid / overlapping block siblings > 30 % → DQ | DQ |
| Visible strip of every design string | +8 | text counts only within max(96 px, 15 % width) of its design position (distance to element box) | gains nothing vs its neutralised twin |
| Lorem-ipsum copy on a perfect layout | 64.4 | text is a multiplier (0.5 + 0.5·text) | 46.0 |
| Horizontal offset unrescued | 87.1 (20 px) | offset search on both axes | — |
| Crashes / free credit on edge inputs | several | input validation (shape, finiteness, range, ≥ 32 px), float64 background (float32 drifted to 255.4), bg-only colour when no content | raise / fixed |

**v4 results (389 candidates):** 134 standalone hacks — max **46.0**; 174 tricks — none gains > 0.5 over its base or neutralised twin; honest pages and markup variants — **never disqualified**. Fidelity ladders (Match): netflix rough 11.8 / decent 59.7 / close 92.7; calcom 1.0 / 35.4 / 82.2. Blue instead of red CTA: −13.8.

Threshold changes made openly in round 2: "20 px offset ≥ 80" now applies with text off (with text on, strings pushed below the fold are genuinely missing; must still beat every hack). `h_heading_br` is not a markup-only variant (the `<br>` changes the mobile line break).

Accepted residuals: oracle pixel textures built FROM the target image (stripes/checker at the target's ink density) still score high at pixel level — the agent never sees the target, so this bounds credibility, not the loop; honest "close" lost ~3 points to a hidden "Password" label in the dev ground truth (production specs come from OCR of visible text).
