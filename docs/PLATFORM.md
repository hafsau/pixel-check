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
