import { useMemo, useState } from 'react';
import { Link } from '../lib/router';
import { useLoad } from '../lib/data';
import { apiBase, failureNotice, FRAME_SIZES, LIVE_BPS, liveFilesBase, resolveAsset, sourceHost, type LiveBp, type LiveStatus, type PollState } from '../lib/live';
import { useLivePoll, getCheck } from '../lib/liveApi';
import { boxPct, checkCells, checkStages, checkSummary, hurtList, missingBoxes, repairRequested, type Box, type CheckBundle, type Hurt } from '../lib/check';
import { REPAIR_ROUNDS, repairOutcome } from '../lib/repair';
import { bandLabel, fmtScore } from '../lib/score';
import { cap, fmtSecs, fmtUsd } from '../lib/format';
import { ErrorView, Loading } from '../components/StatusView';
import { IconAlert, IconArrowLeft, IconCheck, IconCopy } from '../components/Icons';
import { ScoreRing } from '../components/viz/ScoreRing';
import { BpBullets } from '../components/viz/BpBullets';
import { WidthStrip } from '../components/viz/WidthStrip';
import { CompareSlider } from '../components/CompareSlider';
import { FittedFrame, FrameEmpty, FrameImage } from '../components/FittedFrame';
import { StageIcon, useElapsed } from './LiveRunPage';
import { RepairCard } from '../components/RepairCard';

/** /check/<id>: progress while the check runs, then the measured result. */
export function CheckRunPage({ id }: { id: string }) {
  const [poll, retry] = useLivePoll(id);
  if (poll.phase === 'done') return <CheckResultLoader id={id} status={poll.status} />;
  return <CheckProgress id={id} poll={poll} retry={retry} />;
}

function title(source: LiveStatus['source'] | CheckBundle['source'] | undefined): string {
  const host = sourceHost(source && 'url' in source ? source : null);
  if (host) return host;
  return source && 'code' in source && source.code ? 'Your App.jsx' : 'Your build';
}

// ------------------------------------------------------------------------------------------------ progress

function CheckProgress({ id, poll, retry }: { id: string; poll: PollState; retry: () => void }) {
  const st = poll.status ?? { state: 'queued' as const, stages: [] };
  const stages = checkStages(st, { repair: repairRequested(window.location.search) });
  const repairing = stages.some((s) => s.id === 'repair');
  const elapsed = useElapsed(poll.status?.created, poll.phase === 'polling');
  const active = stages.find((s) => s.state === 'active');
  const failed = poll.phase === 'failed';
  const notice = failureNotice(poll.status?.error ?? poll.error);
  const refused = failed && notice.kind === 'refused';

  return (
    <div className="page pt-6">
      <BackLink />
      <p className="eyebrow mt-3">Build check</p>
      <h1 className="display mt-1 break-words text-2xl sm:text-3xl">
        {failed ? (refused ? 'This build was not checked' : 'The check failed') : poll.phase === 'offline' ? 'Lost contact with the server' : `Checking ${title(poll.status?.source)}…`}
      </h1>
      <p className="mt-1 break-all font-mono text-[11px] text-ink-faint">{id}</p>

      <section aria-labelledby="progress-title" className="card card-pad mt-6 max-w-xl">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="progress-title" className="h2">
            Progress
          </h2>
          <p className="text-sm text-ink-muted num" aria-label={`Elapsed ${Math.round(elapsed)} seconds`}>
            {fmtSecs(elapsed)}
          </p>
        </div>
        <p className="sr-only" aria-live="polite">
          {failed ? 'The check failed.' : st.state === 'queued' ? 'Queued.' : active ? `${active.label}.` : ''}
        </p>
        <ol className="mt-4 flex flex-col gap-3">
          {stages.map((s, i) => (
            <li key={s.id} className="flex items-center gap-3">
              <StageIcon state={s.state} n={i + 1} />
              <span className={`text-sm ${s.state === 'pending' ? 'text-ink-muted' : 'font-medium text-ink'}`}>{s.label}</span>
              <span className="sr-only"> — {s.state === 'done' ? 'done' : s.state === 'active' ? 'in progress' : s.state === 'failed' ? 'failed' : 'not started'}</span>
            </li>
          ))}
        </ol>
        {st.state === 'queued' && poll.phase === 'polling' && <p className="mt-4 text-xs text-ink-muted">Queued — starting in a moment.</p>}

        {failed && (
          <div role="alert" className={`mt-5 rounded-md border p-3 text-sm ${refused ? 'border-warn/40 bg-warn/10' : 'border-bad/30 bg-bad/5'}`}>
            <p className={`font-semibold ${refused ? 'text-ink' : 'text-bad'}`}>{notice.message}</p>
            {refused && <p className="mt-1 text-xs text-ink-muted">A safety rule, not an error. Paste the App.jsx instead.</p>}
            <Link to="/check" className="btn mt-3">
              {poll.status ? 'Try again' : 'Start a new check'}
            </Link>
          </div>
        )}
        {poll.phase === 'offline' && (
          <div role="alert" className="mt-5 rounded-md border border-warn/40 bg-warn/10 p-3 text-sm">
            <p className="flex items-center gap-1.5 font-semibold text-ink">
              <IconAlert /> The server did not answer three times in a row.
            </p>
            <p className="mt-1 text-xs text-ink-muted">The check keeps going on the server.</p>
            <button type="button" className="btn-primary mt-3" onClick={retry}>
              Resume checking
            </button>
          </div>
        )}
        {poll.phase === 'polling' && poll.networkErrors > 0 && <p className="mt-4 text-xs text-warn">Connection hiccup — retrying…</p>}

        <p className="mt-5 border-t border-line pt-4 text-xs text-ink-muted">
          Measured in a <strong className="font-semibold text-ink">Token Factory Sandbox</strong>. Usually 1–3 minutes
          {repairing ? `, plus a few minutes for the repair (≤ ${REPAIR_ROUNDS} Nemotron rounds)` : ''} — keep this page open.
        </p>
      </section>
    </div>
  );
}

function BackLink() {
  return (
    <Link to="/check" className="inline-flex w-fit items-center gap-1 rounded-sm text-xs font-medium text-ink-muted hover:text-ink">
      <IconArrowLeft /> Check another build
    </Link>
  );
}

// ------------------------------------------------------------------------------------------------ result

function CheckResultLoader({ id, status }: { id: string; status: LiveStatus | null }) {
  const check = useLoad<CheckBundle>(() => getCheck(id, status), [id]);
  if (check.status === 'loading') return <Loading label="Loading the check…" />;
  if (check.status === 'error') return <ErrorView title="Could not load this check" detail={check.error} />;
  return <CheckResult id={id} check={check.data} />;
}

export function CheckResult({ id, check }: { id: string; check: CheckBundle }) {
  const { report } = check;
  const base = useMemo(() => liveFilesBase(apiBase(), id), [id]);
  const asset = (rel: string | undefined) => (rel ? resolveAsset(base, rel) : null);
  const cells = useMemo(() => checkCells(report), [report]);
  const hurts = useMemo(() => hurtList(report), [report]);
  const summary = useMemo(() => checkSummary(report), [report]);
  const [bp, setBp] = useState<LiveBp>(report.worst ?? 'mobile');
  const activeCell = cells.findIndex((c) => c.score !== undefined && (c as { bp?: LiveBp }).bp === bp);

  return (
    <div className="page pt-6">
      <BackLink />
      <p className="eyebrow mt-3">Build check</p>
      <h1 className="display mt-1 break-words text-2xl sm:text-3xl">{title(check.source)}</h1>
      {check.source && 'url' in check.source && <p className="mt-1 break-all font-mono text-[12px] text-ink-muted">{check.source.url}</p>}

      {check.repair && <RepairCard id={id} repair={check.repair} />}

      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,21rem)_minmax(0,1fr)] lg:items-start">
        <div className="flex min-w-0 flex-col gap-4">
          <section aria-labelledby="score-title" className="card card-pad flex flex-col gap-4">
            <h2 id="score-title" className="eyebrow">
              Match · worst size{check.repair ? ' · before repair' : ''}
            </h2>
            <div className="flex items-center gap-4">
              <ScoreRing score={report.match} size={96} />
              <div className="text-sm">
                <p className="font-semibold text-ink">{bandLabel(report.match)}</p>
                {report.worst && <p className="text-xs text-ink-muted">worst: {cap(report.worst)}</p>}
              </div>
            </div>
            <BpBullets perBp={Object.fromEntries(LIVE_BPS.flatMap((b) => (report.perBp[b] != null ? [[b, report.perBp[b]]] : [])))} legend />
            <CopyLine text={summary} />
          </section>

          <section aria-labelledby="hurt-title" className="card card-pad">
            <h2 id="hurt-title" className="eyebrow">
              What hurt the score
            </h2>
            <HurtList hurts={hurts} />
          </section>
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          <section aria-labelledby="widths-title" className="card card-pad">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="widths-title" className="eyebrow">
                Every width
              </h2>
              <StripLegend />
            </div>
            <WidthStrip
              className="mt-6"
              cells={cells}
              interactive
              showSummary={false}
              active={activeCell >= 0 ? activeCell : null}
              onCellClick={(c) => {
                const b = (c as { bp?: LiveBp }).bp;
                if (b) setBp(b);
              }}
            />
          </section>

          <SizeView check={check} bp={bp} setBp={setBp} asset={asset} />

          {report.runtimeErrors.length > 0 && (
            <details className="card card-pad text-sm">
              <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-warn">
                <IconAlert /> {report.runtimeErrors.length} runtime error{report.runtimeErrors.length === 1 ? '' : 's'}
              </summary>
              <ul className="mt-2 flex flex-col gap-1">
                {report.runtimeErrors.slice(0, 5).map((e, i) => (
                  <li key={i} className="break-words font-mono text-[11px] text-ink-muted">
                    {e}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>

      <p className="mt-6 text-xs text-ink-muted">
        Measured in a Token Factory Sandbox{check.usd != null ? ` · ${fmtUsd(check.usd, 4)}` : ''}. Your build was not changed{check.repair && repairOutcome(check.repair).improved ? ' — the repair is a separate copy' : ''}.
      </p>
    </div>
  );
}

function StripLegend() {
  return (
    <p className="flex items-center gap-3 text-[11px] text-ink-muted" aria-hidden="true">
      <span className="inline-flex items-center gap-1">
        <span className="inline-block h-2.5 w-2.5 rounded-[2px] bg-good" /> fits
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="pc-hatch inline-block h-2.5 w-2.5 rounded-[2px] bg-bad" /> fails
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="pixel rounded-[2px] border border-line px-0.5 text-[10px] leading-none">90</span> design size
      </span>
    </p>
  );
}

function CopyLine({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="inset flex items-center gap-2 py-1.5 pl-3 pr-1.5">
      <p className="min-w-0 flex-1 break-words font-mono text-[11px] leading-snug text-ink">{text}</p>
      <button type="button" className="btn-icon h-8 min-h-0 w-8 shrink-0" onClick={copy} aria-label={copied ? 'Copied' : 'Copy summary'} title={copied ? 'Copied' : 'Copy summary'}>
        {copied ? <IconCheck /> : <IconCopy />}
      </button>
      <span className="sr-only" aria-live="polite">
        {copied ? 'Summary copied' : ''}
      </span>
    </div>
  );
}

function HurtList({ hurts }: { hurts: Hurt[] }) {
  if (!hurts.length)
    return (
      <p className="mt-3 flex items-center gap-1.5 text-sm text-good">
        <IconCheck /> Nothing major. Structure, layout and colour are all ≥ 95 %.
      </p>
    );
  return (
    <ul className="mt-3 flex flex-col gap-3">
      {hurts.map((h) => {
        const pct = Math.round(h.value * 100);
        return (
          <li key={h.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-1">
            <p className="text-sm">
              <span className="font-semibold text-ink">{h.label}</span> <span className="text-ink-muted">— {h.hint}</span>
            </p>
            <p className="text-xs text-ink-muted num">
              <span className="font-semibold text-ink">{pct} %</span> {h.bp}
            </p>
            <div className="col-span-2 h-1.5 overflow-hidden rounded-pill bg-ink/[0.07]" aria-hidden="true">
              <div className={`h-full rounded-pill ${pct < 75 ? 'bg-bad' : pct < 90 ? 'bg-warn' : 'bg-ok'}`} style={{ width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function SizeView({ check, bp, setBp, asset }: { check: CheckBundle; bp: LiveBp; setBp: (b: LiveBp) => void; asset: (rel: string | undefined) => string | null }) {
  const [mode, setMode] = useState<'side' | 'overlay'>('side');
  const [w, h] = FRAME_SIZES[bp];
  const data = check.report.bps[bp];
  const design = asset(check.design[bp]);
  const build = asset(check.build[bp]);
  const missing = data?.missingText ?? [];
  const marks = missingBoxes(missing, check.designTexts[bp] ?? []);
  const regions = data?.regions ?? [];

  return (
    <section aria-labelledby="size-title" className="card card-pad">
      <h2 id="size-title" className="sr-only">
        Per size
      </h2>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="seg" role="group" aria-label="Size">
          {LIVE_BPS.map((b) => (
            <button key={b} type="button" className="seg-item" aria-pressed={b === bp} onClick={() => setBp(b)}>
              {cap(b)} <span className="num text-ink-faint">{fmtScore(check.report.perBp[b])}</span>
            </button>
          ))}
        </div>
        <div className="seg" role="group" aria-label="View">
          <button type="button" className="seg-item" aria-pressed={mode === 'side'} onClick={() => setMode('side')}>
            Side by side
          </button>
          <button type="button" className="seg-item" aria-pressed={mode === 'overlay'} onClick={() => setMode('overlay')}>
            Overlay
          </button>
        </div>
      </div>

      {mode === 'side' ? (
        <div className={`mt-4 grid gap-3 ${bp === 'mobile' ? 'grid-cols-2' : 'grid-cols-1 sm:grid-cols-2'}`}>
          <figure className="min-w-0">
            <FittedFrame width={w} height={h}>
              {design ? <FrameImage src={design} alt={`${cap(bp)} design`} /> : <FrameEmpty>No design frame</FrameEmpty>}
              {design && marks.map((m, i) => <Mark key={i} box={m.box} frame={[w, h]} label={`Missing: ${m.text}`} dashed />)}
            </FittedFrame>
            <figcaption className="mt-1.5 text-center text-xs text-ink-muted">Design</figcaption>
          </figure>
          <figure className="min-w-0">
            <FittedFrame width={w} height={h}>
              {build ? <FrameImage src={build} alt={`${cap(bp)} build`} /> : <FrameEmpty>No capture at this size</FrameEmpty>}
              {build && regions.map((r, i) => <Mark key={i} box={r.box} frame={[w, h]} label={`Differs (${r.kind})`} />)}
            </FittedFrame>
            <figcaption className="mt-1.5 text-center text-xs text-ink-muted">Build</figcaption>
          </figure>
        </div>
      ) : (
        <div className="mt-4">
          {design && build ? (
            <CompareSlider design={design} render={build} width={w} height={h} label={`${cap(bp)}: drag to compare design and build`} labels={['Design', 'Build']} />
          ) : (
            <FittedFrame width={w} height={h}>
              <FrameEmpty>Both images are needed for the overlay</FrameEmpty>
            </FittedFrame>
          )}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-1.5 text-xs">
        {missing.length ? (
          <>
            <span className="mr-1 font-medium text-ink">Missing text</span>
            {missing.map((t, i) => (
              <span key={i} className="mono-chip max-w-full truncate border-bad/30 bg-bad/5 text-bad" title={t}>
                {t}
              </span>
            ))}
          </>
        ) : data ? (
          <span className="inline-flex items-center gap-1 text-good">
            <IconCheck /> All design text found
          </span>
        ) : null}
        {(marks.length > 0 || regions.length > 0) && (
          <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-ink-muted" aria-hidden="true">
            <span className="inline-block h-2.5 w-3.5 rounded-[2px] border-2 border-bad" /> differs
            <span className="ml-2 inline-block h-2.5 w-3.5 rounded-[2px] border-2 border-dashed border-bad" /> missing
          </span>
        )}
      </div>
    </section>
  );
}

function Mark({ box, frame, label, dashed = false }: { box: Box; frame: [number, number]; label: string; dashed?: boolean }) {
  const p = boxPct(box, frame);
  if (p.width <= 0 || p.height <= 0) return null;
  return (
    <span
      className={`pointer-events-none absolute rounded-[2px] border-2 border-bad ${dashed ? 'border-dashed' : 'bg-bad/10'}`}
      style={{ left: `${p.left}%`, top: `${p.top}%`, width: `${p.width}%`, height: `${p.height}%`, minWidth: 4, minHeight: 4 }}
      title={label}
      aria-hidden="true"
    />
  );
}
