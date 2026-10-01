import type { ReactNode } from 'react';
import type { Run } from '../lib/types';
import { Link } from '../lib/router';
import { BAND_TEXT, bandOf, fmtScore } from '../lib/score';
import { IconArrowLeft } from './Icons';

export function RunHeader({ run, subtitle, actions, back = { to: '/', label: 'All runs' } }: { run: Run; subtitle?: string; actions?: ReactNode; back?: { to: string; label: string } }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <Link to={back.to} className="inline-flex items-center gap-1 rounded-sm text-xs font-medium text-ink-muted hover:text-ink">
          <IconArrowLeft /> {back.label}
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{run.title}</h1>
        <p className="mt-1 break-all font-mono text-[11px] text-ink-faint">
          {run.id}
          {subtitle ? <span className="font-sans text-xs text-ink-muted"> · {subtitle}</span> : null}
        </p>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className={`text-3xl font-semibold leading-none num ${BAND_TEXT[bandOf(run.result.match)]}`}>{fmtScore(run.result.match)}</p>
          <p className="mt-1 text-[11px] text-ink-muted">Final Match</p>
        </div>
        {actions}
      </div>
    </header>
  );
}
