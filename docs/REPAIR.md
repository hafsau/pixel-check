# Repair benchmark — pre-registration (written Oct 6, 2026, before any repair run)

This file is committed before the Nemotron repair agent runs on any benchmark build. The bar, baselines and
reporting below do not change after results exist; if they must, the change is dated here with the reason, and
results from before the change are reported under the old bar too.

## Question
Given someone else's build (not ours) and PixelCheck's sandbox failure report, can a Nemotron agent repair the
build towards its design at every size — while keeping the author's code — better than simple alternatives?

## Inputs
- **Designs**: Hafsa's original screens (3–5 screens × 390 / 768 / 1280, Inter, few images). Not yet received.
- **Builds**: generated once per screen by v0, Lovable and/or Anima from the same screens (prompt logged verbatim,
  first output used, no hand edits; each tool's terms checked for benchmarking before use). A build that does not
  render at all is excluded and counted.
- Dev captures (third-party pages) are used only to develop the agent — never reported.

## Arms (same builds, same designs, same scorer — sandbox/evaluate.py --check)
1. **No repair** — the build as generated.
2. **Nemotron one-shot** — "make this responsive to these frames" with the frames' text spec, no sandbox feedback
   (isolates what Token Factory Sandboxes add).
3. **Nemotron repair agent** — check → failure report (worst size, regions, missing text, width-sweep failures) →
   edits → re-check, ≤ 3 rounds, best round kept.
4. **Our compiler** — PixelCheck regenerating from the frames (ignores the author's code; reference, not a rival).

## Bar (the agent "works" only if all hold)
- On **≥ 3 of 4** builds: worst-size score **+10** over No repair **or** **≥ 50 %** of width-sweep failures fixed.
- On those builds, **≥ 70 %** of the original code lines kept (line-level diff, whitespace-insensitive).
- The agent beats the one-shot arm on the same metric for ≥ 3 of 4 builds.
- No build gets worse at its worst size by more than 3 points.

## Reporting
Every arm, every build, every size, cost and wall time, in a table — including failures. If the bar is not met:
"Nemotron reads the failure report and names regions; it does not reliably repair" (or what the data shows), and
check mode ships without the repair claim. A council review reads the results before any claim is made.

## Amendments (dated; made before any benchmark run)
- **Oct 7, 2026 — repeat runs.** Development runs on two dev builds showed large run-to-run variance (one build:
  +9.0 in one run, +4.5 in the next, same code and settings). Every LLM arm (one-shot, repair) is therefore run
  **3 times per build**; the bar is judged on the **mean** of the 3 runs, and the range is reported next to it.
  No-repair and compiler arms are deterministic and run once. The bar's thresholds are unchanged.
- **Oct 8, 2026 — council amendment (two independent reviews, both FAIL on the rules above; made before any
  benchmark build exists). Where it conflicts with the sections above, this amendment wins.** Reasons in brief: the
  build count and conversion were open choices; the bar mixed two metrics with an OR; the repair arm keeps only
  improvements while one-shot was a single blind draw (unequal compute, and "never worse by 3" true by
  construction); 4 builds can never reach p < 0.05; nothing froze the agent; and the Oct 7 line calling the compiler
  arm deterministic was wrong (it calls Nemotron for the plan and the region names).

  **Builds.**
  - Screen → tool assignment fixed before generation and recorded here: every screen goes to the same 2 tools
    (chosen and written down before any build is generated). Every generated build counts.
  - Multi-file outputs are flattened to one `App.jsx` by a committed script (imports inlined, `cn()` resolved, icons →
    same-size text-free spans, theme variables → the tool's own values). The script logs every edit; edits that
    change layout are not allowed. No hand edits.
  - "Renders" = `checks.json` exists and at least one design text is readable at every size. Builds that do not
    render are excluded and counted. Fewer included builds than the bar needs → **inconclusive, no repair claim**;
    no regenerating until enough render.

  **Freeze.** Before any build is generated, this file records: the freeze commit, the runtime image tag, the
  SHA-256 of every design frame, and one stored design reading (spec) per screen with its SHA-256. All arms and
  runs use that stored spec (`tools/repair_run.py --spec`). The commit fixes the models, `REPAIR_SYSTEM`,
  temperatures (0.3 / 0.7 / 1.0), 3 candidates and 3 rounds. No tuning on benchmark builds after the freeze.

  **Arms.**
  1. No repair.
  2. One-shot, single draw (reported raw).
  3. **One-shot best-of-9 (the baseline):** 9 one-shot proposals, each checked in the sandbox, best kept only if
     better than no repair. No measured feedback. Same number of scorer checks as the repair arm's typical run,
     same keep-if-better rule, so the gap measures the feedback, not selection in the sandbox.
  4. Repair agent.
  - Compiler arm: **dropped** from the benchmark (the Rebuild numbers are reported elsewhere, separately).

  **Guards (every arm, every run).**
  - Integrity checks + lint on the final code: a new violation compared with the original = disqualified. That run
    counts as no repair (change 0).
  - Edits that hide or clip (`hidden`, `invisible`, `opacity-*`, `overflow-hidden/clip`, …) are refused by the
    edit filter.
  - A width fix counts only if no design text is cut off at that width (`clipped_overflow_px`, image v18).
  - Code kept: className tokens kept ≥ 70 %. The edit tool guarantees nothing outside `className` changes.
  - Before/after images are published for every included build.

  **Primary metric (one).** Per build: the mean over runs of the change in the **mean score over the 3 sizes**,
  with no size dropping more than 1 point in any kept result. The worst-size change, width-sweep fixes and code
  kept are secondary, reported for every arm.

  **Bar (the agent "works" only if all hold).**
  - ≥ 6 included builds.
  - 5 runs per LLM arm per build.
  - Repair's mean gain over no repair ≥ +10, with a one-sided 95 % bootstrap lower bound > 0 (resampling builds).
  - Repair beats the best-of-9 baseline: Wilcoxon signed-rank on per-build means, one-sided p < 0.05.
  - The 4-build "3 of 4" bar above is replaced. Old-bar numbers are reported too, as this file's rules require.

  **Pilot (credit).** At today's cost (about $0.55 per repair run, mostly sandbox time) the full design is about
  60 LLM-arm runs, roughly $33. That does not fit the credit left after the live demo's reserve. Until it does, at
  most a **pilot** runs: 2–3 builds, 3 runs each for repair and best-of-9, under the same freeze and guards. A pilot
  is **descriptive only**: numbers are reported with "pilot, n = …" and **no "works" claim can come from it**.
  Pilot builds are not reused in a later full benchmark.
