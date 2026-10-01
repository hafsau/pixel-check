import { useState } from 'react';
import type { BpName, Candidate, Run } from '../lib/types';
import { BP_STROKE_VAR, bpBg, cap } from '../lib/format';
import { fmtScore } from '../lib/score';

interface Point {
  round: number;
  match: number;
  perBp: Partial<Record<BpName, number>>;
  worst: BpName | null;
}

const W = 340;
const H = 190;
const M = { top: 10, right: 10, bottom: 24, left: 28 };

/**
 * Match (worst breakpoint) per round, with each breakpoint's score as thin lines.
 * The worst breakpoint of each round gets a large dot. Only rounds up to `upToRound` are drawn.
 */
export function ScoreChart({ run, upToRound, bps }: { run: Run; upToRound: number; bps: BpName[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const byId = new Map<string, Candidate>(run.candidates.map((c) => [c.id, c]));
  const history = run.result.history?.length ? run.result.history : run.rounds.map((r) => r.match);
  const rounds = run.rounds.length ? run.rounds : history.map((m, i) => ({ round: i, best: '', match: m, spend_usd: 0 }));
  const all: Point[] = rounds.map((r, i) => {
    const c = byId.get(r.best);
    return { round: r.round, match: history[i] ?? r.match, perBp: c?.per_bp ?? {}, worst: c?.worst ?? null };
  });
  const pts = all.filter((p) => p.round <= upToRound);
  const maxRound = Math.max(1, ...all.map((p) => p.round));
  // Line charts may start above zero: floor the domain 10+ points under the lowest value so small gains stay visible.
  const lowest = Math.min(100, ...all.flatMap((p) => [p.match, ...bps.map((b) => p.perBp[b] ?? 100)]));
  const lo = Math.max(0, Math.floor((lowest - 10) / 10) * 10);
  const tickStep = (100 - lo) / 4;
  const ticks = [0, 1, 2, 3, 4].map((k) => Math.round(lo + k * tickStep));

  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const x = (r: number) => M.left + (r / maxRound) * iw;
  const y = (v: number) => M.top + (1 - (Math.max(lo, Math.min(100, v)) - lo) / (100 - lo)) * ih;
  const path = (vals: (number | undefined)[]) =>
    vals
      .map((v, i) => (v == null ? null : `${x(pts[i].round).toFixed(1)},${y(v).toFixed(1)}`))
      .filter(Boolean)
      .map((p, i) => `${i ? 'L' : 'M'}${p}`)
      .join(' ');

  const hp = hover != null ? pts.find((p) => p.round === hover) : null;
  const summary = pts.length
    ? `Match by round: ${pts.map((p) => `round ${p.round} ${fmtScore(p.match)}${p.worst ? ` (${p.worst} worst)` : ''}`).join('; ')}.`
    : 'No rounds completed yet.';

  return (
    <figure className="relative">
      <ul className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-muted" aria-hidden="true">
        <li className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-pill bg-ink" /> Match
        </li>
        {bps.map((b) => (
          <li key={b} className="flex items-center gap-1.5">
            <span className={`h-0.5 w-4 rounded-pill ${bpBg(b)}`} /> {cap(b)}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-pill border-2 border-surface bg-ink-muted ring-1 ring-ink-muted" /> Worst
        </li>
      </ul>
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full overflow-visible" role="img" aria-label={summary} onMouseLeave={() => setHover(null)}>
        {/* grid */}
        {ticks.map((v) => (
          <g key={v}>
            <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} stroke="rgb(var(--c-line))" strokeWidth={1} />
            <text x={M.left - 6} y={y(v)} dy="0.32em" textAnchor="end" fontSize={10} fill="rgb(var(--c-ink-faint))" className="num">
              {v}
            </text>
          </g>
        ))}
        {all.map((p) => (
          <text key={p.round} x={x(p.round)} y={H - 8} textAnchor="middle" fontSize={10} fill="rgb(var(--c-ink-faint))">
            R{p.round}
          </text>
        ))}

        {/* per-breakpoint lines */}
        {bps.map((b) => (
          <path key={b} d={path(pts.map((p) => p.perBp[b]))} fill="none" stroke={BP_STROKE_VAR[b] ?? 'rgb(var(--c-ink-muted))'} strokeWidth={1.5} strokeOpacity={0.55} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {/* match line */}
        <path d={path(pts.map((p) => p.match))} fill="none" stroke="rgb(var(--c-ink))" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {/* worst-breakpoint markers */}
        {pts.map((p) => (
          <circle
            key={p.round}
            cx={x(p.round)}
            cy={y(p.match)}
            r={hover === p.round ? 6 : 4.5}
            fill={p.worst ? BP_STROKE_VAR[p.worst] ?? 'rgb(var(--c-ink))' : 'rgb(var(--c-ink))'}
            stroke="rgb(var(--c-surface))"
            strokeWidth={2}
          />
        ))}

        {/* hover crosshair */}
        {hp && <line x1={x(hp.round)} x2={x(hp.round)} y1={M.top} y2={M.top + ih} stroke="rgb(var(--c-ink-faint))" strokeDasharray="2 3" />}
        {/* hit targets: one column per round */}
        {pts.map((p) => (
          <rect
            key={p.round}
            x={x(p.round) - iw / maxRound / 2}
            y={M.top}
            width={iw / maxRound}
            height={ih}
            fill="transparent"
            onMouseEnter={() => setHover(p.round)}
          />
        ))}
      </svg>
      {hp && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-line bg-surface px-2.5 py-2 text-xs shadow-card"
          style={{ left: `${(x(hp.round) / W) * 100}%`, top: 24, transform: `translateX(${hp.round > maxRound / 2 ? '-105%' : '5%'})` }}
        >
          <p className="font-semibold">Round {hp.round}</p>
          <p className="num">
            Match <strong>{fmtScore(hp.match)}</strong>
            {hp.worst ? <span className="text-ink-muted"> · {hp.worst} worst</span> : null}
          </p>
          {bps.map((b) => (
            <p key={b} className="flex items-center gap-1.5 text-ink-muted num">
              <span className={`h-1.5 w-1.5 rounded-pill ${bpBg(b)}`} /> {cap(b)} {fmtScore(hp.perBp[b])}
            </p>
          ))}
        </div>
      )}
      <figcaption className="sr-only">{summary}</figcaption>
    </figure>
  );
}
