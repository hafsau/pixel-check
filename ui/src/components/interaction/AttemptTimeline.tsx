import type { Variant } from '../../lib/types';
import { buildTimeline, writerName } from '../../lib/interactions';
import { cap, fmtSecs, fmtUsd } from '../../lib/format';
import { fmtScore } from '../../lib/score';
import { PassPill } from '../PassPill';
import { IconRevise } from '../Icons';

/**
 * write → test → (revise with the failures → test)… as recorded. Attempt nodes select which attempt the
 * captures, checklist and code below show.
 */
export function AttemptTimeline({ v, selected, onSelect }: { v: Variant; selected: number; onSelect: (i: number) => void }) {
  const steps = buildTimeline(v);
  const outcome = steps[steps.length - 1];
  return (
    <section aria-labelledby="timeline-title" className="card card-pad">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="timeline-title" className="h2">
          Attempts
        </h2>
        {outcome?.kind === 'outcome' && (
          <p className="text-sm text-ink-muted" aria-live="polite">
            {outcome.pass ? 'Passed' : 'Failed'} after {outcome.attempts} {outcome.attempts === 1 ? 'attempt' : 'attempts'}
            {v.writer === 'template' ? ' · no model call' : ''}
          </p>
        )}
      </div>
      <ol className="mt-4 flex flex-col gap-2 md:flex-row md:items-stretch md:gap-0">
        {steps.map((s, k) => {
          if (s.kind === 'attempt') {
            const on = s.index === selected;
            return (
              <li key={k} className="md:min-w-0 md:flex-1">
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => onSelect(s.index)}
                  className={`flex h-full w-full flex-col gap-2 rounded-md border p-3 text-left transition-colors ${
                    on ? 'border-accent bg-accent/5' : 'border-line bg-surface hover:bg-surface-2'
                  }`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold">{s.label}</span>
                    <PassPill status={s.pass ? 'pass' : 'fail'} />
                  </span>
                  <span className="text-xs text-ink-muted num">
                    {s.infra ? (
                      'Infrastructure error — same code re-tested'
                    ) : s.pass ? (
                      'All generated tests pass'
                    ) : (
                      <>
                        {s.failureCount} failed {s.failureCount === 1 ? 'test' : 'tests'}
                        {s.worstBp && s.worstScore != null ? ` · ${cap(s.worstBp)} state ${fmtScore(s.worstScore)}` : ''}
                      </>
                    )}
                  </span>
                  {(s.sandboxS != null || s.sandboxUsd != null) && (
                    <span className="text-[11px] text-ink-faint num">
                      Sandbox {fmtSecs(s.sandboxS)} · {fmtUsd(s.sandboxUsd, 4)}
                    </span>
                  )}
                </button>
              </li>
            );
          }
          if (s.kind === 'revise') {
            return (
              <li key={k} className="flex items-center gap-2 pl-4 text-xs text-ink-muted md:w-36 md:shrink-0 md:flex-col md:justify-center md:px-2 md:pl-2 md:text-center">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-pill border border-line bg-surface-2 text-accent">
                  <IconRevise />
                </span>
                <span>
                  {s.infra ? 'Re-tested (sandbox error, not shown to the writer)' : `${writerName(s.by)} revised from ${s.fedBack.length} test ${s.fedBack.length === 1 ? 'failure' : 'failures'}`}
                </span>
              </li>
            );
          }
          return null;
        })}
      </ol>
      <p className="mt-3 text-xs text-ink-muted">
        {v.writer === 'template'
          ? 'The template writes once from the measured facts; there is nothing to revise.'
          : 'Each revision gets the measured facts, its previous sections and the failing test sentences listed under Tests — text only, never the design images.'}
      </p>
    </section>
  );
}
