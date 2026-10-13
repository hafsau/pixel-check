import { cap } from '../lib/format';
import { inferFrames, type Inferred } from '../lib/frames';
import type { LiveBp } from '../lib/live';
import type { FrameState } from './FramePicker';
import { IconAlert } from './Icons';

/** How PixelCheck will read the picked frames, before anything runs: which file is which size (by width), what is
 *  scored (first screen of a full page), which Tailwind screen each width gets. null until all three are picked. */
export function inferPicked(frames: Partial<Record<LiveBp, FrameState>>): Inferred | null {
  const bps: LiveBp[] = ['mobile', 'tablet', 'desktop'];
  if (!bps.every((bp) => frames[bp]?.status === 'ok')) return null;
  const facts = Object.fromEntries(bps.map((bp) => [bp, (frames[bp] as Extract<FrameState, { status: 'ok' }>).facts])) as Record<LiveBp, never>;
  return inferFrames(facts);
}

export function FramesSummary({ inferred }: { inferred: Inferred | null }) {
  if (!inferred) return null;
  if (!inferred.ok)
    return (
      <p className="flex items-start gap-1.5 rounded-md border border-bad/30 bg-bad/5 p-3 text-sm text-bad" role="alert">
        <IconAlert /> {inferred.error}
      </p>
    );
  return (
    <section aria-label="How PixelCheck reads your frames" className="rounded-md border border-line bg-surface-2 p-3 text-sm">
      <h4 className="font-semibold">We read your frames as</h4>
      <ul className="mt-2 grid gap-1">
        {inferred.rows.map((r) => (
          <li key={r.bp} className="flex flex-wrap items-baseline gap-x-2">
            <span className="w-16 font-medium">{cap(r.bp)}</span>
            <span className="num">
              {r.width} × {r.height} px
            </span>
            {r.cropped && <span className="text-ink-muted">· scored on the first screen ({r.width} × {r.scoredHeight})</span>}
            {r.source !== r.bp && <span className="text-warn">· picked as {r.source} — {r.width} px wide is {r.bp}</span>}
            <span className="font-mono text-[11px] text-ink-faint">{r.prefix ? `${r.prefix} classes` : 'base classes'}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-ink-muted">
        Fonts are detected from the frames when the run starts (16 open families; others get the closest one, and the result says
        which). Photos become placeholder blocks.
      </p>
    </section>
  );
}
