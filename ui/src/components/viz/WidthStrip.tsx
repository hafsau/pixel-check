import type { CellState, StripCell } from '../../lib/viz';
import { stripSummary } from '../../lib/viz';

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
}: {
  cells: StripCell[];
  labels?: 'all' | 'none' | number[];
  summary?: string;
  showSummary?: boolean;
  active?: number | null;
  className?: string;
  height?: string;
}) {
  const text = summary ?? stripSummary(cells);
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
