// Pure models behind the score visuals: bullet charts, the score ring, width strips, and the "See a run" link.
import type { Fluidity, IndexEntry } from './types';
import { entryHref } from './bundle';

// ------------------------------------------------------------------------------------------------ bullet chart

/** Qualitative bands drawn behind every bullet bar (0–49 off · 50–89 close · 90–100 visually the same). */
export const BULLET_BANDS = [
  { from: 0, to: 50, label: '0–49' },
  { from: 50, to: 90, label: '50–89' },
  { from: 90, to: 100, label: '90–100' },
] as const;
/** The target tick: 90 = "visually the same" on the scorer's calibration. */
export const BULLET_TARGET = 90;

export function bulletModel(value: number | null | undefined, target = BULLET_TARGET): { pct: number | null; pass: boolean | null } {
  if (value == null || Number.isNaN(value)) return { pct: null, pass: null };
  const pct = Math.max(0, Math.min(100, value));
  return { pct, pass: pct >= target };
}

// ------------------------------------------------------------------------------------------------ score ring

export function ringModel(score: number | null | undefined, radius: number): { circumference: number; dash: number; gap: number } {
  const circumference = 2 * Math.PI * radius;
  const pct = score == null || Number.isNaN(score) ? 0 : Math.max(0, Math.min(100, score)) / 100;
  return { circumference, dash: circumference * pct, gap: circumference * (1 - pct) };
}

// ------------------------------------------------------------------------------------------------ width strip

/** What one width check found. `pending` = not measured yet; `fail` = failed for another reason (drift, background). */
export type CellState = 'pending' | 'pass' | 'overflow' | 'overlap' | 'fail';
export interface StripCell {
  width: number;
  state: CellState;
  detail?: string;
  /** A design size's score, shown inside the cell by the interactive strip. */
  score?: number | null;
}

/** Overflow wins over overlap; no measurement = pending. */
export function cellState(m: { overflow: number; overlaps: unknown[] } | null | undefined): CellState {
  if (!m) return 'pending';
  if (m.overflow > 0) return 'overflow';
  if (m.overlaps.length > 0) return 'overlap';
  return 'pass';
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

/** The run bundles' sandbox width sweep (fluidity.widths: 360 / 375 / 500 / 1024 / 1600) → strip cells. */
export function fluidityCells(fl: Fluidity | null | undefined): StripCell[] {
  if (!fl?.widths) return [];
  return Object.entries(fl.widths)
    .filter(([k]) => /^\d+$/.test(k))
    .map(([k, x]) => {
      const width = Number(k);
      if (x.ok) return { width, state: 'pass' as const };
      if (x.overflow > 0) return { width, state: 'overflow' as const, detail: `overflow ${Math.round(x.overflow)} px` };
      if (x.overlaps > 0) return { width, state: 'overlap' as const, detail: plural(x.overlaps, 'overlap') };
      const why = x.bg_covers === false ? 'background gap' : x.centre_drift ? `centre drift ${Math.round(x.centre_drift * 100)} %` : 'check failed';
      return { width, state: 'fail' as const, detail: why };
    })
    .sort((a, b) => a.width - b.width);
}

/** One sentence for screen readers (and the visible caption). */
export function stripSummary(cells: StripCell[]): string {
  if (!cells.length) return 'No width checks recorded';
  const done = cells.filter((c) => c.state !== 'pending');
  const fits = done.filter((c) => c.state === 'pass').length;
  const range = `${cells[0].width}–${cells[cells.length - 1].width} px`;
  const fails = done.filter((c) => c.state !== 'pass');
  const head = `${fits} of ${cells.length} widths fit (${range})`;
  if (!fails.length) return head;
  return `${head} · fails at ${fails.map((c) => `${c.width} px (${c.detail ?? c.state})`).join(', ')}`;
}

// ------------------------------------------------------------------------------------------------ "See a run"

/** The highest-scoring static replay, or the run list when none is published. */
export function bestReplayHref(entries: IndexEntry[]): string {
  const best = entries.filter((e) => e.type === 'static').sort((a, b) => (b as { match: number }).match - (a as { match: number }).match)[0];
  return best ? entryHref(best) : '/#runs';
}
