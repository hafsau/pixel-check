import type { Candidate } from '../lib/types';
import { candidateStatus } from '../lib/types';
import { strategyLabel } from '../lib/playback';
import { ScoreBadge } from './ScoreBadge';

/** One-line summary of the candidate shown in the rows. */
export function CandidateHeader({ c, isBest }: { c: Candidate; isBest: boolean }) {
  const status = candidateStatus(c);
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm" aria-live="polite">
      <span className="font-semibold">Candidate</span>
      <code className="mono-chip">{c.id}</code>
      <span className="chip">Round {c.round}</span>
      <span className="chip">{strategyLabel(c.strategy)}</span>
      <span className="text-ink-muted">Match</span>
      <ScoreBadge score={c.match} dq={status === 'disqualified'} empty={status === 'no-render'} />
      {isBest && <span className="chip border-accent/30 bg-accent/10 text-accent">Current best</span>}
      {status !== 'scored' && c.reason && <span className="text-xs text-bad">{c.reason}</span>}
    </div>
  );
}
