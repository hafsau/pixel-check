import type { CheckEntry } from '../lib/types';
import { Link } from '../lib/router';
import { runAsset } from '../lib/data';
import { entryHref } from '../lib/bundle';
import { fmtDate, fmtUsd } from '../lib/format';
import { Thumb } from './Thumb';
import { IconArrowRight } from './Icons';

/** A published check / audit (Oct 13): what broke, which warnings, what a phone loses — no score for an audit. */
export function CheckCard({ e }: { e: CheckEntry }) {
  const audit = e.mode === 'audit';
  const host = e.url ? hostOf(e.url) : null;
  return (
    <article className="card card-pad group relative flex gap-4 transition-colors hover:border-ink-faint">
      <Thumb src={e.thumb ? runAsset(e.id, e.thumb) : null} />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <header className="min-w-0">
          <h3 className="font-semibold leading-snug">
            <Link to={entryHref(e)} className="rounded-sm after:absolute after:inset-0 after:content-['']">
              {e.title}
            </Link>
          </h3>
          {host && <p className="mt-0.5 truncate font-mono text-[11px] text-ink-muted">{host}</p>}
          <p className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {e.label && <span className="chip">{e.label}</span>}
            {e.fluid_pass != null && (
              <span className={`chip ${e.fluid_pass ? '' : 'border-bad/30 text-bad'}`}>{e.fluid_pass ? 'Fits 360–1600 px' : 'Breaks between sizes'}</span>
            )}
          </p>
        </header>
        <ul className="flex flex-col gap-1 text-sm">
          <li className={e.warnings ? 'text-warn' : 'text-ink-muted'}>
            {e.warnings ? `${e.warnings} warning${e.warnings === 1 ? '' : 's'}` : 'No warnings'}
          </li>
          <li className="text-ink-muted">{e.vanished ? `${e.vanished} text${e.vanished === 1 ? '' : 's'} gone on smaller screens` : 'Nothing lost on smaller screens'}</li>
        </ul>
        <footer className="mt-auto flex items-center justify-between gap-2 text-xs text-ink-muted">
          <span className="flex min-w-0 items-baseline gap-1">
            <span className="truncate">{audit ? 'Audit' : 'Check'}</span>
            {e.usd ? <span className="num shrink-0 whitespace-nowrap">· {fmtUsd(e.usd, 3)}</span> : null}
            <span className="sr-only"> · recorded {fmtDate(e.created)}</span>
          </span>
          <span className="inline-flex shrink-0 items-center gap-1 font-medium text-ink group-hover:text-accent-strong">
            Open <IconArrowRight />
          </span>
        </footer>
      </div>
    </article>
  );
}

function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}
