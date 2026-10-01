import { useEffect } from 'react';
import type { PlaybackState } from '../lib/playback';
import { SPEEDS } from '../lib/playback';
import { strategyLabel } from '../lib/playback';
import { IconEnd, IconPause, IconPlay, IconStart, IconStepBack, IconStepFwd } from './Icons';

/**
 * Play/pause, step, speed and scrubber for the replay.
 * Keyboard: Space = play/pause, ←/→ = step (when focus is not in a text field or slider).
 */
export function PlaybackControls({ pb }: { pb: PlaybackState }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.closest('input, textarea, select, [role="slider"], [contenteditable="true"]') || e.metaKey || e.ctrlKey || e.altKey)) return;
      if (e.key === ' ' && !(t instanceof HTMLButtonElement)) {
        e.preventDefault();
        pb.toggle();
      } else if (e.key === 'ArrowRight') pb.step(1);
      else if (e.key === 'ArrowLeft') pb.step(-1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pb]);

  const c = pb.shown;
  return (
    <div className="card flex flex-col gap-3 px-3 py-2.5 sm:flex-row sm:items-center sm:gap-4" role="group" aria-label="Replay controls">
      <div className="flex items-center gap-1">
        <button type="button" className="btn-icon btn-ghost" onClick={() => { pb.pause(); pb.seek(0); }} aria-label="Go to first candidate">
          <IconStart />
        </button>
        <button type="button" className="btn-icon btn-ghost" onClick={() => pb.step(-1)} aria-label="Previous candidate">
          <IconStepBack />
        </button>
        <button type="button" className="btn-primary w-11 px-0" onClick={pb.toggle} aria-label={pb.playing ? 'Pause' : 'Play'}>
          {pb.playing ? <IconPause /> : <IconPlay />}
        </button>
        <button type="button" className="btn-icon btn-ghost" onClick={() => pb.step(1)} aria-label="Next candidate">
          <IconStepFwd />
        </button>
        <button type="button" className="btn-icon btn-ghost" onClick={() => { pb.pause(); pb.seek(pb.total - 1); }} aria-label="Go to last candidate">
          <IconEnd />
        </button>
        <div className="seg ml-2" role="radiogroup" aria-label="Playback speed">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              role="radio"
              aria-checked={pb.speed === s}
              className="seg-item num"
              onClick={() => pb.setSpeed(s)}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <label htmlFor="scrubber" className="sr-only">
          Candidate
        </label>
        <input
          id="scrubber"
          type="range"
          min={0}
          max={Math.max(0, pb.total - 1)}
          step={1}
          value={pb.index}
          onChange={(e) => { pb.pause(); pb.seek(Number(e.target.value)); }}
          aria-valuetext={`Candidate ${pb.index + 1} of ${pb.total}, round ${c.round}, ${strategyLabel(c.strategy)}`}
          className="min-w-0 flex-1 accent-[rgb(var(--c-accent))]"
        />
        <p className="shrink-0 text-xs text-ink-muted num" aria-live="polite">
          <span className="font-semibold text-ink">Round {c.round}</span> · {pb.index + 1}/{pb.total}
        </p>
      </div>
    </div>
  );
}
