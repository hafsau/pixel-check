import { useMemo } from 'react';
import type { Candidate, Run } from '../lib/types';
import { candidateStatus } from '../lib/types';
import { bestPath, strategyLabel } from '../lib/playback';
import { ScoreBadge } from './ScoreBadge';

const NODE_W = 148;
const NODE_H = 58;
const GAP_X = 44;
const GAP_Y = 12;
const HEAD = 26; // round label height

interface Laid {
  c: Candidate;
  x: number;
  y: number;
  index: number;
}

/**
 * Candidates grouped by round (columns), with edges to their parent.
 * Best path is highlighted; disqualified nodes are red; nodes not yet revealed by the
 * replay are faded. Each node is a button that shows that candidate in the rows.
 */
export function BranchTree({
  run,
  revealedIndex,
  selectedId,
  bestId,
  onSelect,
}: {
  run: Run;
  revealedIndex: number;
  selectedId: string;
  bestId: string | null;
  onSelect: (id: string) => void;
}) {
  const { nodes, byId, width, height, rounds } = useMemo(() => layout(run), [run]);
  const onPath = useMemo(() => bestPath(run), [run]);

  return (
    <section aria-labelledby="tree-title" className="card card-pad">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="tree-title" className="h2">
          Branches
        </h2>
        <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-muted">
          <li className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-pill bg-accent" aria-hidden="true" /> Path to final best
          </li>
          <li className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm border border-bad bg-bad/10" aria-hidden="true" /> Disqualified
          </li>
          <li className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm border border-dashed border-ink-faint" aria-hidden="true" /> Not rendered
          </li>
        </ul>
      </div>
      <p className="mt-1 text-xs text-ink-muted">Each round forks branches from the current best. Select a node to show it in the rows above.</p>

      <div className="mt-4 overflow-x-auto pb-2">
        <div className="relative" style={{ width, height }}>
          {rounds.map((r, i) => (
            <p key={r} className="absolute top-0 text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-muted" style={{ left: i * (NODE_W + GAP_X) }}>
              Round {r}
            </p>
          ))}
          <svg className="pointer-events-none absolute inset-0" width={width} height={height} aria-hidden="true">
            {nodes.map((n) => {
              const p = n.c.parent ? byId.get(n.c.parent) : undefined;
              if (!p) return null;
              const x1 = p.x + NODE_W;
              const y1 = p.y + NODE_H / 2;
              const x2 = n.x;
              const y2 = n.y + NODE_H / 2;
              const mx = (x1 + x2) / 2;
              const hot = onPath.has(n.c.id) && onPath.has(p.c.id);
              const visible = n.index <= revealedIndex;
              return (
                <path
                  key={n.c.id}
                  d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`}
                  fill="none"
                  stroke={hot ? 'rgb(var(--c-accent))' : 'rgb(var(--c-line))'}
                  strokeWidth={hot ? 2 : 1.5}
                  opacity={visible ? 1 : 0.35}
                />
              );
            })}
          </svg>
          {nodes.map((n) => (
            <TreeNode
              key={n.c.id}
              n={n}
              revealed={n.index <= revealedIndex}
              selected={n.c.id === selectedId}
              isBest={n.c.id === bestId}
              onPath={onPath.has(n.c.id)}
              onSelect={onSelect}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

function TreeNode({
  n,
  revealed,
  selected,
  isBest,
  onPath,
  onSelect,
}: {
  n: Laid;
  revealed: boolean;
  selected: boolean;
  isBest: boolean;
  onPath: boolean;
  onSelect: (id: string) => void;
}) {
  const c = n.c;
  const status = candidateStatus(c);
  const tipId = `tip-${c.id}`;
  const border =
    status === 'disqualified'
      ? 'border-bad bg-bad/10'
      : status === 'no-render'
        ? 'border-dashed border-ink-faint bg-surface'
        : onPath
          ? 'border-accent bg-surface'
          : 'border-line bg-surface';
  return (
    <div className="group absolute" style={{ left: n.x, top: n.y, width: NODE_W, height: NODE_H }}>
      <button
        type="button"
        onClick={() => onSelect(c.id)}
        aria-pressed={selected}
        aria-describedby={c.reason ? tipId : undefined}
        aria-label={`Candidate ${c.id}, round ${c.round}, ${strategyLabel(c.strategy)}, ${
          status === 'disqualified' ? 'disqualified' : status === 'no-render' ? 'not rendered' : `match ${c.match.toFixed(1)}`
        }${isBest ? ', current best' : ''}`}
        className={`flex h-full w-full flex-col justify-between rounded-md border px-2.5 py-1.5 text-left transition-[opacity,box-shadow] ${border} ${
          selected ? 'ring-2 ring-accent ring-offset-2 ring-offset-surface' : ''
        } ${revealed ? '' : 'opacity-40'}`}
      >
        <span className="flex w-full items-center justify-between gap-1">
          <span className={`truncate text-xs font-semibold ${status === 'disqualified' ? 'text-bad' : ''}`}>{strategyLabel(c.strategy)}</span>
          <ScoreBadge score={c.match} dq={status === 'disqualified'} empty={status === 'no-render'} />
        </span>
        <span className="flex w-full items-center justify-between gap-1">
          <code className="font-mono text-[10px] text-ink-faint">{c.id}</code>
          {isBest && <span className="text-[10px] font-semibold text-accent-strong">BEST</span>}
        </span>
      </button>
      {c.reason && (
        <span
          id={tipId}
          role="tooltip"
          className="pointer-events-none absolute left-0 top-full z-20 mt-1 hidden w-56 rounded-md border border-line bg-surface p-2 text-xs text-ink shadow-card group-hover:block group-focus-within:block"
        >
          <span className={`font-semibold ${status === 'disqualified' ? 'text-bad' : ''}`}>
            {status === 'disqualified' ? 'Disqualified: ' : 'Not rendered: '}
          </span>
          {c.reason}
        </span>
      )}
    </div>
  );
}

function layout(run: Run) {
  const rounds = [...new Set(run.candidates.map((c) => c.round))].sort((a, b) => a - b);
  const perRound = new Map<number, number>();
  const nodes: Laid[] = run.candidates.map((c, index) => {
    const k = perRound.get(c.round) ?? 0;
    perRound.set(c.round, k + 1);
    const col = rounds.indexOf(c.round);
    return { c, index, x: col * (NODE_W + GAP_X), y: HEAD + k * (NODE_H + GAP_Y) };
  });
  const maxRows = Math.max(1, ...perRound.values());
  return {
    nodes,
    byId: new Map(nodes.map((n) => [n.c.id, n])),
    rounds,
    width: rounds.length * (NODE_W + GAP_X) - GAP_X,
    height: HEAD + maxRows * (NODE_H + GAP_Y) + 56, // room for the tooltip under the last row
  };
}
