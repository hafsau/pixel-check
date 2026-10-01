import type { Breakpoint, Candidate, Run } from '../lib/types';
import { BAND_TEXT, bandLabel, bandOf, fmtScore } from '../lib/score';
import { BpBars } from './BpBars';
import { ScoreChart } from './ScoreChart';

/** Match (worst breakpoint) big, per-breakpoint scores, and Match over rounds. */
export function ScorePanel({ run, best, completedRound, bps }: { run: Run; best: Candidate | null; completedRound: number; bps: Breakpoint[] }) {
  return (
    <section aria-labelledby="score-title" className="card card-pad flex flex-col gap-5">
      <div>
        <h2 id="score-title" className="eyebrow">
          Match · current best
        </h2>
        {best ? (
          <div className="mt-2 flex items-end gap-3" aria-live="polite">
            <p className={`text-6xl font-semibold leading-none tracking-tight num ${BAND_TEXT[bandOf(best.match)]}`}>{fmtScore(best.match)}</p>
            <div className="pb-1 text-xs text-ink-muted">
              <p className="font-medium text-ink">{bandLabel(best.match)}</p>
              <p>
                worst breakpoint{best.worst ? `: ${best.worst}` : ''} · <code className="font-mono">{best.id}</code>
              </p>
            </div>
          </div>
        ) : (
          <p className="mt-2 text-sm text-ink-muted" aria-live="polite">
            Scoring round 0…
          </p>
        )}
      </div>

      {best && <BpBars perBp={best.per_bp} bps={bps.map((b) => b.name)} />}

      <div>
        <h3 className="eyebrow mb-2">Match over rounds</h3>
        <ScoreChart run={run} upToRound={completedRound} bps={bps.map((b) => b.name)} />
      </div>
    </section>
  );
}
