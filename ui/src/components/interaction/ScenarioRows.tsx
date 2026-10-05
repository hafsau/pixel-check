import type { Attempt, Breakpoint, Interaction, ScenarioSlot } from '../../lib/types';
import { runAsset } from '../../lib/data';
import { bpBg, cap } from '../../lib/format';
import type { ChecklistRow, CheckId } from '../../lib/interactions';
import { FittedFrame, FrameEmpty, FrameImage } from '../FittedFrame';
import { CompareSlider } from '../CompareSlider';
import { DiffOverlay } from '../DiffOverlay';
import type { CompareMode } from '../CompareModeToggle';
import { ScoreBadge } from '../ScoreBadge';
import { StatusIcon } from '../PassPill';

export const SCENARIOS: { slot: ScenarioSlot; label: string; steps: string; target: 'base' | 'state'; check: CheckId }[] = [
  { slot: 'base', label: 'Before click', steps: 'Page loads, nothing touched', target: 'base', check: 'base' },
  { slot: 'open', label: 'Opened', steps: 'Click the trigger', target: 'state', check: 'opens' },
  { slot: 'closed', label: 'Clicked again', steps: 'Click the trigger, click it again', target: 'base', check: 'closes' },
  { slot: 'esc', label: 'Escape', steps: 'Click the trigger, press Escape', target: 'base', check: 'escape' },
  { slot: 'kbd', label: 'Keyboard', steps: 'Focus the trigger, press Enter', target: 'state', check: 'keyboard' },
];

/** One card per breakpoint: the frame the scenario must match | the sandbox capture | comparison, plus the scenario strip. */
export function ScenarioRows({
  ix,
  attempt,
  rows,
  slot,
  onSlot,
  mode,
}: {
  ix: Interaction;
  attempt: Attempt;
  rows: ChecklistRow[];
  slot: ScenarioSlot;
  onSlot: (s: ScenarioSlot) => void;
  mode: CompareMode;
}) {
  return (
    <div className="flex flex-col gap-3">
      {ix.breakpoints.map((bp) => (
        <ScenarioRow key={bp.name} ix={ix} bp={bp} attempt={attempt} rows={rows} slot={slot} onSlot={onSlot} mode={mode} />
      ))}
    </div>
  );
}

function ScenarioRow({ ix, bp, attempt, rows, slot, onSlot, mode }: { ix: Interaction; bp: Breakpoint; attempt: Attempt; rows: ChecklistRow[]; slot: ScenarioSlot; onSlot: (s: ScenarioSlot) => void; mode: CompareMode }) {
  const sc = SCENARIOS.find((s) => s.slot === slot)!;
  const d = ix.design[bp.name];
  const targetRel = sc.target === 'state' ? d?.state : d?.base;
  const target = targetRel ? runAsset(ix.id, targetRel) : null;
  const capRel = attempt.captures[bp.name]?.[slot];
  const capture = capRel ? runAsset(ix.id, capRel) : null;
  const name = cap(bp.name);
  const status = (check: CheckId) => rows.find((r) => r.id === check)?.cells[bp.name]?.status ?? 'skipped';
  const score = (check: CheckId) => rows.find((r) => r.id === check)?.cells[bp.name]?.score;
  const trig = ix.trigger[bp.name];
  const targetName = sc.target === 'state' ? 'State frame' : 'Design (closed)';

  return (
    <section aria-label={`${name} ${bp.width}×${bp.height}`} className="card card-pad">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-pill ${bpBg(bp.name)}`} aria-hidden="true" />
          <h3 className="text-sm font-semibold">{name}</h3>
          <span className="font-mono text-[11px] text-ink-faint">
            {bp.width}×{bp.height}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <span>State frame match</span>
          <ScoreBadge score={attempt.state_scores[bp.name]} empty={attempt.state_scores[bp.name] == null} size="md" />
        </div>
      </header>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3">
        <Cell title={targetName}>
          <FittedFrame width={bp.width} height={bp.height}>
            {target ? <FrameImage src={target} alt={`${name} ${targetName.toLowerCase()}`} /> : <FrameEmpty>No frame</FrameEmpty>}
            {trig && (
              <span
                className="pointer-events-none absolute rounded-[3px] outline outline-2 outline-offset-2 outline-accent"
                style={{ left: `${(trig[0] / bp.width) * 100}%`, top: `${(trig[1] / bp.height) * 100}%`, width: `${(trig[2] / bp.width) * 100}%`, height: `${(trig[3] / bp.height) * 100}%` }}
                aria-hidden="true"
              />
            )}
          </FittedFrame>
        </Cell>
        <Cell title={`Capture · ${sc.label}`}>
          <FittedFrame width={bp.width} height={bp.height}>
            {capture ? <FrameImage src={capture} alt={`${name} render after: ${sc.steps}`} /> : <FrameEmpty>Not captured in this attempt</FrameEmpty>}
          </FittedFrame>
        </Cell>
        <Cell title={mode === 'slider' ? 'Compare' : 'Difference'} className="col-span-2 hidden sm:col-span-1 sm:flex">
          {target && capture ? (
            mode === 'slider' ? (
              <CompareSlider design={target} render={capture} width={bp.width} height={bp.height} label={`${name}, ${sc.label}: frame versus render`} />
            ) : (
              <DiffOverlay design={target} render={capture} width={bp.width} height={bp.height} label={`${name}, ${sc.label}: difference; black means identical`} />
            )
          ) : (
            <FittedFrame width={bp.width} height={bp.height}>
              <FrameEmpty>Nothing to compare</FrameEmpty>
            </FittedFrame>
          )}
        </Cell>
      </div>

      <div role="group" aria-label={`${name} scenarios`} className="relative -mx-1 mt-3 flex gap-1.5 overflow-x-auto px-1 pb-1 sm:mx-0 sm:grid sm:grid-cols-5 sm:gap-2 sm:overflow-visible sm:px-0">
        {SCENARIOS.map((s) => {
          const rel = attempt.captures[bp.name]?.[s.slot];
          const on = s.slot === slot;
          const st = status(s.check);
          const sv = score(s.check);
          return (
            <button
              key={s.slot}
              type="button"
              aria-pressed={on}
              onClick={() => onSlot(s.slot)}
              title={s.steps}
              className={`group flex w-[5.5rem] shrink-0 flex-col gap-1 rounded-md border p-1 text-left sm:w-auto sm:min-w-0 transition-colors sm:p-1.5 ${on ? 'border-accent bg-accent/5' : 'border-line hover:bg-surface-2'}`}
            >
              <span className="relative block w-full overflow-hidden rounded-sm bg-surface-2" style={{ aspectRatio: `${bp.width} / ${Math.min(bp.height, bp.width * 0.9)}` }}>
                {rel && <img src={runAsset(ix.id, rel)} alt="" loading="lazy" decoding="async" className="absolute inset-0 h-full w-full object-cover object-top" />}
              </span>
              <span className="flex min-w-0 items-center gap-1">
                <StatusIcon status={st} className="shrink-0" />
                <span className="truncate text-[11px] font-medium">{s.label}</span>
              </span>
              <span className="text-[10px] text-ink-faint num">{sv != null ? sv.toFixed(1) : '—'}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function Cell({ title, children, className = 'flex' }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <figure className={`min-w-0 flex-col gap-1.5 ${className}`}>
      <figcaption className="text-[11px] font-medium uppercase tracking-[0.06em] text-ink-muted">{title}</figcaption>
      {children}
    </figure>
  );
}
