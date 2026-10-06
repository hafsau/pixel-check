import type { BpName, PerBp } from '../../lib/types';
import { cap } from '../../lib/format';
import { fmtScore } from '../../lib/score';
import { BULLET_BANDS, BULLET_TARGET, bulletModel } from '../../lib/viz';
import { StatusIcon } from '../PassPill';

// Band shades: darker = worse (classic bullet chart), drawn in ink so they work in both themes.
const BAND_SHADE = ['bg-ink/[0.13]', 'bg-ink/[0.07]', 'bg-ink/[0.03]'];

/** One bullet: qualitative bands 0–49 / 50–89 / 90–100, the score bar, and a target tick at 90. */
export function Bullet({ value, className = '' }: { value: number | null | undefined; className?: string }) {
  const m = bulletModel(value);
  return (
    <div className={`relative h-3.5 overflow-hidden rounded-[3px] ${className}`} aria-hidden="true">
      {BULLET_BANDS.map((b, i) => (
        <span key={b.label} className={`absolute inset-y-0 ${BAND_SHADE[i]}`} style={{ left: `${b.from}%`, width: `${b.to - b.from}%` }} />
      ))}
      {m.pct != null && <span className="absolute left-0 top-1/2 h-1.5 -translate-y-1/2 rounded-r-[2px] bg-ink" style={{ width: `${m.pct}%` }} />}
      <span className="absolute inset-y-0 w-[2px] -translate-x-1/2 bg-accent" style={{ left: `${BULLET_TARGET}%` }} />
    </div>
  );
}

/** Per-breakpoint scores as bullet charts. The worst breakpoint (= the Match) is emphasised. */
export function BpBullets({ perBp, bps = ['mobile', 'tablet', 'desktop'], legend = false }: { perBp: PerBp; bps?: BpName[]; legend?: boolean }) {
  const vals = bps.map((b) => perBp[b]).filter((v): v is number => v != null);
  const worst = vals.length ? Math.min(...vals) : null;
  return (
    <div>
      <dl className="grid gap-2">
        {bps.map((bp) => {
          const v = perBp[bp];
          const m = bulletModel(v);
          const isWorst = v != null && v === worst;
          return (
            <div key={bp} className="grid grid-cols-[4.25rem_minmax(0,1fr)_3.75rem] items-center gap-2.5 text-xs">
              <dt className={isWorst ? 'font-semibold text-ink' : 'text-ink-muted'}>{cap(bp)}</dt>
              <dd>
                <Bullet value={v} />
              </dd>
              <dd className={`flex items-center justify-end gap-1 num ${isWorst ? 'font-semibold text-ink' : 'text-ink-muted'}`}>
                {m.pass != null && <StatusIcon status={m.pass ? 'pass' : 'fail'} />}
                {fmtScore(v)}
                <span className="sr-only">
                  {m.pass == null ? '' : m.pass ? `, at or above the ${BULLET_TARGET} target` : `, below the ${BULLET_TARGET} target`}
                  {isWorst ? ' (worst breakpoint)' : ''}
                </span>
              </dd>
            </div>
          );
        })}
      </dl>
      {legend && (
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-muted" aria-hidden="true">
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-3 w-[2px] bg-accent" /> target {BULLET_TARGET}
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2.5 w-4 rounded-[2px] bg-ink/[0.13]" />
            <span className="-ml-1 inline-block h-2.5 w-4 bg-ink/[0.07]" />
            <span className="-ml-1 inline-block h-2.5 w-4 rounded-r-[2px] bg-ink/[0.03] ring-1 ring-inset ring-line" /> 0–49 · 50–89 · 90–100
          </span>
        </p>
      )}
    </div>
  );
}
