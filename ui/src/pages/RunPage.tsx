import { useEffect, useState } from 'react';
import type { Run } from '../lib/types';
import { useRun, runAsset } from '../lib/data';
import { usePlayback } from '../lib/playback';
import { Link } from '../lib/router';
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

export function RunPage({ id }: { id: string }) {
  const r = useRun(id);
  if (r.status === 'loading') return <Loading label="Loading run…" />;
  if (r.status === 'error') return <ErrorView title="Run not found" detail={r.error} />;
  if (!r.data.candidates?.length) return <ErrorView title="This run has no candidates" />;
  return <RunView run={r.data} />;
}

function RunView({ run }: { run: Run }) {
  const pb = usePlayback(run);
  const [mode, setMode] = useState<CompareMode>('slider');
  const [follow, setFollow] = useState<'step' | 'best'>('step');
  const bps = run.breakpoints?.length ? run.breakpoints : [...DEFAULT_BPS];
  const shown = follow === 'best' && pb.best ? pb.best : pb.shown;
  const activeRound = pb.shown.round;

  // Preload the next two candidates' renders so playback doesn't flash.
  useEffect(() => {
    run.candidates.slice(pb.index + 1, pb.index + 3).forEach((c) =>
      Object.values(c.renders ?? {}).forEach((rel) => {
        if (rel) new Image().src = runAsset(run.id, rel);
      }),
    );
  }, [run, pb.index]);

  return (
    <div className="page pt-6">
      <RunHeader
        run={run}
        subtitle={`${run.candidates.length} candidates · ${run.rounds.length} rounds · ${fmtDate(run.created)}`}
        actions={
          <Link to={`/run/${encodeURIComponent(run.id)}/result`} className="btn">
            Result <IconArrowRight />
          </Link>
        }
      />

      <div className="sticky top-0 z-30 -mx-gutter mt-5 bg-bg/90 px-gutter py-2 backdrop-blur sm:mx-0 sm:px-0">
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
                designSrc={d ? runAsset(run.id, d) : null}
                renderSrc={rr ? runAsset(run.id, rr) : null}
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
          <CritiquePanel critiques={run.critiques ?? []} activeRound={activeRound} />
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
    </div>
  );
}
