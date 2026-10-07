import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Run } from '../lib/types';
import { Link } from '../lib/router';
import { useLoad } from '../lib/data';
import { normalizeRun } from '../lib/owned';
import { apiBase, failureNotice, liveFilesBase, resolveAsset, runDuration, sourceHost, stageProgress, type LiveStatus, type PollState, type StageState } from '../lib/live';
import { useLivePoll } from '../lib/liveApi';
import { fmtSecs, fmtUsd } from '../lib/format';
import { RunView } from './RunPage';
import { ResultView } from './ResultPage';
import { ErrorView, Loading } from '../components/StatusView';
import { IconAlert, IconArrowLeft, IconCheck, IconMinus, IconX } from '../components/Icons';

/** /live/<id> and /live/<id>/result: progress while the run works, then the normal Run / Result view from the API's bundle. */
export function LiveRunPage({ id, result = false }: { id: string; result?: boolean }) {
  const [poll, retry] = useLivePoll(id);
  if (poll.phase === 'done') return <LiveResult id={id} result={result} usd={poll.status?.result?.usd ?? null} source={poll.status?.source} />;
  return <LiveProgress id={id} poll={poll} retry={retry} />;
}

function LiveResult({ id, result, usd, source }: { id: string; result: boolean; usd: number | null; source?: LiveStatus['source'] }) {
  const host = sourceHost(source);
  const base = useMemo(() => liveFilesBase(apiBase(), id), [id]);
  const asset = useCallback((rel: string) => resolveAsset(base, rel) ?? '', [base]);
  const run = useLoad<Run>(async () => {
    const res = await fetch(`${base}run.json`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`The result bundle could not be loaded (${res.status}).`);
    return normalizeRun((await res.json()) as Run);
  }, [base]);
  if (run.status === 'loading') return <Loading label="Loading the result…" />;
  if (run.status === 'error') return <ErrorView title="Could not load this live run" detail={run.error} />;
  if (!run.data.candidates?.length) return <ErrorView title="This live run produced no candidates" />;
  const basePath = `/live/${encodeURIComponent(id)}`;
  if (result) return <ResultView run={run.data} asset={asset} basePath={basePath} sourceHost={host} />;
  return (
    <RunView
      run={run.data}
      asset={asset}
      basePath={basePath}
      sourceHost={host}
      banner={
        <p className="mt-4 rounded-md border border-accent/30 bg-accent/5 px-3 py-2 text-xs text-ink-muted">
          <strong className="font-semibold text-ink">Live run</strong> — made just now from {host ? <>a capture of <span className="font-medium text-ink">{host}</span></> : 'your frames'} with real models on Nebius Token Factory and real renders in
          Token Factory Sandboxes{usd != null ? ` · model cost ${fmtUsd(usd, 4)}` : ''}. It is not added to the replay list.
        </p>
      }
    />
  );
}

export function useElapsed(since: number | undefined, running: boolean): number {
  const [start] = useState(() => Date.now() / 1000);
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!running) return;
    const t = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(t);
  }, [running]);
  return Math.max(0, now - (since ?? start));
}

function LiveProgress({ id, poll, retry }: { id: string; poll: PollState; retry: () => void }) {
  const st = poll.status ?? { state: 'queued' as const, stages: [] };
  const stages = stageProgress(st);
  const elapsed = useElapsed(poll.status?.created, poll.phase === 'polling');
  const active = stages.find((s) => s.state === 'active');
  const failed = poll.phase === 'failed';
  const notice = failureNotice(poll.status?.error ?? poll.error);
  const refused = failed && notice.kind === 'refused';
  const pageUrl = poll.status?.source?.url;

  return (
    <div className="page pt-6">
      <Link to="/#live" className="inline-flex w-fit items-center gap-1 rounded-sm text-xs font-medium text-ink-muted hover:text-ink">
        <IconArrowLeft /> Back
      </Link>
      <p className="eyebrow mt-3">Live run</p>
      <h1 className="display mt-1 text-2xl sm:text-3xl">{failed ? notice.title : poll.phase === 'offline' ? 'Lost contact with the server' : pageUrl ? 'Working on the page…' : 'Working on your frames…'}</h1>
      <p className="mt-1 break-all font-mono text-[11px] text-ink-faint">{id}</p>
      {pageUrl && (
        <p className="mt-2 max-w-2xl break-all text-sm text-ink-muted">
          From <span className="font-mono text-[13px] text-ink">{pageUrl}</span>
        </p>
      )}

      <section aria-labelledby="progress-title" className="card card-pad mt-6 max-w-2xl">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="progress-title" className="h2">
            Progress
          </h2>
          <p className="text-sm text-ink-muted num" aria-label={`Elapsed ${Math.round(elapsed)} seconds`}>
            {fmtSecs(elapsed)}
          </p>
        </div>
        <p className="sr-only" aria-live="polite">
          {failed ? 'The run failed.' : st.state === 'queued' ? 'Queued.' : active ? `${active.label}.` : ''}
        </p>
        <ol className="mt-4 flex flex-col gap-3">
          {stages.map((s, i) => (
            <li key={s.id} className="flex items-center gap-3">
              <StageIcon state={s.state} n={i + 1} />
              <span className={`text-sm ${s.state === 'pending' ? 'text-ink-muted' : 'font-medium text-ink'}`}>{s.label}</span>
              <span className="sr-only">
                {' '}
                — {s.state === 'done' ? 'done' : s.state === 'active' ? 'in progress' : s.state === 'failed' ? 'failed' : 'not started'}
              </span>
            </li>
          ))}
        </ol>
        {st.state === 'queued' && poll.phase === 'polling' && <p className="mt-4 text-xs text-ink-muted">Queued — starting in a moment.</p>}

        {failed && (
          <div role="alert" className={`mt-5 rounded-md border p-3 text-sm ${refused ? 'border-warn/40 bg-warn/10' : 'border-bad/30 bg-bad/5'}`}>
            <p className={`font-semibold ${refused ? 'text-ink' : 'text-bad'}`}>{notice.message}</p>
            {refused && <p className="mt-1 text-xs text-ink-muted">This is a safety rule, not an error: nothing from the page was rebuilt.</p>}
            {poll.status && !refused && <p className="mt-1 text-xs text-ink-muted">Nothing was added to the replay list. You can try again; it counts as a new run.</p>}
            <Link to="/#live" className="btn mt-3">
              {refused ? 'Upload frames instead' : poll.status ? 'Try again' : 'Start a new run'}
            </Link>
          </div>
        )}
        {poll.phase === 'offline' && (
          <div role="alert" className="mt-5 rounded-md border border-warn/40 bg-warn/10 p-3 text-sm">
            <p className="flex items-center gap-1.5 font-semibold text-ink">
              <IconAlert /> The server did not answer three times in a row.
            </p>
            <p className="mt-1 text-xs text-ink-muted">The run keeps going on the server. Check your connection, then resume.</p>
            <button type="button" className="btn-primary mt-3" onClick={retry}>
              Resume checking
            </button>
          </div>
        )}
        {poll.phase === 'polling' && poll.networkErrors > 0 && <p className="mt-4 text-xs text-warn">Connection hiccup — retrying…</p>}

        <p className="mt-5 border-t border-line pt-4 text-xs text-ink-muted">
          This is a real run: a vision model and Nemotron on <strong className="font-semibold text-ink">Nebius Token Factory</strong>, renders and scoring in{' '}
          <strong className="font-semibold text-ink">Token Factory Sandboxes</strong>
          {pageUrl ? ', after the page is captured in a sandbox' : ''}. It usually takes {runDuration(st)}. Keep this page open; the result appears here.
        </p>
      </section>
    </div>
  );
}

export function StageIcon({ state, n }: { state: StageState; n: number }) {
  const base = 'flex h-7 w-7 shrink-0 items-center justify-center rounded-pill border text-xs font-semibold';
  if (state === 'done')
    return (
      <span className={`${base} border-good/30 bg-good/10 text-good`} aria-hidden="true">
        <IconCheck />
      </span>
    );
  if (state === 'failed')
    return (
      <span className={`${base} border-bad/30 bg-bad/10 text-bad`} aria-hidden="true">
        <IconX />
      </span>
    );
  if (state === 'active')
    return (
      <span className={`${base} border-accent bg-accent/10 text-accent-strong`} aria-hidden="true">
        <span className="h-3 w-3 animate-spin rounded-pill border-2 border-accent border-t-transparent motion-reduce:animate-none" />
      </span>
    );
  return (
    <span className={`${base} border-line text-ink-faint`} aria-hidden="true">
      {n > 0 ? n : <IconMinus />}
    </span>
  );
}
