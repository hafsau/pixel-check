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
| 1 | `states.state_diff(base, state)` → appeared / disappeared / moved / persisted, kind (overlay · drawer · inline · none), panel box | deterministic | `tests/test_states.py` (12, incl. real lambda menu) ✅ |
| 2 | Trigger resolution: trigger box/label → element id in the compiled base (`data-pc`) | deterministic | duplicate labels, icon-only triggers, trigger absent at a bp |
| 3 | Panel content: compile the appeared elements with the fluid compiler into a JSX fragment (per-bp, same classes as the page) | deterministic | fragment compiles, lints, contains every appeared text |
| 4 | **Interaction writer (Nemotron)**: given base App.jsx, trigger id, kind, panel fragment, diff → edits App.jsx: state + handlers + mounting (overlay `fixed inset-0`, drawer side panel, inline insert) + a11y (aria-expanded/controls, Escape, focus) | **Nemotron** | output parses, lints, keeps static layout byte-identical outside the edit |
| 5 | Acceptance tests generated from the state frames, run in the sandbox (`render.mjs --interact`): base matches; click trigger → state frame score ≥ threshold; click/Escape → back to base; keyboard Enter works; aria-expanded toggles | deterministic | harness tested on fixture components (toggle, drawer, accordion) incl. failing fixtures |
| 6 | Agent loop: write → run tests → feed failures back → revise (≤ 3 attempts), verified adoption | Nemotron + sandbox | loop stops on pass, never adopts a version that breaks the static score |
| 7 | Ablation: no interaction · deterministic fallback (compiler's inline menu-link toggle) · Nemotron writer | — | numbers per state frame |

## Gates (re-planned Oct 2)
- **Gate A (~Oct 5)**: stages 1–6 on lambda's mobile menu end to end; generated tests pass; state-frame score ≥ 75;
  static score unchanged; cost ≤ $0.15/run.
- **Gate B (~Oct 8)**: overlay + drawer + inline (accordion/tabs) on dev pages; ablation shows Nemotron ≥ +10 on
  state frames over the deterministic fallback.
- **Gate C (~Oct 11)**: Hafsa's original screens with state frames. Feature freeze Oct 18 (unchanged).

## Working rule (Hafsa, Oct 2)
TDD throughout: every change starts with a failing test (behaviour + edge cases); full suite green before hand-off.
