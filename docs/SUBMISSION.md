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

**Tagline (≤ 200 chars):** AI writes UI that looks right at one size. PixelCheck tests it at every size in Nebius sandboxes, and NVIDIA Nemotron writes the verified fix.

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

## 3. Video script (≤ 3:00, screen recording + voice)

Before recording: open https://pixel-check-peach.vercel.app 2 minutes ahead so the free server is awake (no cold start
on camera). Label sped-up parts "sped up". Say "Nebius Token Factory" and "NVIDIA Nemotron" aloud at least twice each.
No music with rights issues. Record the Lovable result from the published replay (its numbers match the README:
38 / 61 / 65, text 11 % smaller) — or say "about 11 to 15 percent" if you record a live run.

| Time | Screen | Voice |
|---|---|---|
| 0:00–0:15 | Lovable build on a laptop, then on a phone frame | "If you build with AI — Lovable, v0, Bolt — your page looks right on your laptop. On a phone, is it still your design?" |
| 0:15–0:30 | PixelCheck home → Check a build → **Try the example** | "PixelCheck is the test step AI coding agents skip. Your design frames are the spec; it checks the build at every size and every width in between." |
| 0:30–0:45 | Run check → progress (label "sped up") | "It captures the build in a Nebius Token Factory Sandbox, then scores it in a separate sandbox with the network off — the only place my designs go." |
| 0:45–1:15 | Result: "Same layout, drifting", 38 / 61 / 65, width strip, "Why mobile scored 38" | "Desktop and tablet are close. Phone drifted: smaller text, spacing 20 percent tighter, the wrong font. Nothing overflows — it's just not my design." |
| 1:15–1:30 | Side by side + drift line, "1h 20m — 152 px higher" chip | "And it shows where: by the bottom of the screen everything sits 150 pixels higher." |
| 1:30–2:00 | "What to do next": brief, fact chips (hover), "What the check dropped, and why" | "NVIDIA Nemotron 3 Super turns those measurements into a fix I can paste back into my AI builder. Every line cites a measurement — and a verifier outside the model drops anything it can't back up." |
| 2:00–2:20 | The loop: paste the brief into Lovable → its rebuild → re-check (if done); otherwise 15 s of Repair on an App.jsx, labelled "experimental" | "Paste, rebuild, check again — the agent gets a test it can't fool." |
| 2:20–2:40 | Audit: Interview Sage card → badge over "Generate Questions", 7 texts lost on phones | "No designs? Audit any page: width breaks, platform badges over your buttons, text a phone loses." |
| 2:40–3:00 | README "Who does what" table / logo | "PixelCheck: design frames are the spec, Nebius Token Factory Sandboxes test every size, NVIDIA Nemotron tells you what to fix." |

---

## 3b. Devpost form answers
- **Links:** demo https://pixel-check-peach.vercel.app · repo https://github.com/hafsau/pixel-check · video _(YouTube)_
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
