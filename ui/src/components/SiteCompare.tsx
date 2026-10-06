import { useState } from 'react';
import type { Breakpoint, Run } from '../lib/types';
import { threeUp } from '../lib/owned';
import { bpBg, cap } from '../lib/format';
import { FittedFrame, FrameEmpty, FrameImage } from './FittedFrame';

/** Owned sites: "Your site" · "What we verify against" · "Rebuild", one breakpoint at a time. Renders nothing without real screenshots. */
export function SiteCompare({ run, asset, bps, className = '' }: { run: Run; asset: (rel: string) => string; bps: Breakpoint[]; className?: string }) {
  const [bpName, setBpName] = useState(bps[0]?.name);
  const bp = bps.find((b) => b.name === bpName) ?? bps[0];
  const t = bp ? threeUp(run, bp.name) : null;
  if (!bp || !t) return null;
  const name = cap(bp.name);
  const cells: { key: string; title: string; note?: string; src: string | null; alt: string }[] = [
    { key: 'real', title: 'Your site', src: t.real, alt: `${name}: your site` },
    { key: 'design', title: 'What we verify against', note: 'Inter · images as blocks', src: t.design, alt: `${name}: the normalised capture the rebuild is scored against` },
    { key: 'rebuild', title: 'Rebuild', src: t.rebuild, alt: `${name}: the rebuild (best candidate)` },
  ];
  return (
    <section aria-labelledby="site-compare-title" className={`card card-pad ${className}`}>
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="site-compare-title" className="h2">
          Side by side
        </h2>
        <div className="seg" role="radiogroup" aria-label="Breakpoint">
          {bps.map((b) => (
            <button key={b.name} type="button" role="radio" aria-checked={b.name === bp.name} className="seg-item inline-flex items-center gap-1.5" onClick={() => setBpName(b.name)}>
              <span className={`h-2 w-2 rounded-pill ${bpBg(b.name)}`} aria-hidden="true" />
              {cap(b.name)}
            </button>
          ))}
        </div>
      </header>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {cells.map((c) => (
          <figure key={c.key} className="flex min-w-0 flex-col gap-1.5">
            <figcaption className="flex flex-wrap items-baseline gap-x-2 text-[11px] font-medium uppercase tracking-[0.06em] text-ink-muted">
              <span className={c.key === 'rebuild' ? 'text-ink' : ''}>{c.title}</span>
              {c.note && <span className="font-mono normal-case tracking-normal text-ink-faint">{c.note}</span>}
            </figcaption>
            <FittedFrame width={bp.width} height={bp.height}>
              {c.src ? <FrameImage src={asset(c.src)} alt={c.alt} /> : <FrameEmpty>Not available</FrameEmpty>}
            </FittedFrame>
          </figure>
        ))}
      </div>
    </section>
  );
}
