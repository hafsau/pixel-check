import { useMemo, useState } from 'react';
import { useLoad } from '../lib/data';
import { getRepairCode } from '../lib/liveApi';
import { downloadBlob } from '../lib/download';
import { cap } from '../lib/format';
import { fmtScore } from '../lib/score';
import {
  diffHunks,
  diffLines,
  diffStats,
  fmtDelta,
  linesKeptLabel,
  repairOutcome,
  repairSizes,
  repairSummary,
  roundBars,
  splitLines,
  widthFailsLabel,
  type Hunk,
  type Repair,
  type RepairOutcome,
} from '../lib/repair';
import { IconArrowRight, IconCheck, IconCopy, IconDownload } from './Icons';

/** "Repair" card on a check result: before → after, per size, rounds, and the class-only diff of the App.jsx. */
export function RepairCard({ id, repair }: { id: string; repair: Repair }) {
  const o = useMemo(() => repairOutcome(repair), [repair]);
  const summary = useMemo(() => repairSummary(repair, o), [repair, o]);
  const rounds = Math.max(0, ...repair.history.map((h) => h.round));

  return (
    <section aria-labelledby="repair-title" className="card card-pad mt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 id="repair-title" className="eyebrow">
          Repair · Nemotron
        </h2>
        <p className="text-[11px] text-ink-muted num">
          {rounds} round{rounds === 1 ? '' : 's'}
          {repair.usd != null ? ` · $${repair.usd.toFixed(2)}` : ''}
        </p>
      </div>

      <div className={`mt-4 grid gap-5 ${o.unchanged ? 'sm:grid-cols-[minmax(0,1fr)_auto]' : 'lg:grid-cols-[auto_minmax(0,1fr)_auto]'} lg:items-start`}>
        <Headline o={o} repair={repair} />
        {!o.unchanged && <SizeRows repair={repair} />}
        <Rounds repair={repair} kept={o.keptRound} />
      </div>

      <p className="sr-only">{summary}</p>
      {!o.unchanged && <CodeDiff id={id} repair={repair} />}
    </section>
  );
}

function Headline({ o, repair }: { o: RepairOutcome; repair: Repair }) {
  if (o.unchanged)
    return (
      <div className="min-w-0">
        <p className="flex items-baseline gap-2">
          <span className="pixel text-4xl leading-none text-ink">{fmtScore(o.before)}</span>
          <span className="text-xs text-ink-muted">worst size</span>
        </p>
        <p className="mt-3 text-sm font-medium text-ink">No round improved it — your code is unchanged.</p>
        <p className="mt-1 text-xs text-ink-muted">The repair only edits Tailwind classes; it cannot add, move or remove elements.</p>
      </div>
    );
  const kept = linesKeptLabel(repair.linesKept);
  const widths = widthFailsLabel(o.fluidBefore, o.fluidAfter);
  return (
    <div className="min-w-0">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1" aria-label={`Worst size ${fmtScore(o.before)} to ${fmtScore(o.after)}, ${fmtDelta(o.delta)}`}>
        <span className="pixel text-3xl leading-none text-ink-muted sm:text-4xl">{fmtScore(o.before)}</span>
        <span className="text-ink-faint" aria-hidden="true">
          <IconArrowRight />
        </span>
        <span className="pixel text-4xl leading-none text-ink sm:text-5xl">{fmtScore(o.after)}</span>
        <span className={`chip num ${o.delta != null && o.delta > 0 ? 'border-good/30 bg-good/10 text-good' : ''}`}>{fmtDelta(o.delta)}</span>
      </p>
      <p className="mt-1.5 text-xs text-ink-muted">worst size, before → after</p>
      <ul className="mt-3 flex flex-wrap gap-1.5">
        {widths && (
          <li className={`chip num ${o.fluidAfter < o.fluidBefore ? 'text-good' : o.fluidAfter > o.fluidBefore ? 'text-bad' : ''}`}>{widths}</li>
        )}
        {kept && <li className="chip num">{kept}</li>}
      </ul>
    </div>
  );
}

/** Per size: a dumbbell from before (hollow) to after (filled) on the 0–100 scale. */
function SizeRows({ repair }: { repair: Repair }) {
  const rows = repairSizes(repair);
  return (
    <dl className="grid min-w-0 gap-2.5 self-center">
      {rows.map((r) => {
        const lo = Math.min(r.before ?? 0, r.after ?? 0);
        const hi = Math.max(r.before ?? 0, r.after ?? 0);
        const tone = r.delta == null || Math.abs(r.delta) < 0.05 ? 'same' : r.delta > 0 ? 'up' : 'down';
        return (
          <div key={r.bp} className="grid grid-cols-[3.75rem_minmax(0,1fr)_auto] items-center gap-2.5 text-xs">
            <dt className="text-ink-muted">{cap(r.bp)}</dt>
            <dd className="relative h-3" aria-hidden="true">
              <span className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-line" />
              {r.before != null && r.after != null && (
                <span className={`absolute top-1/2 h-[3px] -translate-y-1/2 rounded-pill ${SEG[tone]}`} style={{ left: `${clamp(lo)}%`, width: `${clamp(hi) - clamp(lo)}%` }} />
              )}
              {r.before != null && (
                <span className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-pill border-2 border-ink-faint bg-surface" style={{ left: `${clamp(r.before)}%` }} />
              )}
              {r.after != null && (
                <span className={`absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-pill ${DOT[tone]}`} style={{ left: `${clamp(r.after)}%` }} />
              )}
            </dd>
            <dd className="whitespace-nowrap text-right num text-ink-muted">
              {fmtScore(r.before)} → <span className="font-semibold text-ink">{fmtScore(r.after)}</span>
            </dd>
          </div>
        );
      })}
      <div className="flex items-center gap-3 text-[11px] text-ink-muted" aria-hidden="true">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-pill border-2 border-ink-faint" /> before
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-pill bg-ink" /> after
        </span>
        <span className="ml-auto num">0–100</span>
      </div>
    </dl>
  );
}

const clamp = (v: number) => Math.min(100, Math.max(0, v));
const SEG = { up: 'bg-good', down: 'bg-bad', same: 'bg-ink-faint' } as const;
const DOT = { up: 'bg-good', down: 'bg-bad', same: 'bg-ink' } as const;

/** Rounds as tiny bars (worst size, 0–100); the kept round is orange. */
function Rounds({ repair, kept }: { repair: Repair; kept: number | null }) {
  const bars = roundBars(repair, kept);
  if (bars.length < 2) return null;
  const label = bars.map((b) => `round ${b.round}: ${fmtScore(b.worst)}${b.kept ? ' (kept)' : ''}`).join(', ');
  return (
    <figure className="min-w-0">
      <div className="flex h-16 items-stretch gap-1.5" role="img" aria-label={`Worst size per round — ${label}`}>
        {bars.map((b) => (
          <div key={b.round} className="flex w-6 flex-col items-center gap-0.5">
            <span className={`text-[10px] leading-none num ${b.kept ? 'font-semibold text-ink' : 'text-ink-faint'}`}>{b.worst == null ? '—' : Math.round(b.worst)}</span>
            <span className="relative w-full flex-1 overflow-hidden rounded-t-[2px] bg-ink/[0.05]">
              <span className={`absolute inset-x-0 bottom-0 ${b.kept ? 'bg-accent' : 'bg-ink/25'}`} style={{ height: `${Math.max(3, b.pct)}%` }} />
            </span>
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1.5 border-t border-line pt-1" aria-hidden="true">
        {bars.map((b) => (
          <span key={b.round} className={`w-6 text-center font-mono text-[10px] ${b.kept ? 'text-ink' : 'text-ink-faint'}`}>
            R{b.round}
          </span>
        ))}
      </div>
      <figcaption className="mt-1 text-[11px] text-ink-muted">
        <span className="mr-1 inline-block h-2 w-2 rounded-[2px] bg-accent align-middle" aria-hidden="true" />
        kept{kept === 0 ? ' (original)' : ''}
      </figcaption>
    </figure>
  );
}

// ------------------------------------------------------------------------------------------------ code

function CodeDiff({ id, repair }: { id: string; repair: Repair }) {
  const files = useLoad(() => getRepairCode(id, repair), [id, repair.code, repair.original]);
  return (
    <div className="mt-5 border-t border-line pt-4">
      {files.status === 'loading' && <p className="text-xs text-ink-muted">Loading the code…</p>}
      {files.status === 'error' && <p className="text-xs text-bad">{files.error}</p>}
      {files.status === 'ready' && <DiffView original={files.data.original} repaired={files.data.repaired} />}
    </div>
  );
}

function DiffView({ original, repaired }: { original: string; repaired: string }) {
  const { hunks, stats } = useMemo(() => {
    const ops = diffLines(splitLines(original), splitLines(repaired));
    return { hunks: diffHunks(ops, 2), stats: diffStats(ops) };
  }, [original, repaired]);
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(repaired);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };
  const download = () => downloadBlob(repaired, 'App.jsx', 'text/javascript');

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-baseline gap-2 text-sm font-semibold">
          What changed
          <span className="font-mono text-xs font-normal num">
            <span className="text-good">+{stats.added}</span> <span className="text-bad">−{stats.removed}</span>
          </span>
        </h3>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn min-h-[34px] text-xs" onClick={copy}>
            {copied ? <IconCheck /> : <IconCopy />}
            <span aria-live="polite">{copied ? 'Copied' : 'Copy'}</span>
          </button>
          <button type="button" className="btn-primary min-h-[34px] text-xs" onClick={download}>
            <IconDownload /> Download repaired App.jsx
          </button>
        </div>
      </div>
      {hunks.length === 0 ? (
        <p className="mt-3 text-sm text-ink-muted">The files are identical.</p>
      ) : (
        <div className="mt-3 max-h-[28rem] overflow-auto rounded-md border border-line bg-surface" tabIndex={0} role="region" aria-label="Changes from your App.jsx to the repaired one">
          <table className="w-max min-w-full border-collapse font-mono text-[12px] leading-[1.6]">
            <tbody>
              {hunks.map((h, i) => (
                <HunkRows key={i} hunk={h} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function HunkRows({ hunk }: { hunk: Hunk }) {
  return (
    <>
      <tr className="bg-surface-2 text-ink-muted">
        <td colSpan={4} className="sticky left-0 whitespace-pre px-3 py-0.5 text-[11px]">
          @@ −{hunk.aStart},{hunk.aLines} +{hunk.bStart},{hunk.bLines} @@
        </td>
      </tr>
      {hunk.lines.map((l, i) => {
        const row = l.kind === 'add' ? 'bg-good/10' : l.kind === 'del' ? 'bg-bad/10' : '';
        const sign = l.kind === 'add' ? '+' : l.kind === 'del' ? '−' : ' ';
        const signTone = l.kind === 'add' ? 'text-good' : l.kind === 'del' ? 'text-bad' : 'text-ink-faint';
        return (
          <tr key={i} className={row}>
            <td className="select-none px-2 text-right text-ink-faint num" aria-hidden="true">
              {l.a ?? ''}
            </td>
            <td className="select-none border-r border-line px-2 text-right text-ink-faint num" aria-hidden="true">
              {l.b ?? ''}
            </td>
            <td className={`select-none pl-2 pr-1 font-semibold ${signTone}`}>
              <span aria-hidden="true">{sign}</span>
              <span className="sr-only">{l.kind === 'add' ? 'added' : l.kind === 'del' ? 'removed' : ''}</span>
            </td>
            <td className="whitespace-pre pr-4 text-ink">{l.text || ' '}</td>
          </tr>
        );
      })}
    </>
  );
}
