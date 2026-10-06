import type { ReactNode } from 'react';

/** Three visual steps (≤ 8 words each); the scope and honesty notes sit in a compact footnote. */
const STEPS: { name: string; line: string; art: ReactNode }[] = [
  { name: 'Capture', line: 'Three frames — or a page you own.', art: <CaptureArt /> },
  { name: 'Compile', line: 'One fluid React + Tailwind codebase.', art: <CompileArt /> },
  { name: 'Prove', line: 'Rendered, measured and scored at every width.', art: <ProveArt /> },
];

export function HowItWorks() {
  return (
    <section id="how" aria-labelledby="how-title" className="section scroll-mt-6" tabIndex={-1}>
      <h2 id="how-title" className="eyebrow">
        How it works
      </h2>
      <ol className="mt-4 grid gap-3 md:grid-cols-3">
        {STEPS.map((s, i) => (
          <li key={s.name} className="card flex items-center gap-4 p-4 sm:p-5 md:flex-col md:items-start">
            <div className="grid h-[72px] w-[104px] shrink-0 place-items-center rounded-md bg-surface-2 text-ink md:h-[96px] md:w-full">{s.art}</div>
            <div className="min-w-0">
              <p className="flex items-baseline gap-2">
                <span className="font-mono text-[11px] text-ink-faint num" aria-hidden="true">
                  0{i + 1}
                </span>
                <span className="text-base font-semibold tracking-[-0.02em]">{s.name}</span>
              </p>
              <p className="mt-0.5 text-sm text-ink-muted">{s.line}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-4 max-w-4xl text-xs leading-relaxed text-ink-muted">
        <span className="font-semibold text-ink">Notes.</span> Every model call runs on Nebius Token Factory; NVIDIA Nemotron plans the page structure and
        writes interaction code. Code-writing models get text measurements, never image bytes; every render, test and score runs in a Token Factory
        Sandbox. Scope: static responsive layout with working basic controls; designed states only from a state frame. On some tasks a deterministic
        baseline matches the model — the runs say so.
      </p>
    </section>
  );
}

/* --- small illustrations: single-colour line art in currentColor, orange for the one "signal" detail --- */

function CaptureArt() {
  return (
    <svg width="96" height="60" viewBox="0 0 96 60" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <rect x="4" y="14" width="16" height="32" rx="3" />
      <rect x="26" y="10" width="26" height="36" rx="3" />
      <rect x="58" y="12" width="34" height="24" rx="3" />
      <path d="M58 40h34" opacity=".35" />
      <g stroke="rgb(var(--c-accent))" strokeWidth="1.75" strokeLinecap="round">
        <path d="M2 52h18M26 52h26M58 52h34" />
      </g>
      <g fill="currentColor" stroke="none" opacity=".35">
        <rect x="8" y="19" width="8" height="2" rx="1" />
        <rect x="30" y="15" width="14" height="2" rx="1" />
        <rect x="62" y="17" width="16" height="2" rx="1" />
      </g>
    </svg>
  );
}

function CompileArt() {
  return (
    <svg width="96" height="60" viewBox="0 0 96 60" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M22 18 10 30l12 12M74 18l12 12-12 12" />
      <path d="M54 12 42 48" stroke="rgb(var(--c-accent))" />
      <g strokeWidth="1.5" opacity=".35">
        <path d="M30 24h8M30 30h4M30 36h7M60 24h6M62 30h4M58 36h8" />
      </g>
    </svg>
  );
}

function ProveArt() {
  return (
    <svg width="96" height="60" viewBox="0 0 96 60" aria-hidden="true">
      <g fill="currentColor">
        <rect x="6" y="14" width="40" height="10" opacity=".13" />
        <rect x="46" y="14" width="32" height="10" opacity=".07" />
        <rect x="78" y="14" width="12" height="10" opacity=".03" />
        <rect x="6" y="17" width="78" height="4" rx="1" />
      </g>
      <rect x="77" y="11" width="2" height="16" fill="rgb(var(--c-accent))" />
      <g fill="rgb(var(--c-good))">
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <rect key={i} x={6 + i * 12} y="36" width="10" height="8" rx="2" />
        ))}
      </g>
    </svg>
  );
}
