import type { GroupEntry } from '../lib/types';
import { Link } from '../lib/router';
import { runAsset } from '../lib/data';
import { entryHref, splitTitle } from '../lib/bundle';
import { cap } from '../lib/format';
import { Thumb } from './Thumb';
import { IconAlert, IconArrowRight } from './Icons';

export function GroupCard({ e }: { e: GroupEntry }) {
  const t = splitTitle(e.title);
  const rows = e.variants.filter((v) => v.oracle);
  return (
    <article className="card card-pad group relative flex gap-4 transition-colors hover:border-ink-faint">
      <Thumb src={e.thumb ? runAsset(e.id, e.thumb) : null} />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <header>
          <h3 className="font-semibold leading-snug">
            <Link to={entryHref(e)} className="rounded-sm after:absolute after:inset-0 after:content-['']">
              {t.title}
            </Link>
          </h3>
          <p className="mt-1 text-xs text-ink-muted">
            Given: <strong className="font-medium text-ink">{e.given ? cap(e.given) : '—'}</strong> · held out: {e.held.map(cap).join(', ')}
          </p>
        </header>
        <dl className="grid gap-1 text-xs">
          {rows.map((v) => (
            <div key={`${v.planner}-${v.notes}`} className="flex justify-between gap-2">
              <dt className="text-ink-muted">
                {cap(v.planner)} <span className="text-ink-faint">({v.notes === 'notes_prose' ? 'free-form notes' : 'structured notes'})</span>
              </dt>
              <dd className="num font-medium">
                {v.held_out_pass}/{v.held_out_total} held out
              </dd>
            </div>
          ))}
        </dl>
        {e.review && (
          <p className="flex items-start gap-1.5 text-xs text-warn">
            <IconAlert /> <span>Council review: fail — see details</span>
          </p>
        )}
        <footer className="mt-auto flex justify-end text-xs">
          <span className="inline-flex items-center gap-1 font-medium text-ink group-hover:text-accent-strong">
            Open <IconArrowRight />
          </span>
        </footer>
      </div>
    </article>
  );
}
