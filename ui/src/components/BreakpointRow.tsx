import type { Breakpoint, Candidate } from '../lib/types';
import { candidateStatus } from '../lib/types';
import { bpBg, cap } from '../lib/format';
import { ScoreBadge } from './ScoreBadge';
import { FittedFrame, FrameEmpty, FrameImage } from './FittedFrame';
import { CompareSlider } from './CompareSlider';
import { DiffOverlay } from './DiffOverlay';
import type { CompareMode } from './CompareModeToggle';

/** One breakpoint: design | render | comparison. */
export function BreakpointRow({
  bp,
  designSrc,
  renderSrc,
  candidate,
  mode,
}: {
  bp: Breakpoint;
  designSrc: string | null;
  renderSrc: string | null;
  candidate: Candidate;
  mode: CompareMode;
}) {
  const status = candidateStatus(candidate);
  const score = candidate.per_bp[bp.name];
  const isWorst = status === 'scored' && candidate.worst === bp.name;
  const name = cap(bp.name);

  return (
    <section aria-label={`${name} ${bp.width}×${bp.height}`} className="card card-pad">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-pill ${bpBg(bp.name)}`} aria-hidden="true" />
          <h3 className="text-sm font-semibold">{name}</h3>
          <span className="font-mono text-[11px] text-ink-faint">
            {bp.width}×{bp.height}
          </span>
          {isWorst && <span className="chip border-bad/30 bg-bad/10 text-bad">Worst</span>}
        </div>
        <ScoreBadge score={score} dq={status === 'disqualified'} empty={status === 'no-render' || score == null} size="md" />
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Cell title="Design">
          <FittedFrame width={bp.width} height={bp.height}>
            {designSrc ? <FrameImage src={designSrc} alt={`${name} design frame`} /> : <FrameEmpty>No design frame</FrameEmpty>}
          </FittedFrame>
        </Cell>
        <Cell title="Render">
          <FittedFrame width={bp.width} height={bp.height}>
            {renderSrc ? (
              <FrameImage src={renderSrc} alt={`${name} render of candidate ${candidate.id}`} />
            ) : (
              <FrameEmpty>{candidate.reason ? `Not rendered: ${candidate.reason}` : 'Not rendered'}</FrameEmpty>
            )}
          </FittedFrame>
        </Cell>
        <Cell title={mode === 'slider' ? 'Compare' : 'Difference'}>
          {designSrc && renderSrc ? (
            mode === 'slider' ? (
              <CompareSlider design={designSrc} render={renderSrc} width={bp.width} height={bp.height} label={`${name}: design versus render`} />
            ) : (
              <DiffOverlay design={designSrc} render={renderSrc} width={bp.width} height={bp.height} label={`${name}: difference between design and render; black means identical`} />
            )
          ) : (
            <FittedFrame width={bp.width} height={bp.height}>
              <FrameEmpty>Nothing to compare</FrameEmpty>
            </FittedFrame>
          )}
        </Cell>
      </div>
    </section>
  );
}

function Cell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <figure className="flex min-w-0 flex-col gap-1.5">
      <figcaption className="text-[11px] font-medium uppercase tracking-[0.06em] text-ink-muted">{title}</figcaption>
      {children}
    </figure>
  );
}
