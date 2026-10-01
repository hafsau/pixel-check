/** One-line pipeline: Perceive → Scaffold → Render in Sandboxes ×3 → Score → Fix. */
const STEPS: { name: string; detail: string }[] = [
  { name: 'Perceive', detail: 'Read the 3 frames into an element spec' },
  { name: 'Scaffold', detail: 'Write one React + Tailwind codebase' },
  { name: 'Render ×3', detail: 'In network-isolated Token Factory Sandboxes' },
  { name: 'Score', detail: 'Each render vs its frame, 0–100' },
  { name: 'Fix', detail: 'Critique the worst breakpoint, branch, repeat' },
];

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" className="section">
      <h2 id="how-title" className="eyebrow">
        How it works
      </h2>
      <ol className="mt-3 grid gap-2 sm:grid-cols-5 sm:gap-0">
        {STEPS.map((s, i) => (
          <li key={s.name} className="relative flex items-start gap-3 sm:flex-col sm:gap-2 sm:pr-6">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-pill border border-line bg-surface text-xs font-semibold num">
              {i + 1}
            </span>
            {i < STEPS.length - 1 && (
              <span aria-hidden="true" className="absolute left-9 right-2 top-3.5 hidden h-px bg-line sm:block" />
            )}
            <div>
              <p className="text-sm font-semibold">{s.name}</p>
              <p className="text-xs text-ink-muted">{s.detail}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-4 text-sm text-ink-muted">
        Every model call runs on <strong className="font-semibold text-ink">Nebius Token Factory</strong> —{' '}
        <strong className="font-semibold text-ink">NVIDIA Nemotron</strong> writes and critiques the code; every render
        runs in a Token Factory Sandbox. The score that counts is the <em>worst</em> breakpoint: <strong className="font-semibold text-ink">Match</strong>.
      </p>
    </section>
  );
}
