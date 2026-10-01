import type { RunSummary } from '../lib/types';
import { Link } from '../lib/router';
import { BAND_TEXT, bandLabel, bandOf, fmtScore } from '../lib/score';
import { fmtDate } from '../lib/format';
import { BpBars } from './BpBars';
import { IconArrowRight } from './Icons';

export function RunCard({ run }: { run: RunSummary }) {
  return (
    <article className="card card-pad group relative flex flex-col gap-4 transition-colors hover:border-ink-faint">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-semibold">
            <Link to={`/run/${encodeURIComponent(run.id)}`} className="rounded-sm after:absolute after:inset-0 after:content-['']">
              {run.title}
            </Link>
          </h3>
          <p className="mt-0.5 truncate font-mono text-[11px] text-ink-faint">
            {run.id} · {fmtDate(run.created)}
          </p>
        </div>
        <div className="text-right">
          <p className={`text-2xl font-semibold leading-none num ${BAND_TEXT[bandOf(run.match)]}`}>{fmtScore(run.match)}</p>
          <p className="mt-1 text-[11px] text-ink-muted">Match</p>
        </div>
      </header>
      <BpBars perBp={run.per_bp} />
      <footer className="flex items-center justify-between text-xs text-ink-muted">
        <span>{bandLabel(run.match)}</span>
        <span className="inline-flex items-center gap-1 font-medium text-ink group-hover:text-accent">
          Replay <IconArrowRight />
        </span>
      </footer>
    </article>
  );
}
