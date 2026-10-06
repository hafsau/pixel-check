import type { StaticEntry } from '../lib/types';
import { Link } from '../lib/router';
import { runAsset } from '../lib/data';
import { codeHref, entryHref, splitTitle } from '../lib/bundle';
import { bandLabel } from '../lib/score';
import { fmtDate, fmtUsd } from '../lib/format';
import { BpBullets } from './viz/BpBullets';
import { ScoreRing } from './viz/ScoreRing';
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
          <div className="flex shrink-0 flex-col items-center gap-1">
            <ScoreRing score={run.match} size={56} />
            <p className="text-[11px] text-ink-muted" aria-hidden="true">Match</p>
          </div>
        </header>
        <BpBullets perBp={run.per_bp} />
        <footer className="mt-auto flex items-center justify-between gap-2 text-xs text-ink-muted">
          <span className="truncate">
            {bandLabel(run.match)}
            {run.usd != null && <> · {fmtUsd(run.usd, 3)} all-in</>}
            <span className="sr-only"> · recorded {fmtDate(run.created)}</span>
          </span>
          <span className="flex shrink-0 items-center gap-3">
            <Link to={codeHref(run)!} className="relative z-10 rounded-sm font-medium text-ink-muted underline decoration-line underline-offset-2 hover:text-ink" aria-label={`Code of ${t.title}`}>
              Code
            </Link>
            <span className="inline-flex items-center gap-1 font-medium text-ink group-hover:text-accent-strong">
              Replay <IconArrowRight />
            </span>
          </span>
        </footer>
      </div>
    </article>
  );
}
