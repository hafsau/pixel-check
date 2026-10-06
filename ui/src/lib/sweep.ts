// "The Sweep" hero: geometry, live layout measurement, slider keys and the before → after narrative.
// The component (components/hero/HeroSweep.tsx) only wires these to the DOM and requestAnimationFrame.
import type { CellState, StripCell } from './viz';

export const SWEEP_MIN = 360;
export const SWEEP_MAX = 1600;
/** 21 cells, 62 px apart: 360, 422, … 1104 … 1600. Only 1104 lands inside the demo's "before" bug (1080–1133 px). */
export const SWEEP_STEP = 62;
export const SWEEP_CELLS: number[] = Array.from({ length: (SWEEP_MAX - SWEEP_MIN) / SWEEP_STEP + 1 }, (_, i) => SWEEP_MIN + i * SWEEP_STEP);
export const RULER_MARKS = [360, 768, 1280, 1600];
/** One pass: 360 → 1600 → 360. */
export const SWEEP_MS = 8000;

const ease = (x: number) => (x < 0.5 ? 2 * x * x : 1 - (-2 * x + 2) ** 2 / 2);

/** Frame width at `t` ms into a pass (ease-in-out each way). Outside the pass it rests at 360. */
export function sweepWidth(t: number, ms = SWEEP_MS): number {
  if (t <= 0 || t >= ms) return SWEEP_MIN;
  const half = ms / 2;
  const x = t <= half ? t / half : (ms - t) / half;
  return Math.round(SWEEP_MIN + (SWEEP_MAX - SWEEP_MIN) * ease(x));
}

/** The cell whose bucket [cell, next cell) holds `width`, clamped to the strip. */
export function cellIndex(width: number): number {
  const i = Math.floor((width - SWEEP_MIN) / SWEEP_STEP);
  return Math.max(0, Math.min(SWEEP_CELLS.length - 1, i));
}

/** Cells passed while growing from `prev` to `next` (prev < cell ≤ next). Shrinking measures nothing new. */
export function crossedCells(prev: number, next: number): number[] {
  if (next <= prev) return [];
  return SWEEP_CELLS.flatMap((w, i) => (w > prev && w <= next ? [i] : []));
}

// ------------------------------------------------------------------------------------------------ measurement

export interface Box {
  id: string;
  left: number;
  right: number;
  top: number;
  bottom: number;
  /** Boxes in the same group must not overlap (cards in a row, nav items). */
  group?: string | null;
}
export interface Measure {
  /** px past the frame edge (either side) of the worst box. */
  overflow: number;
  overlaps: [string, string][];
  offenders: string[];
}

/** The same two checks the sandbox runs between breakpoints, on boxes in the frame's own CSS px. */
export function measureLayout(frame: { left: number; right: number }, all: Box[], tol = 1): Measure {
  // hidden elements (display: none, collapsed) report an empty box — they cannot overflow or overlap anything
  const boxes = all.filter((b) => b.right - b.left > 0 && b.bottom - b.top > 0);
  let overflow = 0;
  const offenders: string[] = [];
  for (const b of boxes) {
    const spill = Math.max(b.right - frame.right, frame.left - b.left);
    if (spill > tol) {
      offenders.push(b.id);
      overflow = Math.max(overflow, Math.round(spill));
    }
  }
  const overlaps: [string, string][] = [];
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i];
      const b = boxes[j];
      if (!a.group || a.group !== b.group) continue;
      const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (w > tol && h > tol) overlaps.push([a.id, b.id]);
    }
  return { overflow, overlaps, offenders };
}

// ------------------------------------------------------------------------------------------------ slider

const STATE_WORD: Record<CellState, string> = { pending: 'not measured yet', pass: 'fits', overflow: 'overflow', overlap: 'overlap', fail: 'fails' };

export function valueText(width: number, state: CellState): string {
  return `${Math.round(width)} px — ${STATE_WORD[state]}`;
}

/** Arrow keys step between measured cells; Page keys jump 4 cells; Home / End go to the ends. null = not ours. */
export function sliderKey(value: number, key: string): number | null {
  const next = SWEEP_CELLS.find((w) => w > value) ?? SWEEP_MAX;
  const prev = [...SWEEP_CELLS].reverse().find((w) => w < value) ?? SWEEP_MIN;
  const clamp = (w: number) => Math.max(SWEEP_MIN, Math.min(SWEEP_MAX, w));
  switch (key) {
    case 'ArrowRight':
    case 'ArrowUp':
      return next;
    case 'ArrowLeft':
    case 'ArrowDown':
      return prev;
    case 'PageUp':
      return clamp(SWEEP_CELLS[cellIndex(value)] + SWEEP_STEP * 4);
    case 'PageDown':
      return clamp(SWEEP_CELLS[cellIndex(value)] - SWEEP_STEP * 4);
    case 'Home':
      return SWEEP_MIN;
    case 'End':
      return SWEEP_MAX;
    default:
      return null;
  }
}

// ------------------------------------------------------------------------------------------------ narrative

/** before = the demo with a deliberate overflow; after = the fixed demo; interactive = handle is the user's. */
export type Phase = 'before' | 'after' | 'interactive';
export type Variant = 'before' | 'after';

export function initialSweep(reducedMotion: boolean): { phase: Phase; variant: Variant; width: number; autoplay: boolean } {
  return reducedMotion ? { phase: 'interactive', variant: 'after', width: 768, autoplay: false } : { phase: 'before', variant: 'before', width: SWEEP_MIN, autoplay: true };
}

export function nextPhase(p: Phase): Phase {
  return p === 'before' ? 'after' : 'interactive';
}

export function sweepCaption(phase: Phase, cells: StripCell[]): string {
  if (cells.some((c) => c.state === 'pending')) return `Measuring ${cells.length} widths…`;
  const bad = cells.filter((c) => c.state !== 'pass');
  if (bad.length) return `${phase === 'after' ? 'After the fix' : 'Before'}: ${bad[0].state} at ${bad.map((c) => `${c.width}`).join(', ')} px`;
  return `${phase === 'before' ? 'Before' : 'After the fix'}: ${cells.length} of ${cells.length} widths fit`;
}
