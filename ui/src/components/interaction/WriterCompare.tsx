import type { Interaction, Variant } from '../../lib/types';
import { cap, fmtSecs, fmtUsd } from '../../lib/format';
import { fmtScore } from '../../lib/score';
import { bestAttempt, summarizeRepeats } from '../../lib/interactions';
import { ModelName } from '../ModelName';
import { PassPill } from '../PassPill';

/** Template vs Nemotron, side by side. Picking a card shows that writer's attempts, tests and captures below. */
export function WriterCompare({ ix, selected, onSelect }: { ix: Interaction; selected: string; onSelect: (key: string) => void }) {
  return (
    <section aria-labelledby="writers-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="writers-title" className="h2">
          Who wired it
        </h2>
        <p className="text-xs text-ink-muted">Same compiled panel, same generated tests, same sandbox. Pick one to inspect.</p>
      </div>
      <div
        role="radiogroup"
        aria-labelledby="writers-title"
        onKeyDown={(e) => {
          const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
          if (!d) return;
          e.preventDefault();
          const root = e.currentTarget;
          const i = ix.variants.findIndex((v) => v.key === selected);
          const next = ix.variants[(i + d + ix.variants.length) % ix.variants.length];
          onSelect(next.key);
          requestAnimationFrame(() => (root.querySelector(`[data-key="${next.key}"]`) as HTMLElement | null)?.focus());
        }}
        className={`mt-3 grid gap-3 ${ix.variants.length > 1 ? 'md:grid-cols-2' : ''}`}>
        {ix.variants.map((v) => (
          <WriterCard key={v.key} ix={ix} v={v} checked={v.key === selected} onSelect={() => onSelect(v.key)} />
        ))}
      </div>
    </section>
  );
}

function WriterCard({ ix, v, checked, onSelect }: { ix: Interaction; v: Variant; checked: boolean; onSelect: () => void }) {
  const best = bestAttempt(v);
  const reps = summarizeRepeats(ix.repeats.filter((r) => r.writer === v.writer));
  const nem = v.writer === 'nemotron';
  return (
    <div
      className={`card card-pad relative flex flex-col gap-4 transition-[border-color,box-shadow] hover:border-ink-faint has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent ${checked ? 'border-accent ring-1 ring-accent' : ''}`}
    >
      <div className="flex w-full items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow">{nem ? 'Model' : 'Baseline · no model'}</p>
          <p className="mt-1 text-base font-semibold">
            <button
              type="button"
              role="radio"
              aria-checked={checked}
              tabIndex={checked ? 0 : -1}
              data-key={v.key}
              onClick={onSelect}
              className="text-left outline-none after:absolute after:inset-0 after:rounded-lg after:content-[''] focus-visible:ring-0 focus-visible:ring-offset-0"
            >
              {nem ? 'Nemotron writer' : 'Deterministic template'}
            </button>
          </p>
          <p className="mt-0.5 text-xs text-ink-muted">
            {nem ? (
              <>
                <ModelName id={ix.writer_model ?? 'nvidia/Nemotron'} /> writes the wiring, then revises from failed tests
              </>
            ) : (
              'Fills the same wiring from the measured facts'
            )}
          </p>
        </div>
        <PassPill status={v.pass ? 'pass' : 'fail'} label={v.pass ? 'Passes' : 'Fails'} size="md" />
      </div>

      <dl className="grid w-full grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
        {Object.entries(best?.state_scores ?? {}).map(([bp, s]) => (
          <div key={bp}>
            <dt className="text-[11px] text-ink-muted">{cap(bp)} state</dt>
            <dd className="font-semibold num">{fmtScore(s)}</dd>
          </div>
        ))}
        <div>
          <dt className="text-[11px] text-ink-muted">Attempts</dt>
          <dd className="font-semibold num">{v.attempts.length}</dd>
        </div>
        <div>
          <dt className="text-[11px] text-ink-muted">Cost, all-in</dt>
          <dd className="font-semibold num">{fmtUsd(v.usd, 3)}</dd>
        </div>
      </dl>
      <p className="w-full text-xs text-ink-muted num">
        Model {fmtUsd(v.model_usd, 4)} · sandbox {fmtUsd(v.sandbox_usd, 4)} · {v.sandbox.runs} sandbox runs, {fmtSecs(v.sandbox.wall_s)} · {fmtSecs(v.seconds)} wall
      </p>
      {reps.length > 0 && (
        <ul className="w-full border-t border-line pt-3 text-xs text-ink-muted">
          {reps.map((r) => (
            <li key={r.label} className="flex justify-between gap-3">
              <span>{r.label}</span>
              <span className="num">
                <strong className={`font-semibold ${r.passed === r.runs ? 'text-good' : r.passed === 0 ? 'text-bad' : 'text-ink'}`}>
                  {r.passed}/{r.runs}
                </strong>{' '}
                runs passed{nem && r.passed > 0 ? ` · ${r.firstTry} at attempt 1` : ''}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
