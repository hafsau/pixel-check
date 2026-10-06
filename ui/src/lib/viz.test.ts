import { describe, expect, it } from 'vitest';
import { BULLET_BANDS, BULLET_TARGET, bestReplayHref, bulletModel, cellState, fluidityCells, ringModel, stripSummary } from './viz';
import type { Fluidity, IndexEntry } from './types';

describe('bullet chart', () => {
  it('has three qualitative bands 0–49 / 50–89 / 90–100 and a target at 90', () => {
    expect(BULLET_BANDS.map((b) => [b.from, b.to])).toEqual([
      [0, 50],
      [50, 90],
      [90, 100],
    ]);
    expect(BULLET_TARGET).toBe(90);
  });
  it('maps a score to a bar length and pass / below-target', () => {
    expect(bulletModel(94.03)).toEqual({ pct: 94.03, pass: true });
    expect(bulletModel(69.8)).toEqual({ pct: 69.8, pass: false });
    expect(bulletModel(90)).toEqual({ pct: 90, pass: true });
  });
  it('clamps and handles missing scores', () => {
    expect(bulletModel(120)).toEqual({ pct: 100, pass: true });
    expect(bulletModel(-3)).toEqual({ pct: 0, pass: false });
    expect(bulletModel(null)).toEqual({ pct: null, pass: null });
    expect(bulletModel(undefined)).toEqual({ pct: null, pass: null });
    expect(bulletModel(Number.NaN)).toEqual({ pct: null, pass: null });
  });
});

describe('score ring', () => {
  it('draws the arc proportional to the score', () => {
    const r = ringModel(75, 20);
    expect(r.circumference).toBeCloseTo(2 * Math.PI * 20, 6);
    expect(r.dash).toBeCloseTo(r.circumference * 0.75, 6);
    expect(r.gap).toBeCloseTo(r.circumference * 0.25, 6);
  });
  it('empty for a missing score, full at 100, clamped', () => {
    expect(ringModel(null, 10).dash).toBe(0);
    expect(ringModel(100, 10).gap).toBeCloseTo(0, 6);
    expect(ringModel(140, 10).dash).toBeCloseTo(2 * Math.PI * 10, 6);
  });
});

const fl = (widths: Fluidity['widths']): Fluidity => ({ pass: true, fails: [], widths });
const w = (o: Partial<Fluidity['widths'][string]>) => ({ overflow: 0, overlaps: 0, centre_drift: 0, max_gap: 0, bg_covers: true, ok: true, ...o });

describe('WidthStrip cells from fluidity.widths', () => {
  it('uses the numeric widths only, sorted, and skips the breakpoint entries', () => {
    const cells = fluidityCells(fl({ '1600': w({}), '360': w({}), mobile: w({}), '500': w({}), '1024': w({}), '375': w({}) } as Fluidity['widths']));
    expect(cells.map((c) => c.width)).toEqual([360, 375, 500, 1024, 1600]);
    expect(cells.every((c) => c.state === 'pass')).toBe(true);
  });
  it('names why a width fails', () => {
    const cells = fluidityCells(
      fl({
        '360': w({ ok: false, overflow: 14 }),
        '500': w({ ok: false, overlaps: 2 }),
        '1024': w({ ok: false, centre_drift: 0.2 }),
        '1600': w({}),
      }),
    );
    expect(cells.map((c) => c.state)).toEqual(['overflow', 'overlap', 'fail', 'pass']);
    expect(cells[0].detail).toBe('overflow 14 px');
    expect(cells[1].detail).toBe('2 overlaps');
  });
  it('is empty without a record', () => {
    expect(fluidityCells(null)).toEqual([]);
    expect(fluidityCells(undefined)).toEqual([]);
  });
  it('summarises for screen readers', () => {
    expect(stripSummary([])).toBe('No width checks recorded');
    expect(stripSummary(fluidityCells(fl({ '360': w({}), '1600': w({}) })))).toBe('2 of 2 widths fit (360–1600 px)');
    expect(stripSummary(fluidityCells(fl({ '360': w({ ok: false, overflow: 14 }), '500': w({}), '1024': w({ ok: false, overlaps: 1 }) })))).toBe(
      '1 of 3 widths fit (360–1024 px) · fails at 360 px (overflow 14 px), 1024 px (1 overlap)',
    );
  });
  it('cell state mapping covers pending', () => {
    expect(cellState(null)).toBe('pending');
  });
});

describe('"See a run" link', () => {
  const s = (id: string, match: number, created = 1): IndexEntry => ({ type: 'static', id, title: id, match, per_bp: {}, created });
  it('goes to the best static replay', () => {
    expect(bestReplayHref([s('a', 70), s('b', 92.15), s('c', 87)])).toBe('/run/b');
  });
  it('ignores interactions and groups, falls back to the run list', () => {
    expect(bestReplayHref([{ type: 'interaction', id: 'x', title: 'x', page: '', state: '', kind: null, created: 1, bps: [], variants: [] }])).toBe('/#runs');
    expect(bestReplayHref([])).toBe('/#runs');
  });
});
