import { useEffect, useState } from 'react';
import type { Breakpoint, Candidate } from '../lib/types';
import type { Run } from '../lib/types';
import { useRun, runAsset, useText } from '../lib/data';
import { usePlayback } from '../lib/playback';
import { Link, setHash, useHash } from '../lib/router';
import { RUN_TABS, hashForTab, tabFromHash, type RunTab } from '../lib/viewTabs';
import { DEFAULT_BPS, fmtDate } from '../lib/format';
import { Loading, ErrorView } from '../components/StatusView';
import { PlaybackControls } from '../components/PlaybackControls';
import { BreakpointRow } from '../components/BreakpointRow';
import { CandidateHeader } from '../components/CandidateHeader';
import { CompareModeToggle, type CompareMode } from '../components/CompareModeToggle';
import { ScorePanel } from '../components/ScorePanel';
import { BranchTree } from '../components/BranchTree';
import { CritiquePanel } from '../components/CritiquePanel';
import { AgentLog } from '../components/AgentLog';
import { SandboxLog } from '../components/SandboxLog';
import { RunHeader } from '../components/RunHeader';
import { IconArrowRight } from '../components/Icons';
import { PipelinePanel } from '../components/PipelinePanel';
import { ViewTabs } from '../components/ViewTabs';
import { LivePreview } from '../components/LivePreview';
import { CodeViewer } from '../components/CodeViewer';
import { DownloadProject, runProjectMeta } from '../components/DownloadProject';

export function RunPage({ id }: { id: string }) {
  const r = useRun(id);
  if (r.status === 'loading') return <Loading label="Loading run…" />;
  if (r.status === 'error') return <ErrorView title="Run not found" detail={r.error} />;
  if (!r.data.candidates?.length) return <ErrorView title="This run has no candidates" />;
  return <RunView run={r.data} asset={(rel) => runAsset(r.data.id, rel)} basePath={`/run/${encodeURIComponent(r.data.id)}`} />;
}

/** The replay of one static run. `asset` resolves bundle-relative paths (replay folder or the live API's files base);
 * `basePath` is this view's own route, so the Result link works for replays (/run/<id>) and live runs (/live/<id>). */
export function RunView({ run, asset, basePath, banner, sourceHost }: { run: Run; asset: (rel: string) => string; basePath: string; banner?: React.ReactNode; sourceHost?: string | null }) {
  const tab = tabFromHash(useHash());
  const pickTab = (t: RunTab) => setHash(hashForTab(t));
  const bps = run.breakpoints?.length ? run.breakpoints : [...DEFAULT_BPS];

  return (
    <div className="page pt-6">
      <RunHeader
        run={run}
        subtitle={`${sourceHost ? `From ${sourceHost} · ` : ''}${run.label ? `${run.label} · ` : ''}${run.candidates.length} ${run.candidates.length === 1 ? 'candidate' : 'candidates'} · ${run.rounds.length} ${run.rounds.length === 1 ? 'round' : 'rounds'} · ${fmtDate(run.created)}`}
        actions={
          <Link to={`${basePath}/result`} className="btn">
            Result <IconArrowRight />
          </Link>
        }
      />

      {banner}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <ViewTabs id="runview" label="Run view" tabs={RUN_TABS} value={tab} onChange={pickTab} />
        <p className="text-xs text-ink-muted">
          {tab === 'replay' ? 'Every candidate, step by step.' : tab === 'preview' ? 'The best candidate, live in your browser.' : 'The best candidate — one responsive file.'}
        </p>
      </div>
      <div role="tabpanel" id="runview-panel" aria-labelledby={`runview-tab-${tab}`} tabIndex={-1} className="outline-none">
        {tab === 'replay' ? (
          <ReplayPanel run={run} asset={asset} bps={bps} />
        ) : (
          <BestCode run={run} asset={asset} bps={bps} tab={tab} sourceHost={sourceHost} />
        )}
      </div>
    </div>
  );
}

function ReplayPanel({ run, asset, bps }: { run: Run; asset: (rel: string) => string; bps: Breakpoint[] }) {
  const pb = usePlayback(run, true); // open on the final candidate; Play restarts from the first
  const [mode, setMode] = useState<CompareMode>('slider');
  const [follow, setFollow] = useState<'step' | 'best'>('best');
  useEffect(() => {
    if (pb.playing) setFollow('step'); // watching the replay: show every candidate as it arrives
  }, [pb.playing]);
  const shown: Candidate = follow === 'best' && pb.best ? pb.best : pb.shown;
  const activeRound = pb.shown.round;

  // Preload the next two candidates' renders so playback doesn't flash.
  useEffect(() => {
    run.candidates.slice(pb.index + 1, pb.index + 3).forEach((c) =>
      Object.values(c.renders ?? {}).forEach((rel) => {
        if (rel) new Image().src = asset(rel);
      }),
    );
  }, [run, pb.index, asset]);

  return (
    <>
      <div className="sticky top-0 z-30 -mx-gutter mt-3 bg-bg/90 px-gutter py-2 backdrop-blur sm:mx-0 sm:px-0">
        <PlaybackControls pb={pb} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-label="Breakpoints" className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CandidateHeader c={shown} isBest={!!pb.best && shown.id === pb.best.id} />
            <div className="flex flex-wrap items-center gap-2">
              <div className="seg" role="radiogroup" aria-label="Candidate shown in the rows">
                <button type="button" role="radio" aria-checked={follow === 'step'} className="seg-item" onClick={() => setFollow('step')}>
                  Latest
                </button>
                <button type="button" role="radio" aria-checked={follow === 'best'} className="seg-item" onClick={() => setFollow('best')}>
                  Best
                </button>
              </div>
              <CompareModeToggle mode={mode} onChange={setMode} />
            </div>
          </div>
          {bps.map((bp) => {
            const d = run.design?.[bp.name];
            const rr = shown.renders?.[bp.name];
            return (
              <BreakpointRow
                key={bp.name}
                bp={bp}
                designSrc={d ? asset(d) : null}
                renderSrc={rr ? asset(rr) : null}
                candidate={shown}
                mode={mode}
              />
            );
          })}
        </section>
        <aside aria-label="Scores" className="lg:sticky lg:top-24 lg:self-start">
          <ScorePanel run={run} best={pb.best} completedRound={pb.completedRound} bps={bps} />
        </aside>
      </div>

      <div className="section flex flex-col gap-4">
        <BranchTree
          run={run}
          revealedIndex={pb.index}
          selectedId={shown.id}
          bestId={pb.best?.id ?? null}
          onSelect={(cid) => {
            setFollow('step');
            pb.selectCandidate(cid);
          }}
        />
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 [&>*]:min-w-0">
          {run.pipeline && <PipelinePanel run={run} shown={shown} />}
          {(!!run.critiques?.length || !run.pipeline) && <CritiquePanel critiques={run.critiques ?? []} activeRound={activeRound} />}
          <SandboxLog
            run={run}
            selectedId={shown.id}
            onSelect={(cid) => {
              setFollow('step');
              pb.selectCandidate(cid);
              window.scrollTo({ top: 0 });
            }}
          />
        </div>
        <AgentLog run={run} />
      </div>
    </>
  );
}

/** Preview / Code tabs: the best candidate's App.jsx, live in an iframe or as source with the project download. */
function BestCode({ run, asset, bps, tab, sourceHost }: { run: Run; asset: (rel: string) => string; bps: Breakpoint[]; tab: 'preview' | 'code'; sourceHost?: string | null }) {
  const best = run.candidates.find((c) => c.id === run.result.best) ?? null;
  const code = useText(best?.code ? asset(best.code) : null);
  if (code.status === 'loading') return <p className="mt-6 text-sm text-ink-muted" role="status">Loading the code…</p>;
  if (code.status === 'error') return <ErrorView title="Could not load App.jsx" detail={code.error} />;
  if (!code.data) return <p className="mt-6 text-sm text-ink-muted">The best candidate has no code in this bundle.</p>;
  if (tab === 'preview') return <div className="mt-4"><LivePreview code={code.data} /></div>;
  return (
    <section aria-labelledby="code-title" className="card card-pad mt-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="code-title" className="h2">
            App.jsx
          </h2>
          <p className="mt-1 text-xs text-ink-muted">
            Best candidate <code className="font-mono">{run.result.best}</code> · one responsive React + Tailwind file, exactly as it was scored. The project download
            adds Vite, Tailwind (same config as the renderer) and a README.
          </p>
        </div>
        <DownloadProject code={code.data} meta={runProjectMeta(run, sourceHost, bps)} />
      </div>
      <div className="mt-4">
        <CodeViewer code={code.data} />
      </div>
    </section>
  );
}
