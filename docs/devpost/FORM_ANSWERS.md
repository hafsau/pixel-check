# Devpost form — paste-ready answers

Ratings are suggestions based on what we measured. They're Hafsa's call; change them freely.

---

**Upload a file:** leave empty. It's optional, and the repo, demo and video already cover everything.

**Submitter type:** Individual · **Organization:** N/A · **Country:** United States

**Track:** Coding and agentic engineering

**New or existing:** New

**If existing, how you updated it:** leave empty. If the field is required, write:
> N/A: new project. The repository was created on Sep 25, 2026, during the hackathon.

**Public code repository:** https://github.com/hafsau/pixel-check

**Working demo:** https://pixel-check-peach.vercel.app

---

## Which model(s) did you use, and why did you choose that size/variant?

> **NVIDIA Nemotron 3 Super (120B-A12B)** writes the fix brief on every check. It turns about 8 numbered, measured facts into a short summary and a message to paste into an AI builder, and every line cites its facts. I chose Super because this is a structured writing job: it returned valid JSON every time with thinking off, in about 7 s, for about $0.0005 a brief. That's fast and cheap enough to run on every check. Super also names page regions in rebuilds and proposes the class edits for an experimental repair agent.
>
> **NVIDIA Nemotron 3 Ultra (550B-A55B)** plans responsive intent in rebuilds: which elements form repeated cards, and how bands behave beyond the widest frame. It's one call per page ($0.002–0.01), and the plan is only adopted when the sandbox shows it's no worse. Ultra was clearly stronger at layout reasoning than Super (single-shot 39–47 vs about 15 on our scorer), so the larger model goes where the reasoning is hardest and only one call is needed.
>
> **Gemma 3 27B** reads the design frames, because there's no NVIDIA vision model on Token Factory's public endpoints. It won a bake-off of 5 vision models on 12 UI frames: 176 of 183 strings, best end-to-end score, and the cheapest.

## How would you rate Nemotron's output quality for your use case? (1–10)

> **8/10.** Writing instructions from measured facts, Nemotron 3 Super is very good. It turns numbers like "text 11 % smaller on mobile" into clear, followable instructions, it returned valid JSON on every call, and it's fast.
>
> **Where it fell short:**
> - **Format instructions:** it doesn't reliably follow rules like "start every instruction with the screen size". It sometimes turned a mobile-only fact into an instruction with no size.
> - **Overclaiming:** it occasionally overreached, for example "causing multiple text elements to sit higher" or "making it inaccessible", and it varied its quoting style.
>
> A rule-based verifier outside the model catches all of these and shows the user what it dropped. With that verifier, on the real Lovable check 3 of 4 claims were kept, each backed by a measurement.
>
> On pixel-precise code from a numeric spec, Super was weak (median about 15 on our scorer), and our deterministic compiler beat both Super and Ultra there. So I use Nemotron for language and planning, not for pixel geometry.

## Did you fine-tune, prompt-engineer, or use Nemotron out of the box? What was your approach?

> **Prompt engineering plus a deterministic verifier. No fine-tuning.**
>
> - **Input is measured facts only.** The model gets numbered facts (F1, F2, …) computed from sandbox measurements: text size, spacing drift, font, warnings. It never sees an image.
> - **Settings and output:** thinking off and temperature 0.3, with a JSON schema for the output (summary items and paste-ready instructions, each with the fact ids it cites).
> - **Prompt rules** come from failures we saw: name the screen size in every instruction, never narrow a whole-page finding to one size, no positioning advice that spacing drift already explains, no advice to move platform badges, and no cause words.
> - **A verifier outside the model** checks each line:
>   - it must cite known facts;
>   - its numbers must match those facts, with units and a tolerance;
>   - its quotes must appear in the facts, and the sizes it names must be covered by them;
>   - it drops overclaim and cause words.
>
>   Any actionable fact left without a line gets a template line. If the model fails, the whole brief falls back to a template.
> - **Shown to the user:** the page shows which claims were dropped, and why.

## How did Nemotron's performance compare to other models you've used for similar tasks?

> - **Super vs Ultra:** for structured jobs (the fix brief, region names, JSON edits), Super was the best fit: 10/10 valid JSON with thinking off, about 1 s on short prompts, about 7 s for a brief. For layout reasoning, Ultra was clearly better than Super on the same spec (single-shot 39–47 vs about 15). Both lost to a deterministic compiler on pixel-precise code.
> - **Reasoning modes:** in our tests, all three reasoning modes still returned valid JSON. With large reasoning budgets, though, some code generations returned no answer within `max_tokens`.
> - **Vision models (for comparison):** Gemma 3 27B beat DeepSeek-V4.1-Flash, GLM-5.3-Flash, MiniCPM-V-4.5 and Kimi-K2.6 on our UI-frame bake-off. Kimi returned empty answers on 9 of 12 frames while billing reasoning tokens.

## Which Nebius platform capabilities were most valuable to your project and how?

> **1. Token Factory Sandboxes.** They're the backbone. Every build is captured in one sandbox with the network on, then scored in a **disposable sandbox with the network off**, the only place the design frames ever go. So the build can't see the answer or grade itself.
> - **Checkpoints and forks:** 3 parallel forks start in about 4 s.
> - **Per-run network switch:** that's what makes the anti-cheat design simple.
> - **Determinism:** renders are byte-identical across runs and across 9 image rebuilds, so scores stay comparable.
> - **Custom images:** `contree build` built our runtime image.
>
> **2. The Token Factory inference API.** One key and one OpenAI-compatible endpoint (`api.tokenfactory.nebius.com/v1`) gave us Nemotron 3 Super, Nemotron 3 Ultra and Gemma 3 with no GPU setup at all. It's serverless, so there are no instance types to manage.
> - **Live prices:** `GET /v1/models?verbose=true` returns per-token prices, which feed our app-level spend cap directly.
> - **Metered sandboxes:** every sandbox run reports `resources.cost`, so each check's cost is shown to the user (about $0.05).
>
> **Hosting:** our API runs on Render's free plan and the web app on Vercel. All model and sandbox work happens in Token Factory.

## How likely are you to recommend running Nemotron on Nebius to other developers? (1–10)

> **8/10.**
>
> **Why I'd recommend it:**
> - Getting started is easy: the endpoint is OpenAI-compatible, the standard client worked unchanged, and I made my first valid call on day one.
> - It's cheap: about 1,200 model calls cost under $5 by Oct 7.
> - Sandboxes next to the models make write → run → test loops natural.
>
> **What held it back from higher:**
> - There's no billing alert or spend limit in the console, so I had to build my own cap.
> - Vision calls have a long latency tail (median 13–25 s, worst 293 s).
> - Sandbox access was a separate beta (about 3 days' wait), and there was a 64 KiB stdout cap that reported `truncated: false`.

## How would you rate your experience running Nemotron inference on Nebius compared to previous cloud or local environments? (1–10)

> **8/10.** It's much simpler than hosting a 120B–550B model myself: no GPUs, no serving stack, per-token pricing, and live prices from the API.
>
> The reasons it's not higher:
> - **No spend controls:** there are no alerts or hard stops.
> - **Unpredictable latency:** there's no published latency target, and no queue or priority signal on slow calls.
> - **Catalogue errors:** Nemotron 3 Super and Ultra showed "0B" parameters, and Gemma 3 is listed as `text->text` although it reads images.

## What additional features or improvements would have made the Nemotron on Nebius experience more effective for your project?

> - **An NVIDIA vision model on public endpoints.** Nemotron-Nano-V2-12b and Cosmos3-Super-Reasoner are Dedicated-only, so my design reading had to use Gemma.
> - **Spend controls:** a billing alert at a user-set threshold, an optional hard stop, and a sandbox-vs-inference split in the console.
> - **Latency:** published latency targets, or a queue-position or priority header.
> - **Constrained decoding:** `json_schema` with an array of mostly optional objects made Super return `{"calls": []}` every time, while the same prompt without the schema gave 18 good calls. Bias against the empty array, or document it.
> - **Reasoning budgets:** guidance on sizing `max_tokens` vs `reasoning_budget`, so reasoning doesn't use up the whole answer budget.
> - **Sandboxes:**
>   - network off by default in the `contree` CLI;
>   - fix the 64 KiB stdout cap (and the `truncated: false` flag);
>   - document how sandbox time is billed;
>   - say whether `contree build` honours `.dockerignore`.

## What do you most hope to see from the Nemotron team next?

> - **A Nemotron vision-language model on Token Factory's public endpoints**, good at reading UI screenshots (text, layout, roles). It would let a UI tool like PixelCheck run entirely on NVIDIA models.
> - **Stronger format-following**, for example "every instruction must start with the screen size".
> - **A small, fast Nemotron tuned for verification**, checking that a claim is supported by given facts. It would pair well with Super as the writer.

## Did you use Tavily in your project?

> **No.**

## Builders & Brews – IRL Events City

> **Check this one.** The field says it's for people **attending** one of the 20 IRL events. Keep San Francisco only if you attended, or if the rules say attendance isn't required. Otherwise, leave it blank.

## Which AI tools have you leveraged while working on this project?

> - **Claude Code (Anthropic)** was my coding agent for building and testing PixelCheck, with test-driven development and independent review rounds before any claim.
> - **Lovable** generated the AI build of my dashboard that PixelCheck checks, from my three frames and one prompt, taking its first output.
> - **In the product:** NVIDIA Nemotron 3 Super and Ultra and Gemma 3 27B, all on Nebius Token Factory.

**Level of learning:** Significant · **AI value for your career:** Yes · **Age checkbox:** ticked
