import type { CellState, StripCell } from '../../lib/viz';
import { stripSummary } from '../../lib/viz';
import { fmtScore } from '../../lib/score';

const FILL: Record<CellState, string> = {
  pending: 'bg-ink/[0.07]',
  pass: 'bg-good',
  overflow: 'bg-accent pc-hatch',
  overlap: 'bg-accent pc-hatch',
  fail: 'bg-bad pc-hatch',
};

/**
 * A heat strip: one cell per measured width, green = fits, orange/red hatched = overflow / overlap / other failure.
 * The visible caption (or a screen-reader summary) names every failing width, so colour is never the only signal.
 */
export function WidthStrip({
  cells,
  labels = 'all',
  summary,
  showSummary = true,
  active = null,
  className = '',
  height = 'h-3',
  interactive = false,
  onCellClick,
}: {
  cells: StripCell[];
  labels?: 'all' | 'none' | number[];
  summary?: string;
  showSummary?: boolean;
  active?: number | null;
  className?: string;
  height?: string;
  /** Tall, focusable tiles: scores inside design sizes, the reason in a tooltip on hover / focus. */
  interactive?: boolean;
  onCellClick?: (cell: StripCell, index: number) => void;
}) {
  const text = summary ?? stripSummary(cells);
  if (interactive) return <TileStrip cells={cells} text={text} showSummary={showSummary} active={active} className={className} onCellClick={onCellClick} />;
  const lab = (w: number) => labels === 'all' || (Array.isArray(labels) && labels.includes(w));
  return (
    <figure className={className}>
      <div className="flex gap-[3px]" aria-hidden="true">
        {cells.map((c, i) => (
          <span
            key={c.width}
            title={`${c.width} px — ${c.state === 'pass' ? 'fits' : c.state === 'pending' ? 'not measured' : (c.detail ?? c.state)}`}
            className={`relative min-w-0 flex-1 rounded-[3px] transition-colors duration-300 ${height} ${FILL[c.state]} ${active === i ? 'ring-2 ring-ink ring-offset-1 ring-offset-surface' : ''}`}
          />
        ))}
      </div>
      {labels !== 'none' && (
        <div className="mt-1 flex gap-[3px] font-mono text-[10px] text-ink-faint" aria-hidden="true">
          {cells.map((c) => (
            <span key={c.width} className={`min-w-0 flex-1 text-center num ${c.state !== 'pass' && c.state !== 'pending' ? 'font-medium text-ink' : ''}`}>
              {lab(c.width) ? c.width : ''}
            </span>
          ))}
        </div>
      )}
      <figcaption className={showSummary ? 'mt-1.5 text-xs text-ink-muted' : 'sr-only'}>{text}</figcaption>
    </figure>
  );
}

function TileStrip({
  cells,
  text,
  showSummary,
  active,
  className,
  onCellClick,
}: {
  cells: StripCell[];
  text: string;
  showSummary: boolean;
  active: number | null;
  className: string;
  onCellClick?: (cell: StripCell, index: number) => void;
}) {
  const why = (c: StripCell) => (c.state === 'pass' ? 'fits' : c.state === 'pending' ? 'not measured' : (c.detail ?? 'fails'));
  return (
    <figure className={className}>
      <ul className="flex gap-1">
        {cells.map((c, i) => {
          const scored = c.score !== undefined;
          const tip = `${c.width} px${scored ? ` · ${fmtScore(c.score)}` : ''} — ${why(c)}`;
          const right = i >= cells.length / 2;
          return (
            <li key={c.width} className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => onCellClick?.(c, i)}
                aria-label={tip}
                aria-pressed={onCellClick && scored ? active === i : undefined}
                className={`group relative flex h-11 w-full items-center justify-center rounded-[4px] transition-colors duration-300 ${FILL[c.state]} ${
                  active === i ? 'ring-2 ring-ink ring-offset-2 ring-offset-surface' : ''
                } ${onCellClick && scored ? 'cursor-pointer' : 'cursor-default'}`}
              >
                {scored && (
                  <span className="pixel rounded-[3px] bg-surface/95 px-1 text-[11px] leading-[1.35] text-ink num sm:text-[13px]" aria-hidden="true">
                    {fmtScore(c.score, c.score != null && c.score >= 99.95 ? 0 : 1)}
                  </span>
                )}
                <span
                  role="tooltip"
                  className={`pointer-events-none invisible absolute bottom-full z-10 mb-2 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-[11px] font-medium text-bg opacity-0 shadow-lift transition-opacity group-hover:visible group-hover:opacity-100 group-focus-visible:visible group-focus-visible:opacity-100 ${
                    right ? 'right-0' : 'left-0'
                  }`}
                  aria-hidden="true"
                >
                  {tip}
                </span>
              </button>
              <span className={`mt-1 block text-center font-mono text-[10px] num ${scored ? 'font-semibold text-ink' : c.state === 'fail' ? 'font-medium text-bad' : 'text-ink-faint'}`} aria-hidden="true">
                {c.width}
              </span>
            </li>
          );
        })}
      </ul>
      <figcaption className={showSummary ? 'mt-1.5 text-xs text-ink-muted' : 'sr-only'}>{text}</figcaption>
    </figure>
  );
}
