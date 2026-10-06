import type { Breakpoint, Candidate, Run } from '../lib/types';
import { bandLabel } from '../lib/score';
import { BpBullets } from './viz/BpBullets';
import { ScoreRing } from './viz/ScoreRing';
import { WidthStrip } from './viz/WidthStrip';
import { fluidityCells } from '../lib/viz';
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
          <div className="mt-3 flex items-center gap-4" aria-live="polite">
            <ScoreRing score={best.match} size={88} />
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

      {best && (
        <div>
          <h3 className="eyebrow mb-2">Per breakpoint</h3>
          <BpBullets perBp={best.per_bp} bps={bps.map((b) => b.name)} legend />
        </div>
      )}

      {best?.fluidity && (
        <div>
          <h3 className="eyebrow mb-2">Between breakpoints</h3>
          <WidthStrip cells={fluidityCells(best.fluidity)} height="h-4" />
        </div>
      )}

      <div>
        <h3 className="eyebrow mb-2">Match over rounds</h3>
        <ScoreChart run={run} upToRound={completedRound} bps={bps.map((b) => b.name)} />
      </div>
    </section>
  );
}
