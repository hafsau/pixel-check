import type { Run } from '../lib/types';
import { candidateStatus } from '../lib/types';
import { strategyLabel } from '../lib/playback';
import { fmtUsd } from '../lib/format';
import { ScoreBadge } from './ScoreBadge';

/** Sandbox checkpoint per candidate: proof each render ran in a Token Factory Sandbox. */
export function SandboxLog({ run, onSelect, selectedId }: { run: Run; onSelect: (id: string) => void; selectedId: string }) {
  const total = run.candidates.reduce((a, c) => a + (c.sandbox_cost || 0), 0);
  const rendered = run.candidates.filter((c) => c.checkpoint).length;
  return (
    <section aria-labelledby="sbx-title" className="card card-pad">
      <h2 id="sbx-title" className="h2">
        Sandbox renders
      </h2>
      <p className="mt-1 text-xs text-ink-muted">
        {rendered} candidates rendered at 3 sizes in network-isolated <strong className="font-semibold text-ink">Token Factory Sandboxes</strong>. Checkpoint IDs identify each render run.
      </p>
      <div className="mt-4 max-h-[22rem] overflow-auto rounded-md border border-line">
        <table className="table">
          <caption className="sr-only">Sandbox checkpoint per candidate</caption>
          <thead className="sticky top-0 z-10">
            <tr>
              <th scope="col">Candidate</th>
              <th scope="col">Round</th>
              <th scope="col">Strategy</th>
              <th scope="col">Match</th>
              <th scope="col" className="text-right">Sandbox $</th>
              <th scope="col">Checkpoint</th>
            </tr>
          </thead>
          <tbody>
            {run.candidates.map((c) => {
              const st = candidateStatus(c);
              return (
                <tr key={c.id} className={c.id === selectedId ? 'bg-accent/5' : ''}>
                  <td>
                    <button type="button" className="rounded-sm font-mono text-xs text-accent underline-offset-2 hover:underline" onClick={() => onSelect(c.id)}>
                      {c.id}
                    </button>
                  </td>
                  <td className="num">{c.round}</td>
                  <td>{strategyLabel(c.strategy)}</td>
                  <td>
                    <ScoreBadge score={c.match} dq={st === 'disqualified'} empty={st === 'no-render'} />
                  </td>
                  <td className="text-right num">{c.sandbox_cost ? fmtUsd(c.sandbox_cost) : '—'}</td>
                  <td className="font-mono text-[11px] text-ink-muted">{c.checkpoint ?? <span className="text-ink-faint">— {c.reason ?? 'no render'}</span>}</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot className="sticky bottom-0 bg-surface-2">
            <tr>
              <td colSpan={4}>Sandbox total</td>
              <td className="text-right num">{fmtUsd(total)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
