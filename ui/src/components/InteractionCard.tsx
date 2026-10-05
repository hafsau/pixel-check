import type { InteractionEntry } from '../lib/types';
import { Link } from '../lib/router';
import { runAsset } from '../lib/data';
import { entryHref, splitTitle } from '../lib/bundle';
import { cap, fmtUsd } from '../lib/format';
import { fmtScore } from '../lib/score';
import { writerName } from '../lib/interactions';
import { PassPill } from './PassPill';
import { Thumb } from './Thumb';
import { IconArrowRight } from './Icons';

export function InteractionCard({ e }: { e: InteractionEntry }) {
  const t = splitTitle(e.title);
  return (
    <article className="card card-pad group relative flex gap-4 transition-colors hover:border-ink-faint">
      <Thumb src={e.thumb ? runAsset(e.id, e.thumb) : null} />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <header className="min-w-0">
          <h3 className="font-semibold leading-snug">
            <Link to={entryHref(e)} className="rounded-sm after:absolute after:inset-0 after:content-['']">
              {t.title}
            </Link>
          </h3>
          <p className="mt-1 flex flex-wrap gap-1.5">
            {e.kind && <span className="chip">{cap(e.kind)}</span>}
            <span className="chip">{e.bps.map(cap).join(' + ')}</span>
            {t.note && <span className="chip border-dashed">{t.note}</span>}
          </p>
        </header>
        <dl className="grid gap-2 text-xs">
          {e.variants.map((v) => (
            <div key={v.writer} className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 rounded-md bg-surface-2 px-2.5 py-1.5">
              <dt className="flex items-center gap-2 font-medium text-ink">
                {writerName(v.writer)} <PassPill status={v.pass ? 'pass' : 'fail'} />
              </dt>
              <dd className="text-ink-muted num">
                {v.attempts} {v.attempts === 1 ? 'attempt' : 'attempts'} · {fmtUsd(v.usd, 3)}
              </dd>
              <dd className="w-full text-ink-muted num">
                State match {Object.entries(v.state_scores).map(([bp, s]) => `${cap(bp)} ${fmtScore(s)}`).join(' · ')}
              </dd>
            </div>
          ))}
        </dl>
        <footer className="mt-auto flex justify-end text-xs">
          <span className="inline-flex items-center gap-1 font-medium text-ink group-hover:text-accent">
            Tests &amp; attempts <IconArrowRight />
          </span>
        </footer>
      </div>
    </article>
  );
}
