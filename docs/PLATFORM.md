# Platform facts (verified first-hand)

## G4 — Sandbox smoke (2026-09-29) ✅
| Check | Result |
|---|---|
| `contree images import python:3.12-slim` | SUCCESS, 9 s op / 12 s wall; UUID `ed34f898-9c18-38f8-ae50-f39edc831e98`, tag `python:3.12-slim` |
| `contree run --use tag:python:3.12-slim --disposable -- python3 -c "print(2+2)"` | `4`, 3 s wall |
| CLI run, network default | **ON** — `urlopen('https://example.com')` → 200. CLI 0.9.4 has no network flag |
| API `POST /sandboxes/v1/instances` with `networking:{enabled:false}`, `shell:true`, `timeout:60`, `disposable:true` | 201; spawn→result 2.8 s; run 0.69 s; stdout `NET_BLOCKED URLError` / `4` |
| API response fields | op `uuid`, `status`, `metadata.result.stdout.value`, `metadata.result.state.exit_code/timed_out`, `metadata.result.resources.cost` (0.00217 for this run), `result_image_uuid` (null when disposable) |
| API default `truncate_output_at` | 1,048,576 (1 MiB) |
| CLI global flags | `-o json` goes **before** the subcommand: `contree -o json run ...` |

Script: `gates/g4_api.py`.

## G5 — Render image (2026-09-29) ✅
| Check | Result |
|---|---|
| `contree build sandbox/ --tag pixel-check-runtime:v1` | image `4bacde62-72ec-4391-9802-c1104c720a95`; first build ~100 s, cached rebuild 6 s; `RUN node render.mjs --selftest` passes inside the build |
| Base | `mcr.microsoft.com/playwright:v1.63.0-noble` + npm (exact): react 18.3.1, esbuild 0.25.10, tailwindcss 3.4.17, postcss 8.5.6, playwright 1.63.0; Python numpy/pillow/scikit-image |
| Render via API (network off, non-disposable) | 3 PNGs exact size, Inter loaded, **4–5 s wall**, ~1.1 s VM time, `resources.cost` ≈ 0.012/run |
| Determinism | 2 API runs → identical SHA-256 per breakpoint; also identical to the build-time self-test |
| Network | `http.get('http://example.com')` → `NET_BLOCKED` |
| **stdout cap bug** | `truncate_output_at: 10485760` is echoed back, but stdout (both `GET /operations/{id}` and `/subprocesses/1`) is cut at **exactly 65,536 bytes** with `truncated: false`. Workaround: outputs are files; fetch with `GET /inspect/{image}/archive?path=/work/out` (tar) from the run's checkpoint |
| `contree build` COPY quirk | `COPY file ./` after `WORKDIR /opt/pc` did **not** land in `/opt/pc`; absolute destinations work |
| `contree build` multistage | `--help` (0.9.4) says FROM … AS / COPY --from are supported (docs said no multistage) |
| Spec | Full OpenAPI spec ships in the CLI: `contree_client/spec_info.py` |

## G6 — Branching (2026-09-29) ✅
| Check | Result |
|---|---|
| Parent run (non-disposable) → checkpoint | 3.3 s |
| 3 children forked in parallel from the parent checkpoint | 4.3 s total; each saw `parent` + its own line; 3 distinct checkpoints |
| Parent re-read after forks | unchanged (`parent`) |

Script: `gates/g6_branch.py`. Client: `orchestrator/sandbox.py`.

## G3 — Vision (2026-09-29) ✅ google/gemma-3-27b-it
Test: `gates/g3_vision.py` — 5 dev captures × {desktop, mobile}; ground truth = visible DOM text nodes; match = substring or fuzzy ≥ 0.85; temperature 0; max_tokens 3000; plain JSON requested in the prompt (no `response_format`).

| Model | Recall | Invented | Unparseable | Latency | Tokens in (image) |
|---|---|---|---|---|---|
| **google/gemma-3-27b-it** | **181/189 = 95.8 %** | 7/172 (mostly real text missing from GT: `01/`, placeholders) | 0/10 | 7–30 s | ~372 per image regardless of size |
| openbmb/MiniCPM-V-4_5 | 122/189 = 64.6 % | 4/112 | **4/10** (emits `<think>…` and runs out of tokens, or invalid JSON like `[275 20 345 40]`) | 2–20 s | 316–581 |

Gemma misses: "Netflix" (logo → grey block, correctly unreadable), "Password" (hidden label), "$20" (1 case), "9 days", "Toggle theme" (icon-only aria text). Box accuracy not yet measured.
Decision: **Gemma 3 27B** reads the designs (perceive) and does the visual critique. No NVIDIA VLM on Public endpoints; Nemotron-Nano-V2-12b (Dedicated) still to price.

## Live mode from a URL — network guardrails (Oct 5)
- The page capture runs in a Token Factory sandbox with networking ON (capture only). Pixel-Check blocks private /
  loopback / link-local (incl. 169.254.169.254) / reserved addresses itself: a redirect preflight checks every hop
  before the browser navigates, and every request the page makes is checked (DNS lookup) and aborted if private
  (`tools/capture/capture.mjs --block-private`); the API re-checks the final URL, every hop and the server IP.
- We did **not** probe whether a networking sandbox can reach the provider's metadata service or private ranges —
  that would be testing Nebius's infrastructure without authorisation. Open question for Nebius (FEEDBACK):
  are sandbox egress rules restricting internal addresses?
- Real guarded capture: hafsausmani.com in 19 s, navigation recorded, nothing blocked, verification passed.
