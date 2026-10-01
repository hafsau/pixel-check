import { useRunIndex } from '../lib/data';
import { RunCard } from './RunCard';

export function RunList() {
  const idx = useRunIndex();
  return (
    <section id="runs" aria-labelledby="runs-title" className="section scroll-mt-6" tabIndex={-1}>
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 id="runs-title" className="h2">
            Replay a run
          </h2>
          <p className="mt-1 text-sm text-ink-muted">Recorded runs, played back step by step. No models are called.</p>
        </div>
      </div>
      <div className="mt-4">
        {idx.status === 'loading' && <p className="text-sm text-ink-muted" role="status">Loading runs…</p>}
        {idx.status === 'error' && (
          <p className="text-sm text-bad" role="alert">
            Could not load runs: {idx.error}
          </p>
        )}
        {idx.status === 'ready' && idx.data.length === 0 && <p className="text-sm text-ink-muted">No runs exported yet.</p>}
        {idx.status === 'ready' && idx.data.length > 0 && (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {idx.data.map((r) => (
              <li key={r.id} className="min-w-0">
                <RunCard run={r} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
