import type { StaticEntry } from '../lib/types';
import { Link } from '../lib/router';
import { runAsset } from '../lib/data';
import { entryHref, splitTitle } from '../lib/bundle';
import { BAND_TEXT, bandLabel, bandOf, fmtScore } from '../lib/score';
import { fmtDate, fmtUsd } from '../lib/format';
import { BpBars } from './BpBars';
import { Thumb } from './Thumb';
import { IconArrowRight } from './Icons';

export function RunCard({ run }: { run: StaticEntry }) {
  const t = splitTitle(run.title);
  return (
    <article className="card card-pad group relative flex gap-4 transition-colors hover:border-ink-faint">
      <Thumb src={run.thumb ? runAsset(run.id, run.thumb) : null} />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-semibold leading-snug">
              <Link to={entryHref(run)} className="rounded-sm after:absolute after:inset-0 after:content-['']">
                {t.title}
              </Link>
            </h3>
            <p className="mt-1 flex flex-wrap items-center gap-1.5">
              {run.label && <span className="chip">{run.label}</span>}
              {t.note && <span className="chip border-dashed">{t.note}</span>}
              {run.fluid_pass != null && (
                <span className={`chip ${run.fluid_pass ? '' : 'border-bad/30 text-bad'}`} title="No overflow, overlap or drift at 360 / 375 / 500 / 1024 / 1600 px">
                  {run.fluid_pass ? 'Fluid 5/5 widths' : 'Fluidity fails'}
                </span>
              )}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className={`text-2xl font-semibold leading-none num ${BAND_TEXT[bandOf(run.match)]}`}>{fmtScore(run.match)}</p>
            <p className="mt-1 text-[11px] text-ink-muted">Match</p>
          </div>
        </header>
        <BpBars perBp={run.per_bp} />
        <footer className="mt-auto flex items-center justify-between gap-2 text-xs text-ink-muted">
          <span className="truncate">
            {bandLabel(run.match)}
            {run.usd != null && <> · {fmtUsd(run.usd, 3)} all-in</>}
            <span className="sr-only"> · recorded {fmtDate(run.created)}</span>
          </span>
          <span className="inline-flex shrink-0 items-center gap-1 font-medium text-ink group-hover:text-accent">
            Replay <IconArrowRight />
          </span>
        </footer>
      </div>
    </article>
  );
}
