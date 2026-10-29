# PixelCheck demo video — script (simple version)

One story, in order: the problem → a real AI build → PixelCheck checks it → the result → what to fix → a URL-only audit → close.
Four tabs, nine scenes, about 2:40.

**How to read this:** every scene has DO lines and SAY lines. Start each SAY line as you start its DO line.
When a DO line says "hands off", just talk.

---

## Before you record

**Chrome:** about 1440 px wide, zoom 100 %, DevTools closed, notifications off.
Use full screen (Cmd+Ctrl+F) so the tabs and address bar are hidden. Cmd+1…5 still switch tabs.

**Open these tabs, in this order:**

| Tab | Open | Leave it at |
|---|---|---|
| 1 | `file:///Users/hafsa/Nebius/pixel-check/docs/video/title-slide.html` | The title slide. Press **Space** to replay its width sweep. |
| 2 | https://adaptable-hub-central.lovable.app | The top of the page. If the "Edit with Lovable" badge shows, close it with its ×. |
| 3 | https://pixel-check-peach.vercel.app/check | The top, empty form. Wait for the green "Live mode on" chip: that means the server is awake. |
| 4 | https://pixel-check-peach.vercel.app/check/interview-sage-audit/replay | Scrolled so the Replit-badge warning and the "Mobile hides 7" chips are both in view. |
| 5 (backup) | https://pixel-check-peach.vercel.app/check/lovable-dashboard-check/replay | The top. Use it only if the live run fails (see the end). |

**Wake the server** 3–5 minutes before you start: open tab 3 and wait for the green chip.
The free server allows 3 live runs per person and 5 in total until it next sleeps.

---

## The script

### 1 · Hook — title slide (0:00–0:17)
- **DO:** Tab 1, the title slide. Hands off.
- **SAY:** "AI can build a page that looks right on a laptop, and is a hundred and fifty pixels off your design on a phone. Nothing overflows, so nothing warns you. I'm Hafsa Usmani, and this is PixelCheck: the test step AI coding agents skip."

### 2 · The AI build (0:17–0:28)
- **DO:** Cmd+2. Scroll the dashboard slowly down.
- **SAY:** "Here's a real one. I gave Lovable my phone, tablet and desktop designs with one prompt, and took its first output. On a laptop, it looks right."

### 3 · Start the check (0:28–0:40)
- **DO:** Cmd+3. Click **Try the example**.
- **SAY:** "PixelCheck uses my three design frames as the spec, and that Lovable page as the build."
- **DO:** Scroll down a little. Click **Run check**.
- **SAY:** "Every build is captured and scored in Nebius Token Factory Sandboxes."

### 4 · While it runs (sped up in the edit) (0:40–1:02)
- **DO:** Hands off. The stages tick down the list.
- **SAY:** "One sandbox captures the build. A second, disposable sandbox scores it with the network off; it's the only place my design frames go. The build can't see the answer, or grade itself. Then NVIDIA Nemotron three Super, on Nebius Token Factory, writes a fix brief. The whole check takes about a minute and costs about five cents."

### 5 · The verdict (1:02–1:17)
- **DO:** The result loads. Point at the **Mobile 38.5** bar.
- **SAY:** "On a phone, it scores thirty-eight and a half out of a hundred against my design."
- **DO:** Move the cursor along the eight green **Every width** cells.
- **SAY:** "Yet every width, from three-sixty to sixteen hundred pixels, is green. It fits. It doesn't match. An overflow check would pass it."

### 6 · Why (1:17–1:35)
- **DO:** Scroll down one screen. Point at **What differs** (left).
- **SAY:** "Here's why: Roboto instead of Lato, text eleven percent smaller, spacing twenty percent tighter."
- **DO:** On the right, click **Overlay** and drag the slider slowly across.
- **SAY:** "By the bottom of the screen, the build sits a hundred and fifty pixels higher than my design."

### 7 · What to fix (1:35–2:00)
- **DO:** Scroll back up. In **What to do next**, hover the **F2** chip.
- **SAY:** "NVIDIA Nemotron turns those measurements into three instructions to paste back into Lovable. Each one cites a measured fact."
- **DO:** Click **What the check dropped, and why**.
- **SAY:** "A rule-based check outside the model removes anything the measurements don't support. Here, it dropped a sentence that guessed at a cause."
- **DO:** Click the copy icon.
- **SAY:** "So what I paste back is backed by the numbers."

### 8 · No design files (2:00–2:15)
- **DO:** Cmd+4. Point at the Replit badge warning, then at the **Mobile hides 7** chips.
- **SAY:** "No design files? Give it just a URL. On my own Replit app, it found the platform badge covering part of the main button on phones, and seven pieces of text that disappear on phones."

### 9 · Close — title slide (2:15–2:40)
- **DO:** Cmd+1. Press Space once to replay the sweep. Hands off.
- **SAY:** "PixelCheck can also rebuild: it writes one responsive React and Tailwind codebase from your frames, then runs and tests it in the same sandboxes. Measured in Nebius Token Factory. Explained by NVIDIA Nemotron. Designed once. Verified everywhere."

---

## Editing (only four things)

1. **Speed up scene 4** (the wait, about 55 s real) so it fits under the voice. Put a small "sped up" label in a corner while it plays.
2. **Zoom in** (about 1.5×) on: the 38.5 bar, the green cells, "What differs", the F2 tooltip, the dropped sentence, and the Replit warning.
3. **Blur Lovable's logo** if the "Edit with Lovable" badge appears anywhere, including the build image in scene 6.
4. **No music**, or royalty-free only.

## If the live run goes wrong
- **It stalls past about 90 s, or the runs are used up:** go to tab 5 (the replay of the same check) and do scenes 5–7 there with the same actions.
- **Nemotron's wording differs:** the numbers stay the same, but the wording can change. Say what's on screen. If there aren't three instructions, say "a short list of instructions". If the "What the check dropped" toggle is missing, use tab 5 for scene 7.
- Never say a number that isn't on screen.

## Checks
- "Nebius Token Factory" is said 3 times (scenes 3, 4 and 9). "NVIDIA Nemotron" is said 3 times (scenes 4, 7 and 9).
- 351 spoken words: about 2:30 of speech at 140 words a minute, and about 2:45 with the actions. That's under 3:00.
- If a take runs long, cut the first sentence of scene 9 (the Rebuild line, about 9 s).
