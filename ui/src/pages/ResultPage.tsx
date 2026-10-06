import type { Run } from '../lib/types';
import { useRun, useText, runAsset } from '../lib/data';
import { Link } from '../lib/router';
import { BAND_TEXT, bandLabel, bandOf, fmtScore } from '../lib/score';
import { DEFAULT_BPS, cap, fmtSecs, fmtUsd } from '../lib/format';
import { Loading, ErrorView } from '../components/StatusView';
import { RunHeader } from '../components/RunHeader';
import { StatTile } from '../components/StatTile';
import { CodeViewer } from '../components/CodeViewer';
import { LivePreview } from '../components/LivePreview';
import { IconArrowLeft } from '../components/Icons';
import { DownloadProject, runProjectMeta } from '../components/DownloadProject';

export function ResultPage({ id }: { id: string }) {
  const r = useRun(id);
  if (r.status === 'loading') return <Loading label="Loading result…" />;
  if (r.status === 'error') return <ErrorView title="Run not found" detail={r.error} />;
  return <ResultView run={r.data} asset={(rel) => runAsset(r.data.id, rel)} basePath={`/run/${encodeURIComponent(r.data.id)}`} />;
}

export function ResultView({ run, asset, basePath, sourceHost }: { run: Run; asset: (rel: string) => string; basePath: string; sourceHost?: string | null }) {
  const res = run.result;
  const best = run.candidates.find((c) => c.id === res.best);
  const code = useText(best?.code ? asset(best.code) : null);
  const bps = run.breakpoints?.length ? run.breakpoints : [...DEFAULT_BPS];
  const sandboxUsd = run.candidates.reduce((a, c) => a + (c.sandbox_cost || 0), 0);
  const worstBp = bps.reduce<string | null>((w, b) => (w == null || (res.per_bp[b.name] ?? 101) < (res.per_bp[w] ?? 101) ? b.name : w), null);

  return (
    <div className="page pt-6">
      <RunHeader
        run={run}
        subtitle={sourceHost ? `Result · from ${sourceHost}` : 'Result'}
        back={{ to: basePath, label: 'Back to the run' }}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Link to={basePath} className="btn">
              <IconArrowLeft /> Replay
            </Link>
            {code.status === 'ready' && code.data && <DownloadProject code={code.data} meta={runProjectMeta(run, sourceHost, bps)} />}
          </div>
        }
      />

      <section aria-label="Final scores" className="mt-6">
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Match" value={fmtScore(res.match)} pixel tone={BAND_TEXT[bandOf(res.match)]} hint={`${bandLabel(res.match)}${worstBp ? ` · ${worstBp} worst` : ''}`} />
          {bps.map((b) => (
            <StatTile key={b.name} label={cap(b.name)} value={fmtScore(res.per_bp[b.name])} tone={b.name === worstBp ? BAND_TEXT[bandOf(res.per_bp[b.name])] : ''} hint={`${b.width}×${b.height}`} />
          ))}
        </dl>
        <dl className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Rounds" value={run.rounds.length} hint={`${run.candidates.length} candidates`} />
          <StatTile label="Model cost" value={fmtUsd(res.spend_usd, 3)} hint={`${run.calls.length} calls · Nebius Token Factory`} />
          <StatTile label="Sandbox cost" value={fmtUsd(sandboxUsd, 3)} hint="Token Factory Sandboxes" />
          <StatTile label="Wall time" value={fmtSecs(res.wall_s)} hint={res.stop_reason ? `Stopped: ${res.stop_reason}` : undefined} />
        </dl>
      </section>

      <div className="section flex flex-col gap-4">
        {code.status === 'ready' && code.data ? (
          <>
            <LivePreview code={code.data} />
            <section aria-labelledby="code-title" className="card card-pad">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 id="code-title" className="h2">
                    Code
                  </h2>
                  <p className="mt-1 text-xs text-ink-muted">
                    Best candidate <code className="font-mono">{res.best}</code> — one responsive file, no per-breakpoint copies.
                  </p>
                </div>
                <DownloadProject code={code.data} meta={runProjectMeta(run, sourceHost, bps)} />
              </div>
              <CodeViewer code={code.data} />
            </section>
          </>
        ) : code.status === 'error' ? (
          <ErrorView title="Could not load App.jsx" detail={code.error} />
        ) : code.status === 'loading' ? (
          <p className="text-sm text-ink-muted" role="status">Loading code…</p>
        ) : (
          <p className="text-sm text-ink-muted">The best candidate has no code in this bundle.</p>
        )}
      </div>
    </div>
  );
}
