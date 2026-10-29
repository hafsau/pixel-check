# PixelCheck — submission pack (Devpost, video, finish line)

Deadline Fri Oct 30, 10:00 AM PT · our target **Wed Oct 28**. Track: **Coding and Agentic Engineering**.
Numbers below are the real ones from our runs (Oct 20); quote whole numbers.

---

## 1. Finish line

| When | What | Who |
|---|---|---|
| Oct 21 | Lovable card + replay published, feedback file complete, this pack | Claude ✅ |
| Oct 21–22 | Optional before/after: paste the fix brief into the same Lovable project (one message, first output), publish → Claude re-checks | Hafsa (15 min) |
| Oct 22–23 | Deploy: Render (API) + Vercel (web app) — `docs/DEPLOY.md`; Claude verifies the live site end to end | Hafsa (≈ 20 min) + Claude |
| Oct 23–24 | Record the video from the script below (screen recording + voice) | Hafsa |
| Oct 24 | Repo public: `gitleaks detect` on full history, MIT detected in GitHub's About panel, fresh-clone test, tag `v1.0-submission` | Claude (Hafsa flips "public") |
| Oct 25–26 | Devpost draft from §2–§4; links filled in | Claude drafts, Hafsa pastes |
| Oct 27 | Final check: live demo, replays, video link, model IDs still listed | Claude |
| **Oct 28** | **Submit** | Hafsa |

---

## 2. Devpost text

**Name:** PixelCheck

**Tagline (≤ 200 chars):** AI writes UI that looks right at one size. PixelCheck tests it against your design at every size in Nebius Token Factory Sandboxes, and NVIDIA Nemotron tells you what to fix.

**Built with:** Nebius Token Factory · Token Factory Sandboxes · NVIDIA Nemotron 3 Super · NVIDIA Nemotron 3 Ultra ·
Gemma 3 27B · Python · FastAPI · Playwright · Tesseract · React · Tailwind CSS · TypeScript · Vite · Render · Vercel

### First paragraph (Devpost requires Nebius Token Factory and NVIDIA Nemotron here)
PixelCheck is the test step AI coding agents skip. It runs AI-written UI code in **Nebius Token Factory Sandboxes**,
tests it against the designer's phone, tablet and desktop frames at every width from 360 to 1600 px, and hands a
verified fix back: **NVIDIA Nemotron 3 Super** turns the measurements into instructions you can paste into your AI
builder, and a verifier outside the model drops any claim the measurements don't back.

### Inspiration
AI builders (Lovable, v0, Bolt) turn a design into a working page in minutes. It usually looks right on the laptop you
check it on. On a phone it quietly drifts — smaller type, tighter spacing, the wrong font, a platform badge on top of a
button — and nobody measures that until a user complains. Designers already make phone, tablet and desktop frames.
Nothing holds the build to them.

### What it does
- **Check:** give PixelCheck your three design frames (as exported, any size) and the build — a URL or an `App.jsx`.
  It captures the build at each frame's width and every width in between (360–1600 px), scores how closely each
  matches its frame, and shows *why*: what moved and how far, what's missing, where the spacing drifts, which font is
  wrong, what overflows.
- **What to do next:** **NVIDIA Nemotron 3 Super** turns those measurements into a short fix brief and a message to
  paste into your AI builder. A verifier outside the model drops any claim the measurements don't back — and shows
  what it dropped and why.
- **Audit (no designs):** a URL alone — width breaks, platform badges over your content, text a phone loses.
- **Rebuild (reference):** from the frames, one responsive React + Tailwind codebase that passes the same checks.

### How we built it
- Every capture and score runs in **Nebius Token Factory Sandboxes**: the build is captured with the network on, then
  scored in a **disposable fork with the network off**, the only place the design frames ever enter. Checkpoints make
  that cheap; sandbox renders of the same code are byte-identical across runs.
- **Gemma 3 27B** (Token Factory) reads the frames; OCR and pixel measurement place every text and block.
- The scorer compares edges, layout blocks, colour and text per size (worst size = the headline), hardened in two
  red-team rounds against builds that try to game it.
- **Nemotron 3 Super** writes the fix brief from numbered facts, citing them; a deterministic verifier checks numbers
  and units, quoted text, which screen size each instruction names, and drops overclaims. **Nemotron 3 Ultra** plans
  responsive intent in rebuilds; Super also names page regions and proposes the experimental repair agent's edits.
- 1,160 Python tests and 443 web-app tests; independent review rounds before every claim we publish.

### Challenges
- One global alignment per screen punishes spacing that drifts down the page — we explain the score beside it
  (drift band by band, points lost per factor) rather than changing the score after seeing a result.
- Our first fix briefs looked plausible but weren't safe to paste (a mobile-only fix with no size named; "move the
  badge"). The verifier now catches those, and the review caught that our own badge detector had false positives.

### Accomplishments
- A Lovable build of our own dashboard, given all three frames: close on desktop (65) and tablet (61), drifted on
  phone (38: text 11–15 % smaller, spacing 20 % tighter, Roboto instead of Lato). PixelCheck said so in about a minute
  for about $0.05, and every line of Nemotron's fix brief is backed by a measurement. Repeat runs on one machine gave
  identical scores; the deployed server gave the same rounded scores.
- Audits of three of our own deployed apps found a platform badge over part of a primary button and seven texts lost on
  phones.

### What we learned
Measurements make a language model useful and safe here: Nemotron is good at turning numbered facts into instructions
a builder can follow; a verifier is what makes them trustworthy.

### What's next
Per-band alignment in the scorer (pre-registered, red-teamed before it ships); full-page scoring; a CLI so an AI
coding agent can check its own UI at every size before it says "done".

### Testing notes (for judges)
- No login, no passcode. Fastest path: **Check a build → Try the example → Run check** (about a minute; the example's
  frames were read in advance). An audit of any URL ("No designs?") takes under a minute.
- Replays: home page → **Examples** → *Dashboard built by Lovable* and the audits. If live runs are paused (each
  15-minute wake-up period allows 5 runs), the replays show every result.
- Live mode needs no passcode: open the site and run a check. The live server runs on Render's free plan: after 15 idle
  minutes it sleeps, so the first live request waits up to a minute while it wakes (the site says "Waking the live
  server…"). A check then takes about a minute. Replays need no server.

---

## 3. Video script (council-reviewed final, Oct 26)

> Recorded from the simpler version in [`docs/VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) (Oct 29): https://youtu.be/k2rHocKInfg. The Devpost story and form answers are in [`docs/devpost/`](devpost/).

### PixelCheck: "It fits. It doesn't match." (final script)

**Logline:** An AI build of my dashboard looks right on a laptop but drifts up to 150 px on a phone, with every width green. PixelCheck captures and scores it in Nebius Token Factory Sandboxes, NVIDIA Nemotron writes a fix brief, and a rule-based check outside the model drops a sentence the measurements don't back.

---

## Before you record

- **Tabs 1–4.**
  - (1) https://adaptable-hub-central.lovable.app: top of the page, laptop width.
  - (2) https://pixel-check-peach.vercel.app/check: top, empty form.
  - (3) https://pixel-check-peach.vercel.app/check/lovable-dashboard-check/replay: scroll to "Side by side | Overlay". Select **Mobile**, click **Overlay**, and park the slider at the left edge.
  - (4) https://pixel-check-peach.vercel.app/check/interview-sage-audit/replay: scroll so the Replit-badge warning and the "Mobile hides 7" chips are both in view.
- **Tabs 5–7.**
  - (5) https://github.com/hafsau/pixel-check: "Who does what" table in view.
  - (6) https://pixel-check-peach.vercel.app/: top. Load it last and switch away at once. The hero sweep only advances while the tab is visible.
  - (7) The same replay as tab 3, left at the top of the page. This is the backup.
- **Wake the server 3–5 minutes before each take.** Open tab 2 and wait for the green chip "Live mode on" (with "N runs left today · M left in total" beneath). Do not start a run just to warm the server.
- **Runs budget: 3 live runs per visitor and 5 in total until the server next sleeps** (the counters reset when it sleeps after 15 idle minutes; the chip's counter is server-wide). That allows at most 3 live takes. If they are spent, or the run stalls past about 90 s, cut to tab 7 and do beats 10–15 there with the same actions.
- **Capture the display, not the window.** Window capture misses the native tooltip on chip F2. Set Chrome to about 1440 px wide, zoom 100 %, bookmarks bar hidden, notifications off, cursor highlight on. Use no music, or royalty-free only.
- **Reload tab 6 before the close.** Do it in the cut before beat 20 so the hero sweep starts fresh.
- **Live numbers match the replay** (38.5 / 61.1 / 64.5, 11 %, 20 %) because the frame reading is cached; only Nemotron's wording can vary. Before recording the voice, check: 3 instructions, chip F2 is the mobile text-size fact, and the "What the check dropped" toggle is present.

---

## Script (21 beats · 2:44 · 339 spoken words)

Each line starts as its action starts. Numbers are written the way they are spoken.

| # | Time | ACTION (≤ 10 words) | VOICE |
|---|---|---|---|
| 1 | 0:00–0:08 | Tab 3: drag the Overlay slider slowly left to right. | On a phone, this AI build drifts up to a hundred and fifty pixels off my design. |
| 2 | 0:08–0:11 | Drag the slider slowly back. | And nothing overflows to warn you. |
| 3 | 0:11–0:19 | Cmd+1. Scroll the Lovable dashboard slowly down. | I gave Lovable my three frames and one prompt. On a laptop, its first output looks right. |
| 4 | 0:19–0:25 | Cmd+6. The hero sweeps 360 to 1600; cursor still. | AI agents write the page, then skip the test. PixelCheck is that test. |
| 5 | 0:25–0:32 | Rest the cursor on "Check a build". Don't click. | It's for designers, and anyone shipping UI from an AI builder or coding agent. |
| 6 | 0:32–0:38 | Cmd+2. Click "Try the example". | My three frames are the spec. The build is that Lovable page. |
| 7 | 0:38–0:44 | Scroll down once. Click "Run check". | Every build is captured and scored in **Nebius Token Factory** Sandboxes. |
| 8 | 0:44–0:57 | Hands off. Stages tick, sped up, timer visible. | One sandbox captures the build. A second, disposable sandbox scores it, network off: the only sandbox my frames enter. The build can't see the answer, or grade itself. |
| 9 | 0:57–1:07 | Hands off. "Writing the fix brief (Nemotron)" ticks done. | Then **NVIDIA Nemotron** three Super, on **Nebius Token Factory**, writes the fix brief. This check: about a minute, about five cents. |
| 10 | 1:07–1:14 | Result loads. Point at the Mobile 38.5 bar. | Against my design, on a phone: thirty-eight and a half out of a hundred. |
| 11 | 1:14–1:24 | Glide across the eight green "EVERY WIDTH" cells. | Yet all eight widths, three-sixty to sixteen hundred, are green. It fits. It doesn't match. *(beat)* An overflow check would pass this. |
| 12 | 1:24–1:30 | Scroll about 300 px. Point at "What differs". | Why? Roboto, not Lato. Text eleven percent smaller. Spacing twenty percent tighter. |
| 13 | 1:30–1:38 | Move right. Hover chip F2; hold two seconds. | **NVIDIA Nemotron** turns those numbers into three instructions to paste back. Every line cites a measured fact. |
| 14 | 1:38–1:49 | Click "What the check dropped, and why". | A rule-based check outside the model drops what the measurements don't back. Here: a sentence that guessed at a cause. *(hold 2 s on the struck sentence)* |
| 15 | 1:49–1:55 | Click the copy icon above the message. | What I paste back is a fix brief checked against the measurements. |
| 16 | 1:55–2:04 | Cmd+4. Point at the Replit badge warning. | No design files? Just a URL. On my own Replit app, the badge covers part of Generate Questions on phones. |
| 17 | 2:04–2:10 | Point at the "Mobile hides 7" chips. | And seven texts shown on larger screens are hidden on phones. |
| 18 | 2:10–2:20 | Cmd+5. Point at "(Rebuild)" in the Sandboxes row. | PixelCheck's Rebuild writes one responsive React and Tailwind codebase from your frames, then runs and tests it in the same sandboxes. |
| 19 | 2:20–2:27 | Scroll the README slowly down. | Over sixteen hundred tests. A scorer red-teamed against builds that try to game it. |
| 20 | 2:27–2:37 | Cmd+6 (reloaded). The hero sweeps; cursor still. | AI writes UI that looks right at one size. PixelCheck measures it against your design, and tells you what to fix. |
| 21 | 2:37–2:44 | Hold on "Designed once. Verified everywhere." | Measured in **Nebius Token Factory**. Explained by **NVIDIA Nemotron**. Designed once. Verified everywhere. |

**Wow moments.** Beat 11 is the first: 38.5 on a phone while all eight widths are green ("An overflow check would pass this"). Beat 14 is the second: the check drops a sentence that guessed at a cause.

**Pitch coverage.**

| Element | Beats |
|---|---|
| Problem | 1–4 |
| Who it's for | 5 |
| What it does | 4, 6, 10–15, 20 |
| How Nebius and NVIDIA are used | 7–9, 13–14 |
| Impact | 9 (a minute, five cents), 16–17 (finds real problems from a URL alone), 20 |
| Rebuild, for track fit | 18 |
| Trust | 19 |

---

## Editing notes

- **Opening frame.** Trim the head so the first frame already shows the slider moving. There is no title card and no black frame.
- **The Overlay strip is about 192 px wide.** Zoom it 2× in post for beats 1–2.
- **Sped-up section (beats 8–9): a speed ramp, not a flat speed-up.** Run about 1.8× from the "Run check" click until "Writing the fix brief (Nemotron)" starts (about 23 s real becomes about 13 s, under beat 8). Then run about 3.2× until the result loads (about 32 s real becomes about 10 s, under beat 9), so the stage change lands with the "NVIDIA Nemotron" line.
  - Keep the elapsed timer readable.
  - Put a small "sped up" label in a corner for the whole stretch.
  - The voice runs continuously over it.
  - Beat 8 sits on "Capturing your build" → "Measuring every size". Beat 9 sits on "Writing the fix brief (Nemotron)".
- **Zoom-ins in post (about 1.5–2×).**
  - **Beats 1–3: blur the "Edit with Lovable" badge (Lovable's logo) wherever it shows** — bottom right of the mobile build in the Overlay (beats 1–2, whenever the slider exposes the build) and bottom right of the Lovable page (beat 3). Required: no third-party logos.
  - Beat 10: score ring and Mobile bar.
  - Beat 11: the eight width cells.
  - Beat 12: "What differs".
  - Beat 13: the F2 tooltip.
  - Beat 14: the struck-through sentence. Hold it 2 s.
  - Beat 16: the warning text.
  - Beat 18: the "(Rebuild)" phrase in the README row.
- **Cut points.**
  - Hard cuts at every Cmd+number switch: beats 3, 4, 6, 16, 18 and 20.
  - Beats 6–15 are one continuous live take.
  - Reload tab 6 in the cut before beat 20, and cut out any reload flash.
- **If the live brief differs from the replay, say what is on screen.** The numbers match the replay; only Nemotron's wording can vary.
  - **Number of instructions:** say the count shown. If it isn't three, change "three instructions" to "a short list of instructions".
  - **Chip numbering:** if F2 isn't the mobile font or spacing fact, hover whichever chip cites a mobile measurement.
  - **Dropped sentence:** if the toggle is missing, or its reason isn't "says more than the measurements (overclaim or cause)", redo beats 10–15 on tab 7 with the same actions, labelled "replay of the same check".
  - **Never** say a number that isn't on screen.
- **Voice.** The voice can be recorded live or over the edited picture. Either way, each line starts on its action, with no silent click blocks. If the read runs long, the safe trims are beat 19 (about 7 s) and the word "Yet" in beat 11.
- **Home-page hero (beats 4–5 and 20–21).** The hero switches itself to its "After fix" demo after the first 8-second sweep. Cover the hero card's top bar (caption + Before / After fix toggle) with a paper-coloured box; the stage and headline stay visible.
- **Don't add these.** Do not show or mention the hero's "Before / After fix" toggle. That is the synthetic demo page, and it would imply a before/after that was never run. Do not paste into Lovable's chat, and do not mention Repair or Gemma.

---

## Counts

- **Spoken words: 339.** Numbers are counted as spoken, and hyphenated words count as two ("thirty-eight", "rule-based", "red-teamed"), so this is a conservative count. It is under the 340 cap.
- **Runtime.** Speech alone is about 2:25 at 140 wpm. The beat timeline totals **2:44**, and every line fits its beat at 140 wpm with 0.4–1.4 s to spare (beat 14 fits exactly once its 2 s hold is counted). A natural read lands at about 2:44–2:50, under 2:55.
- **"Nebius Token Factory": 3 times** (beats 7, 9 and 21).
- **"NVIDIA Nemotron": 3 times** (beats 9, 13 and 21).
- **Longest action: 10 words** (beat 1).

---

## 3b. Devpost form answers
- **Links:** demo https://pixel-check-peach.vercel.app · repo https://github.com/hafsau/pixel-check · video https://youtu.be/k2rHocKInfg
- **Track:** Coding and Agentic Engineering · **City:** San Francisco (attendance not required)
- **Pre-existing work:** None; repository created Sep 25, 2026.
- **Built with:** as in §2.
- **Gallery:** `docs/img/check-result.png` (the example result) + a home-page screenshot + the audit result.
- **Feedback:** `docs/FEEDBACK.md` (paste per tool if the form has fields).

---

## 4. Claims we can and can't make (from our reviews)
- ✅ "Given all three frames, Lovable's first output matched desktop and tablet closely but drifted on phone."
- ✅ Whole numbers (38 / 61 / 65), "one example", "a verifier drops claims the measurements don't back".
- ❌ "Lovable fails", "breaks on mobile", "38 % accurate", any ranking of tools, "pixel-perfect".
- ❌ "Repair works" — Repair is experimental, benchmark pending.
