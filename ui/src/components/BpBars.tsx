import type { BpName, PerBp } from '../lib/types';
import { bpBg, cap } from '../lib/format';
import { fmtScore } from '../lib/score';

/** Compact per-breakpoint bars (0–100). The worst breakpoint is marked. */
export function BpBars({ perBp, bps = ['mobile', 'tablet', 'desktop'] }: { perBp: PerBp; bps?: BpName[] }) {
  const vals = bps.map((b) => perBp[b]).filter((v): v is number => v != null);
  const worst = vals.length ? Math.min(...vals) : null;
  return (
    <dl className="grid gap-1.5">
      {bps.map((bp) => {
        const v = perBp[bp];
        const isWorst = v != null && v === worst;
        return (
          <div key={bp} className="grid grid-cols-[4.5rem_1fr_2.75rem] items-center gap-2 text-xs">
            <dt className={isWorst ? 'font-semibold text-ink' : 'text-ink-muted'}>{cap(bp)}</dt>
            <dd className="h-1.5 overflow-hidden rounded-pill bg-surface-2" aria-hidden="true">
              <div className={`h-full rounded-pill ${bpBg(bp)}`} style={{ width: `${Math.max(0, Math.min(100, v ?? 0))}%` }} />
            </dd>
            <dd className={`text-right num ${isWorst ? 'font-semibold text-ink' : 'text-ink-muted'}`}>
              {fmtScore(v)}
              <span className="sr-only">{isWorst ? ' (worst)' : ''}</span>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
