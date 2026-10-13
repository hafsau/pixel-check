# PixelCheck

**One codebase. Every breakpoint. Verified.**

PixelCheck turns a screen's three design frames — your own exports, phone / tablet / desktop widths, any height —
or your own live page into **one responsive React + Tailwind codebase**, then **proves** it: every candidate is
rendered and scored at the frames' own sizes and at the widths in between inside **Nebius Token Factory
Sandboxes**, with models served by **Nebius Token Factory** — **NVIDIA Nemotron 3 Ultra** plans responsive intent,
**NVIDIA Nemotron 3 Super** names page regions and makes the repair agent's edits, and Gemma 3 27B reads the design
frames.

AI-generated UI usually looks right at one size. PixelCheck measures it at every size — and can check a build
someone else made and try to repair it (repair is experimental: its benchmark is pending, see
[`docs/REPAIR.md`](docs/REPAIR.md)).

> Built solo for the Nebius × NVIDIA Global AI Hackathon (track: Coding and Agentic Engineering).
> Demo: _(Vercel URL — added at deploy)_ · Video: _(YouTube — added at submission)_

---

## What it does

| Mode | Input | Output |
|---|---|---|
| **Rebuild** | 3 design frames as you export them (PNG / JPEG / WebP, 320–1600 px wide, any height; labelled by width, full pages scored on their first screen), or a URL of a page you own | One responsive React + Tailwind `App.jsx` (or a runnable Vite project), scored per size, with a width sweep. For your own site: your real images back in the delivered code |
| **Check** | 3 design frames + any build (a public URL or an `App.jsx`) | How close the build is at the frames' own widths, whether it breaks in between (360 / 375 / midpoints / 1600 px) and why, which text is missing. Your code is not changed (a URL is captured as it looks, with animations stopped and scrollbars hidden; an `App.jsx` must be one React + Tailwind file and is rendered offline with the default Tailwind theme and the fonts it names from PixelCheck's catalogue — remote images and fonts don't load) |
| **Repair** _(experimental)_ | A check of an `App.jsx` | Nemotron edits Tailwind classes size by size (it cannot add, move or delete elements, but it can restyle, hide or reorder them), the sandbox re-checks, the best round is kept — or your code comes back unchanged. Benchmark pending: [`docs/REPAIR.md`](docs/REPAIR.md) |

Every run can be replayed in the web app: the design, each candidate's renders, the score per size, the width
strip, the model calls and their cost.

## How it works

```
design frames ─┐
  (or a URL ──── capture in a sandbox, network on, behind URL guards)
               ▼
  perception: Gemma 3 27B reads the text and roles  +  Tesseract OCR and pixel measurement
               (boxes ±1–6 px, colours, borders, radius, soft shadows, gradients, photos → placeholder blocks,
                the font of each text line from 16 open families, size / weight / spacing in that font's metrics)
               ▼
  fluid compiler: bands, rows, grids, columns, layers → one responsive App.jsx (standard Tailwind screens for the
     frames' widths — e.g. 402 / 768 / 1071 → base / md: / lg: — no per-size copies)
     + Nemotron 3 Ultra: responsive intent (repeated cards, centred vs full-bleed) — adopted only if verified no worse
     + Nemotron 3 Super: semantic regions (header / nav / main / section / footer)
               ▼
  Token Factory Sandbox (network off): esbuild + Tailwind → Chromium at the frames' sizes and 360–1600
               ▼
  disposable scoring fork (the only place the design frames enter): score per size → worst size = Match
```

- **Code-writing models never see the design images** — only text measurements. The frames enter only the
  disposable scoring run.
- **Anti-cheat**: a static lint (no `<img>`, `url(`, `data:`, canvas, iframes, per-breakpoint copies of the same
  text, no arbitrary breakpoints such as `min-[402px]:max-[403px]:` that would pin a layout to one measured width) and runtime integrity checks (same DOM at every size, ≤ 30 % positioned elements, no traced layouts, no
  hidden-text stuffing). A cheat scores 0. Red team: 389 attack candidates, best attack 46. (Check mode measures
  someone else's code and applies no anti-cheat verdict.)
- **Interactions** (development only — not in the demo): from a state frame (menu open, tab selected), Nemotron 3
  Ultra wrote the wiring and the sandbox clicked, pressed Escape and tabbed through it; with measured facts, a
  deterministic template wired the same menus.
- **Check & repair**: the build is captured (URL) or rendered (`App.jsx`) in the sandbox and scored against the
  frames; the repair agent turns the measured report (per-size text and box offsets, missing text, the element that
  is wider than the screen, structure hints) plus the design spec into size-scoped class edits, three candidates per
  round, each size keeping the edits that improved it.

### The score
Per size (all parts in [0, 1]):

    S = 100 × (0.25 + 0.75·colour) × (0.5 + 0.5·text) × (0.57·structure + 0.43·layout)
    Match = min(S_mobile, S_tablet, S_desktop)

structure = edge-energy F1 at 2–16 px tolerance; layout = min(precision, recall) of content cells; colour = share of
the page whose colour matches; text = target strings readable in the render (pixel-checked, near their design
spot). The width sweep at 360 / 375 / 500 / 1024 / 1600 px fails on sideways scroll, new text overlaps, content
drifting off-centre or the page background ending early. Details: [`docs/SCORING.md`](docs/SCORING.md).

## Results (only pages we may publish)

| What | Result |
|---|---|
| **hafsausmani.com** (the author's own site), live run from its URL — replay in [`ui/published/hafsausmani-home`](ui/published/hafsausmani-home/run.json) | worst size **87.4** (mobile 94.6 · tablet 92.9 · desktop 87.4), width sweep pass; **~33 s** end to end with the design reading cached (compile + render + score 14 s; an uncached reading adds 13–30 s); model **$0.0022** (+ ~$0.001 for an uncached reading) and sandbox ~$0.04; the delivered code shows the site's real headshot and icon |
| **Check-mode sanity check**: hafsausmani.com checked against its own screenshots (a reproducibility test, not accuracy on a different build) — [`docs/results/hafsausmani-self-check.json`](docs/results/hafsausmani-self-check.json) | **99.8 · 99.9 · 99.9**, no missing text, width sweep pass |
| **Repair benchmark** on builds generated by other tools from original designs | _pending_ — the bar was committed before any repair run (commit `c2f9412`): [`docs/REPAIR.md`](docs/REPAIR.md) |
| **Original design: the author's fitness dashboard** — her own exports as they are (402 × 2453, 768 × 1936, 1071 × 1177; Lato; stock photos, gradients) | **Live pipeline in the sandbox** (Oct 13): worst size **59.95** (mobile 66.2 · tablet 60.1 · desktop 60.0), width sweep pass, Lato detected; 58 s end to end, $0.16 all-in ($0.0067 models). After the element fixes that followed (avatar, gradient tiles, chart bars, progress bar, button label): **62.5** (68.2 · 62.5 · 66.6), local measurement. All on the first screen of each frame |
| **hafsausmani.com with its own fonts** (Space Grotesk + JetBrains Mono; its Moche headline face is commercial and gets an open stand-in) | **54.5** (78.8 · 71.9 · 54.5), local measurement (Oct 12). Not comparable with the 87.4 above, where both the site and the rebuild were normalised to Inter |

During development we measured on captures of public third-party pages. They are not reported as results here:
the pages are not ours to publish (some development measurements appear in `docs/FEEDBACK.md` as tool feedback).

**Cost**: a rebuild is ~$0.002–0.01 in model calls plus ~$0.05 of sandbox time; a check ~$0.001 (design reading)
+ sandbox; a repair ~$0.02–0.04 in model calls + up to 13 sandbox checks — about **$0.55** in all, mostly sandbox time.

## Limits (stated plainly)
- Frames are scored on their **first screen** (a full page taller than 1.5 screens is cropped for scoring; the
  whole page is kept for display). Full-page scoring needs a different scorer and is not done yet.
- **Fonts**: 16 open-licence families (Inter, Lato, Roboto, Open Sans, Poppins, Montserrat, DM Sans, Source Sans 3,
  Space Grotesk, Manrope, Nunito Sans, Work Sans, Plus Jakarta Sans, IBM Plex Sans, IBM Plex Mono, JetBrains Mono).
  Commercial fonts (SF Pro, Helvetica, Avenir, …) cannot be shipped: the closest open family is used and named.
- **Photos** become placeholder blocks in scored code (code never embeds images); on your own site the delivered
  code puts your real images back.
- Text is Latin-script only (OCR and the fonts).

## Safety in URL mode
Public http(s) pages only, with "I own this page or have permission" confirmed. Every resolved address must be
public (no localhost, private, link-local or metadata addresses); redirects are followed by hand and every hop,
the final URL at every size and the server IP are re-checked. Pages with password, one-time-code, payment, IBAN,
seed-phrase or sign-in fields are refused, and so are banking, payment, crypto, government, healthcare and sign-in
sites and look-alike addresses. Rebuilt code from someone else's page carries an attribution header and no
images. Not a security guarantee — the UI says so.

## Prior art and what PixelCheck adds
- **imugi** — a visual feedback loop for one viewport. **VisRefiner**, **UI2Code^N** — screenshot to code with
  visual refinement, single screenshot. **MobileForge** — multi-page apps, not breakpoints. A Hugging Face dataset
  of 3-viewport screenshots — training data, not an agent.
- PixelCheck adds: **one** codebase verified against **three** frames at once and across the widths in between,
  scored in isolated sandboxes with anti-cheat; checking builds made elsewhere (and an experimental repair agent);
  and replays of every run.
- We do not claim to be the first agent that checks its work visually.

## Run it locally
Requirements: Python 3.12, Node 20+, Tesseract 5, a Nebius Token Factory key with Sandboxes access.

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # NEBIUS_API_KEY, NEBIUS_AI_PROJECT
(cd sandbox && npm ci) && (cd tools/capture && npm ci && npx playwright install chromium) && (cd ui && npm ci)
LIVE_ENABLED=1 LIVE_PASSCODE=choose-one .venv/bin/uvicorn orchestrator.api:app --port 8000
(cd ui && npm run dev)          # http://localhost:5173 → Live run / Check a build
```

Tests: `.venv/bin/python -m pytest tests` (Python) and `(cd ui && npm test)` (web app). Deploy: [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Repository
`orchestrator/` pipeline, API, compiler, perception, repair · `sandbox/` the runtime image (renderer, lint, scorer)
· `tools/capture/` URL capture and guards · `ui/` web app · `tests/` · `docs/` scoring, platform facts, feedback,
deploy, repair pre-registration.

## Built with
Nebius Token Factory · Token Factory Sandboxes · NVIDIA Nemotron 3 Ultra · NVIDIA Nemotron 3 Super · Gemma 3 27B ·
Tesseract · React · Tailwind CSS · Vite · Playwright · Python · FastAPI · Render · Vercel

Feedback on each tool (required): [`docs/FEEDBACK.md`](docs/FEEDBACK.md).

## License
[MIT](LICENSE)
