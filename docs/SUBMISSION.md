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

**Tagline (≤ 200 chars):** AI writes UI that looks right at one size. PixelCheck proves whether it's right at every size — and tells you what to fix.

**Built with:** Nebius Token Factory · Token Factory Sandboxes · NVIDIA Nemotron 3 Super · NVIDIA Nemotron 3 Ultra ·
Gemma 3 27B · Python · FastAPI · Playwright · Tesseract · React · Tailwind CSS · TypeScript · Vite · Render · Vercel

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
  that cheap; renders are byte-identical across runs.
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
  phone (38: text 11 % smaller, spacing 20 % tighter, Roboto instead of Lato). PixelCheck said so in under a minute for
  about $0.05, and Nemotron's brief said exactly what to change. Four repeat runs gave identical scores.
- Audits of three of our own deployed apps found a platform badge over part of a primary button and seven texts lost on
  phones.

### What we learned
Measurements make a language model useful and safe here: Nemotron is good at turning numbered facts into instructions
a builder can follow; a verifier is what makes them trustworthy.

### What's next
Per-band alignment in the scorer (pre-registered, red-teamed before it ships); full-page scoring; a CLI so an AI
coding agent can check its own UI at every size before it says "done".

### Testing notes (for judges)
- Replays work without any login: home page → **Replay a run** → *Dashboard built by Lovable* and the audits.
- Live mode needs no passcode: open the site and run a check. The live server runs on Render's free plan: after 15 idle
  minutes it sleeps, so the first live request waits up to a minute while it wakes (the site says "Waking the live
  server…"). A check then takes about a minute. Replays need no server.

---

## 3. Video script (≤ 3:00, screen recording + voice)

Say "Nebius Token Factory" and "NVIDIA Nemotron" aloud at least twice each. No music with rights issues.

| Time | Screen | Voice |
|---|---|---|
| 0:00–0:15 | Lovable build on a laptop, then the same page on a phone frame | "I gave an AI builder my three design frames. On my laptop it looks right. On a phone, is it?" |
| 0:15–0:30 | PixelCheck home → Check a build: three frames + the Lovable URL | "PixelCheck holds a build to its design frames — at every designed size and every width in between." |
| 0:30–0:45 | Progress: capture → read design → measure → fix brief | "It captures the build in a Nebius Token Factory Sandbox, then scores it in a separate sandbox with the network off — the only place my designs go." |
| 0:45–1:15 | Result: score ring "Same layout, drifting", 38 / 61 / 65, width strip all green, "Why mobile scored 38" | "Desktop and tablet are close. Phone drifted: text 11 percent smaller, spacing 20 percent tighter, the wrong font. It doesn't overflow — it's just not my design." |
| 1:15–1:30 | Side by side + drift line, "1h 20m — 152 px higher" chip | "And it shows where: by the bottom of the screen everything sits 150 pixels higher." |
| 1:30–2:00 | "What to do next": brief, fact chips (hover), "What the check dropped, and why" | "NVIDIA Nemotron 3 Super turns those measurements into a fix I can paste into my AI builder. Every line cites a measurement — and a verifier outside the model drops anything it can't back up." |
| 2:00–2:20 | (If done) Lovable after the brief → re-check score; otherwise the copy button + paste into Lovable | "One message later…" / "Paste it, rebuild, check again." |
| 2:20–2:40 | Audits: Interview Sage card → badge over "Generate Questions", 7 texts lost on phones | "No designs? Audit any page: width breaks, platform badges over your buttons, text a phone loses." |
| 2:40–3:00 | README "Built with" line / logo | "PixelCheck: design frames are the spec, Nebius Token Factory Sandboxes measure, NVIDIA Nemotron tells you what to fix." |

---

## 4. Claims we can and can't make (from our reviews)
- ✅ "Given all three frames, Lovable's first output matched desktop and tablet closely but drifted on phone."
- ✅ Whole numbers (38 / 61 / 65), "one example", "a verifier drops claims the measurements don't back".
- ❌ "Lovable fails", "breaks on mobile", "38 % accurate", any ranking of tools, "pixel-perfect".
- ❌ "Repair works" — Repair is experimental, benchmark pending.
