import { describe, expect, it } from 'vitest';
import {
  RULER_MARKS,
  SWEEP_CELLS,
  SWEEP_MAX,
  SWEEP_MIN,
  SWEEP_MS,
  cellIndex,
  crossedCells,
  initialSweep,
  measureLayout,
  nextPhase,
  sliderKey,
  sweepCaption,
  sweepWidth,
  valueText,
  type Box,
} from './sweep';
import { cellState } from './viz';

const box = (id: string, left: number, right: number, top = 0, bottom = 10, group: string | null = null): Box => ({ id, left, right, top, bottom, group });

describe('sweep geometry', () => {
  it('cells run from 360 to 1600 in even steps and include both ends', () => {
    expect(SWEEP_CELLS[0]).toBe(SWEEP_MIN);
    expect(SWEEP_CELLS[SWEEP_CELLS.length - 1]).toBe(SWEEP_MAX);
    expect(SWEEP_CELLS.length).toBe(21);
    const steps = new Set(SWEEP_CELLS.slice(1).map((w, i) => w - SWEEP_CELLS[i]));
    expect(steps.size).toBe(1);
  });
  it('exactly one cell falls inside the demo bug window (1080–1133 px)', () => {
    expect(SWEEP_CELLS.filter((w) => w >= 1080 && w < 1134)).toEqual([1104]);
  });
  it('ruler marks are the scored breakpoints plus the sweep ends', () => {
    expect(RULER_MARKS).toEqual([360, 768, 1280, 1600]);
  });
  it('one pass goes 360 → 1600 → 360 in SWEEP_MS', () => {
    expect(SWEEP_MS).toBeGreaterThanOrEqual(7000);
    expect(SWEEP_MS).toBeLessThanOrEqual(9000);
    expect(sweepWidth(0)).toBe(360);
    expect(sweepWidth(SWEEP_MS / 2)).toBe(1600);
    expect(sweepWidth(SWEEP_MS)).toBe(360);
    expect(sweepWidth(SWEEP_MS / 4)).toBeGreaterThan(360);
    expect(sweepWidth(SWEEP_MS / 4)).toBeLessThan(1600);
    expect(sweepWidth(-50)).toBe(360);
    expect(sweepWidth(SWEEP_MS * 3)).toBe(360);
  });
  it('is monotonic on the way up', () => {
    let prev = 0;
    for (let t = 0; t <= SWEEP_MS / 2; t += 100) {
      const w = sweepWidth(t);
      expect(w).toBeGreaterThanOrEqual(prev);
      prev = w;
    }
  });
  it('maps a width to its cell (bucket below), clamped', () => {
    expect(cellIndex(360)).toBe(0);
    expect(cellIndex(421)).toBe(0);
    expect(cellIndex(422)).toBe(1);
    expect(cellIndex(1104)).toBe(SWEEP_CELLS.indexOf(1104));
    expect(cellIndex(1600)).toBe(20);
    expect(cellIndex(100)).toBe(0);
    expect(cellIndex(5000)).toBe(20);
  });
  it('reports the cells crossed on the way up only', () => {
    expect(crossedCells(SWEEP_MIN - 1, 360)).toEqual([0]);
    expect(crossedCells(400, 500)).toEqual([1, 2]);
    expect(crossedCells(422, 430)).toEqual([]); // 422 was already crossed
    expect(crossedCells(1600, 1200)).toEqual([]);
    expect(crossedCells(500, 500)).toEqual([]);
  });
});

describe('measureLayout (real overflow / overlap checks on the demo boxes)', () => {
  const frame = { left: 0, right: 1000 };
  it('passes when everything fits and nothing overlaps', () => {
    const m = measureLayout(frame, [box('a', 0, 400, 0, 10, 'row'), box('b', 420, 1000, 0, 10, 'row')]);
    expect(m).toEqual({ overflow: 0, overlaps: [], offenders: [] });
    expect(cellState(m)).toBe('pass');
  });
  it('measures how far the widest box spills past the frame', () => {
    const m = measureLayout(frame, [box('a', 0, 600), box('b', 640, 1030)]);
    expect(m.overflow).toBe(30);
    expect(m.offenders).toEqual(['b']);
    expect(cellState(m)).toBe('overflow');
  });
  it('treats a spill to the left as overflow too', () => {
    expect(measureLayout(frame, [box('a', -12, 300)]).overflow).toBe(12);
  });
  it('ignores hidden elements (display: none gives an empty box at the page origin)', () => {
    const m = measureLayout({ left: 0, right: 360 }, [box('links', -500, -500, -40, -40, 'nav'), box('brand', 20, 120, 0, 10, 'nav'), box('zero-w', 400, 400, 0, 30)]);
    expect(m).toEqual({ overflow: 0, overlaps: [], offenders: [] });
  });
  it('ignores sub-pixel rounding within the tolerance', () => {
    expect(measureLayout(frame, [box('a', 0, 1000.6)]).overflow).toBe(0);
  });
  it('finds overlaps only between boxes of the same group', () => {
    const m = measureLayout(frame, [box('a', 0, 500, 0, 50, 'cards'), box('b', 480, 900, 10, 40, 'cards'), box('c', 0, 900, 0, 50, 'other')]);
    expect(m.overlaps).toEqual([['a', 'b']]);
    expect(cellState(m)).toBe('overlap');
  });
  it('touching edges are not an overlap', () => {
    expect(measureLayout(frame, [box('a', 0, 500, 0, 50, 'g'), box('b', 500, 900, 0, 50, 'g')]).overlaps).toEqual([]);
  });
  it('overflow wins over overlap for the cell state', () => {
    const m = measureLayout(frame, [box('a', 0, 600, 0, 50, 'g'), box('b', 500, 1100, 0, 50, 'g')]);
    expect(cellState(m)).toBe('overflow');
  });
});

describe('slider (keyboard + aria)', () => {
  it('arrow keys step to the next / previous measured cell', () => {
    expect(sliderKey(360, 'ArrowRight')).toBe(422);
    expect(sliderKey(360, 'ArrowUp')).toBe(422);
    expect(sliderKey(768, 'ArrowRight')).toBe(794);
    expect(sliderKey(768, 'ArrowLeft')).toBe(732);
    expect(sliderKey(422, 'ArrowDown')).toBe(360);
  });
  it('clamps at the ends', () => {
    expect(sliderKey(360, 'ArrowLeft')).toBe(360);
    expect(sliderKey(1600, 'ArrowRight')).toBe(1600);
  });
  it('Home / End / PageUp / PageDown', () => {
    expect(sliderKey(900, 'Home')).toBe(360);
    expect(sliderKey(900, 'End')).toBe(1600);
    expect(sliderKey(360, 'PageUp')).toBe(360 + 62 * 4);
    expect(sliderKey(1600, 'PageDown')).toBe(1600 - 62 * 4);
  });
  it('ignores other keys', () => {
    expect(sliderKey(500, 'a')).toBeNull();
    expect(sliderKey(500, 'Tab')).toBeNull();
  });
  it('aria-valuetext names the width and what was measured there', () => {
    expect(valueText(1104, 'overflow')).toBe('1104 px — overflow');
    expect(valueText(768, 'pass')).toBe('768 px — fits');
    expect(valueText(900, 'overlap')).toBe('900 px — overlap');
    expect(valueText(900.4, 'pending')).toBe('900 px — not measured yet');
  });
});

describe('narrative + reduced motion', () => {
  it('autoplays the "before" pass when motion is allowed', () => {
    expect(initialSweep(false)).toEqual({ phase: 'before', variant: 'before', width: 360, autoplay: true });
  });
  it('reduced motion: a static fixed frame at 768 px, no autoplay', () => {
    expect(initialSweep(true)).toEqual({ phase: 'interactive', variant: 'after', width: 768, autoplay: false });
  });
  it('before → after → interactive, and stays interactive', () => {
    expect(nextPhase('before')).toBe('after');
    expect(nextPhase('after')).toBe('interactive');
    expect(nextPhase('interactive')).toBe('interactive');
  });
  it('captions say what the measurement found', () => {
    const cells = SWEEP_CELLS.map((width) => ({ width, state: width === 1104 ? ('overflow' as const) : ('pass' as const) }));
    expect(sweepCaption('before', cells)).toBe('Before: overflow at 1104 px');
    expect(sweepCaption('after', cells.map((c) => ({ ...c, state: 'pass' as const })))).toBe('After the fix: 21 of 21 widths fit');
    expect(sweepCaption('before', cells.map((c) => ({ ...c, state: 'pending' as const })))).toBe('Measuring 21 widths…');
    expect(sweepCaption('before', [{ width: 360, state: 'pass' }, { width: 422, state: 'pending' }])).toBe('Measuring 2 widths…');
  });
});
