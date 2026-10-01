import { HowItWorks } from '../components/HowItWorks';
import { RunList } from '../components/RunList';
import { LiveRunPanel } from '../components/LiveRunPanel';
import { DEFAULT_BPS, cap } from '../lib/format';

export function HomePage() {
  return (
    <div className="page pt-10 sm:pt-16">
      <section aria-labelledby="hero-title" className="max-w-3xl">
        <p className="eyebrow">Responsive design → verified code</p>
        <h1 id="hero-title" className="h1 mt-3">
          One codebase. Every breakpoint. <span className="text-accent">Verified.</span>
        </h1>
        <p className="mt-4 max-w-2xl text-base text-ink-muted sm:text-lg">
          Give Pixel-Check the mobile, tablet and desktop frames of one screen. An agent writes a single React + Tailwind
          codebase, renders it at all three sizes, scores each render against its frame and keeps fixing it.
        </p>
        <ul className="mt-5 flex flex-wrap gap-2" aria-label="Breakpoints">
          {DEFAULT_BPS.map((b) => (
            <li key={b.name} className="mono-chip">
              {cap(b.name)} {b.width}×{b.height}
            </li>
          ))}
        </ul>
      </section>
      <HowItWorks />
      <RunList />
      <LiveRunPanel />
    </div>
  );
}
