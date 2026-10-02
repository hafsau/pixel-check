# Interactions — Nemotron writes the behaviour (decided Oct 2)

## Why
Step D ablation (`tools/ablation.py`, Oct 2): the deterministic compiler produces the static layout; Nemotron's intent
plan and the loop's editing rounds added **0 points** (rounds cost 7–10×). Honest Gate A as defined failed on
"Nemotron decisive". Hafsa chose to give Nemotron the job the compiler cannot do: **write the interaction code** —
React state, event handlers, the panel/expanded content — from *state frames*, verified by tests run in the sandbox.

## Input
Per page: the 3 static frames (as now) + state frames, each `{bp, state name, trigger}`:
- dev pages: captured with `tools/capture_linux.py <page> --state=<name> --click='<css>' --bps=...`
  (Oct 2: lambda / vercel mobile+tablet menus = full-screen overlays; lennysjobs mobile menu = side drawer)
- Hafsa's originals: Figma frames named `<screen>/<bp>/<state>` + the trigger's layer name.

## Pipeline (each stage written test-first)
| # | Stage | Deterministic / model | Tests first |
|---|---|---|---|
| 1 | `states.state_diff(base, state)` → appeared / disappeared / moved / persisted, kind (overlay · drawer · inline · none), panel box; `dim_region`, `backdrop`, `trigger_look` from the images | deterministic | `tests/test_states.py` ✅ |
| 2 | Trigger resolution: trigger box → `<button data-trigger>` in the compiled base | deterministic | `tests/test_triggers.py` ✅ |
| 3 | Panel content (shared or per-breakpoint + wrapper), compiled trigger open look | deterministic | `tests/test_panel.py`, `tests/test_glyphs.py`, `tests/test_measure_crosses.py` ✅ |
| 4 | **Interaction writer (Nemotron Ultra)**: four sections → deterministic assembly | **Nemotron** | `tests/test_writer.py` ✅ |
| 5 | Generated acceptance tests (`render.mjs --interact`, `acceptance.py`), run in the sandbox (`sandbox_runner`, image v10) | deterministic | `tests/test_interact.py` (fixtures: good, no handler, no Escape, covered, no aria-controls, dead classes, duplicate ids), `tests/test_sandbox_runner.py` ✅ |
| 6 | Agent loop (`interact_loop.py`) | Nemotron + sandbox | `tests/test_interact_loop.py` ✅ — lambda perception path in the sandbox: **6/6 pass** (first draft 0/6, revision 6/6) |
| 7 | Ablation: no interaction · deterministic fallback (compiler's inline menu-link toggle) · Nemotron writer | — | numbers per state frame |

## Gates (re-planned Oct 2)
- **Gate A (~Oct 5)**: stages 1–6 on lambda's mobile menu end to end; generated tests pass; state-frame score ≥ 75;
  static score unchanged; cost ≤ $0.15/run.
  Oct 2 measurement (sandbox, perception path, 6 runs, image v10): end to end ✓ (mobile **and** tablet), tests pass
  6/6, state scores mobile 87.2 / tablet 84.4, static render pixel-identical (test), $0.0042 + ~16 s sandbox per run.
  **Criteria met — council review pending before it counts as passed.**
- **Gate B (~Oct 8)**: overlay + drawer + inline (accordion/tabs) on dev pages; ablation shows Nemotron ≥ +10 on
  state frames over the deterministic fallback.
- **Gate C (~Oct 11)**: Hafsa's original screens with state frames. Feature freeze Oct 18 (unchanged).

## Working rule (Hafsa, Oct 2)
TDD throughout: every change starts with a failing test (behaviour + edge cases); full suite green before hand-off.
