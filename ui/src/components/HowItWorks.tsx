/** The pipeline as it runs today (Oct 5): measured facts → deterministic compiler → sandbox render + score → interactions. */
const STEPS: { name: string; detail: string }[] = [
  { name: 'Perceive', detail: 'A vision model reads the text; OCR and pixel measurement give boxes, colours and type' },
  { name: 'Compile', detail: 'One fluid React + Tailwind file; Nemotron names regions and finds repeated cards' },
  { name: 'Render', detail: 'At 390 / 768 / 1280 px and 5 widths between, in a network-isolated Token Factory Sandbox' },
  { name: 'Score', detail: 'Each render against its frame, 0–100. Match = the worst breakpoint' },
  { name: 'Interactions', detail: 'From state frames: Nemotron writes the wiring, generated tests run in the sandbox' },
];

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" className="section">
      <h2 id="how-title" className="eyebrow">
        How it works
      </h2>
      <ol className="mt-3 grid gap-3 sm:grid-cols-5 sm:gap-0">
        {STEPS.map((s, i) => (
          <li key={s.name} className="relative flex items-start gap-3 sm:flex-col sm:gap-2 sm:pr-6">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-pill border border-line bg-surface text-xs font-semibold num">
              {i + 1}
            </span>
            {i < STEPS.length - 1 && <span aria-hidden="true" className="absolute left-9 right-2 top-3.5 hidden h-px bg-line sm:block" />}
            <div>
              <p className="text-sm font-semibold">{s.name}</p>
              <p className="text-xs text-ink-muted">{s.detail}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-5 grid gap-3 text-sm text-ink-muted md:grid-cols-2">
        <p>
          Every model call runs on <strong className="font-semibold text-ink">Nebius Token Factory</strong>;{' '}
          <strong className="font-semibold text-ink">NVIDIA Nemotron</strong> plans the page structure and writes the interaction code, and every render and
          test runs in a <strong className="font-semibold text-ink">Token Factory Sandbox</strong>. Code-writing models get text measurements only, never
          image bytes; scoring runs in a separate disposable sandbox.
        </p>
        <p>
          <strong className="font-semibold text-ink">Scope:</strong> static responsive layout with working basic controls — real inputs, buttons, links and a
          mobile menu toggle. Designed states (an open menu, an expanded answer) are built only when a state frame shows them. Where a deterministic
          baseline does as well as the model, the runs say so.
        </p>
      </div>
    </section>
  );
}
