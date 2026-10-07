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
