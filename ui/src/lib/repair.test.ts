import { describe, expect, it } from 'vitest';
import {
  diffHunks,
  diffLines,
  diffStats,
  fmtDelta,
  linesKeptLabel,
  parseRepair,
  repairFileUrls,
  repairOutcome,
  repairSizes,
  repairSummary,
  roundBars,
  splitLines,
  widthFailsLabel,
  type DiffOp,
} from './repair';

// ------------------------------------------------------------------------------------------------ fixtures

const raw = {
  code: 'repair/App.jsx',
  original: 'original/App.jsx',
  start: { worst: 21.3, per_bp: { mobile: 21.3, tablet: 30.3, desktop: 74.5 }, fluid_fails: 4, fails: [360, 375, 500, 'mobile'] },
  best: { worst: 30.3, per_bp: { mobile: 33.1, tablet: 30.3, desktop: 74.9 }, fluid_fails: 0, fails: [] },
  history: [
    { round: 0, worst: 21.3, fluid_fails: 4 },
    { round: 1, worst: 25.8, fluid_fails: 0, applied: 7, candidates: 3 },
    { round: 2, worst: 30.3, fluid_fails: 0, applied: 4, candidates: 3 },
    { round: 3, worst: 28.9, fluid_fails: 1, applied: 2, candidates: 2 },
  ],
  lines_kept: 0.85,
  usd: 0.03,
};

const unchangedRaw = {
  ...raw,
  best: raw.start,
  history: [
    { round: 0, worst: 21.3, fluid_fails: 4 },
    { round: 1, worst: 20.1, fluid_fails: 4, applied: 3, candidates: 3 },
  ],
  lines_kept: 1,
};

// ------------------------------------------------------------------------------------------------ parsing

describe('parseRepair', () => {
  it('normalises a full repair block', () => {
    const r = parseRepair(raw)!;
    expect(r.code).toBe('repair/App.jsx');
    expect(r.original).toBe('original/App.jsx');
    expect(r.start).toEqual({ worst: 21.3, perBp: { mobile: 21.3, tablet: 30.3, desktop: 74.5 }, fluidFails: 4, fails: ['360', '375', '500', 'mobile'] });
    expect(r.best.worst).toBe(30.3);
    expect(r.best.fluidFails).toBe(0);
    expect(r.history.map((h) => h.round)).toEqual([0, 1, 2, 3]);
    expect(r.history[1]).toEqual({ round: 1, worst: 25.8, fluidFails: 0, applied: 7, candidates: 3 });
    expect(r.history[0].applied).toBeNull();
    expect(r.linesKept).toBe(0.85);
    expect(r.usd).toBe(0.03);
  });

  it('is null when the check had no repair (null, missing or not an object)', () => {
    expect(parseRepair(null)).toBeNull();
    expect(parseRepair(undefined)).toBeNull();
    expect(parseRepair('repair')).toBeNull();
    expect(parseRepair([raw])).toBeNull();
  });

  it('accepts only repair/App.jsx and original/App.jsx as file paths', () => {
    const bad = ['../App.jsx', '/etc/passwd', 'https://evil.example/App.jsx', 'repair/../../x', 'repair/app.jsx', 'repair/App.jsx?x', 'other/App.jsx', 'repair/App.jsx/', ' repair/App.jsx', 42];
    for (const p of bad) {
      const r = parseRepair({ ...raw, code: p, original: p })!;
      expect(r.code, String(p)).toBeNull();
      expect(r.original, String(p)).toBeNull();
    }
  });

  it('turns wrong types into null / empty and sorts + de-duplicates rounds', () => {
    const r = parseRepair({
      start: { worst: 'x', per_bp: { mobile: NaN, tablet: 5, phone: 9 }, fails: 'nope' },
      best: 7,
      history: [{ round: 2, worst: 30 }, { round: 'one', worst: 1 }, { round: 0, worst: 20 }, { round: 2, worst: 99 }, null, { round: -1, worst: 3 }],
      lines_kept: 'most',
      usd: Infinity,
    })!;
    expect(r.start).toEqual({ worst: null, perBp: { mobile: null, tablet: 5, desktop: null }, fluidFails: 0, fails: [] });
    expect(r.best).toEqual({ worst: null, perBp: { mobile: null, tablet: null, desktop: null }, fluidFails: 0, fails: [] });
    expect(r.history.map((h) => [h.round, h.worst])).toEqual([
      [0, 20],
      [2, 30],
    ]);
    expect(r.linesKept).toBeNull();
    expect(r.usd).toBeNull();
    expect(r.code).toBeNull();
  });

  it('counts width failures from the list when fluid_fails is missing (empty entries ignored)', () => {
    const r = parseRepair({ ...raw, start: { worst: 10, fails: [360, '', 500, null] } })!;
    expect(r.start.fluidFails).toBe(2);
    expect(r.start.fails).toEqual(['360', '500']);
  });

  it('clamps lines kept to 0–1', () => {
    expect(parseRepair({ ...raw, lines_kept: 1.4 })!.linesKept).toBe(1);
    expect(parseRepair({ ...raw, lines_kept: -0.2 })!.linesKept).toBe(0);
  });
});

// ------------------------------------------------------------------------------------------------ outcome

describe('repairOutcome', () => {
  it('improved: before → after, delta, width failures, the kept round', () => {
    const o = repairOutcome(parseRepair(raw)!);
    expect(o).toMatchObject({ before: 21.3, after: 30.3, improved: true, unchanged: false, fluidBefore: 4, fluidAfter: 0, keptRound: 2 });
    expect(o.delta).toBeCloseTo(9.0, 5);
  });

  it('unchanged when no round beat the start (best == start)', () => {
    const o = repairOutcome(parseRepair(unchangedRaw)!);
    expect(o).toMatchObject({ before: 21.3, after: 21.3, improved: false, unchanged: true, keptRound: 0 });
    expect(o.delta).toBe(0);
  });

  it('unchanged when after is lower than before', () => {
    const o = repairOutcome(parseRepair({ ...raw, best: { ...raw.start, worst: 20 } })!);
    expect(o.unchanged).toBe(true);
    expect(o.improved).toBe(false);
  });

  it('a level score with fewer width failures still counts as improved', () => {
    const o = repairOutcome(parseRepair({ ...raw, best: { ...raw.start, worst: 21.3, fluid_fails: 1, fails: [360] } })!);
    expect(o.improved).toBe(true);
    expect(o.unchanged).toBe(false);
  });

  it('unknown scores are not an improvement', () => {
    const o = repairOutcome(parseRepair({ start: {}, best: {} })!);
    expect(o).toMatchObject({ before: null, after: null, delta: null, improved: false, unchanged: true, keptRound: null });
  });

  it('kept round falls back to the highest-scoring round when none matches best exactly', () => {
    const o = repairOutcome(parseRepair({ ...raw, best: { worst: 31, fluid_fails: 0 } })!);
    expect(o.keptRound).toBe(2);
  });
});

describe('labels', () => {
  it('fmtDelta: signed, one decimal, true minus sign', () => {
    expect(fmtDelta(9)).toBe('+9.0');
    expect(fmtDelta(-1.24)).toBe('−1.2');
    expect(fmtDelta(0)).toBe('±0.0');
    expect(fmtDelta(0.04)).toBe('±0.0');
    expect(fmtDelta(null)).toBe('—');
  });
  it('linesKeptLabel', () => {
    expect(linesKeptLabel(0.85)).toBe('lines kept 85 %');
    expect(linesKeptLabel(0.9)).toBe('lines kept 90 %');
    expect(linesKeptLabel(1)).toBe('lines kept 100 %');
    expect(linesKeptLabel(null)).toBe('');
  });
  it('widthFailsLabel', () => {
    expect(widthFailsLabel(4, 0)).toBe('width failures 4 → 0');
    expect(widthFailsLabel(1, 1)).toBe('width failures 1 → 1');
    expect(widthFailsLabel(null, 0)).toBe('');
  });
});

describe('repairSizes', () => {
  it('one row per size with before, after and delta', () => {
    const rows = repairSizes(parseRepair(raw)!);
    expect(rows.map((r) => r.bp)).toEqual(['mobile', 'tablet', 'desktop']);
    expect(rows[0]).toMatchObject({ bp: 'mobile', before: 21.3, after: 33.1 });
    expect(rows[0].delta).toBeCloseTo(11.8, 5);
    expect(rows[1].delta).toBeCloseTo(0, 5);
  });
  it('delta is null when either side is unknown', () => {
    const rows = repairSizes(parseRepair({ start: { per_bp: { mobile: 10 } }, best: {} })!);
    expect(rows[0]).toMatchObject({ before: 10, after: null, delta: null });
  });
});

describe('roundBars', () => {
  it('one bar per round on a 0–100 scale; the kept round is marked', () => {
    const r = parseRepair(raw)!;
    const bars = roundBars(r, repairOutcome(r).keptRound);
    expect(bars.map((b) => [b.round, b.pct, b.kept])).toEqual([
      [0, 21.3, false],
      [1, 25.8, false],
      [2, 30.3, true],
      [3, 28.9, false],
    ]);
  });
  it('clamps to 0–100 and keeps unknown rounds as empty bars', () => {
    const r = parseRepair({ history: [{ round: 0, worst: 120 }, { round: 1 }, { round: 2, worst: -5 }] })!;
    expect(roundBars(r, null).map((b) => [b.pct, b.worst])).toEqual([
      [100, 120],
      [0, null],
      [0, -5],
    ]);
  });
});

describe('repairSummary', () => {
  it('improved: one copy-able line', () => {
    const r = parseRepair(raw)!;
    expect(repairSummary(r, repairOutcome(r))).toBe('Repair: worst size 21.3 → 30.3 (+9.0) · width failures 4 → 0 · lines kept 85 %');
  });
  it('unchanged: says so plainly', () => {
    const r = parseRepair(unchangedRaw)!;
    expect(repairSummary(r, repairOutcome(r))).toBe('Repair: no round improved it (worst size 21.3) — code unchanged');
  });
});

// ------------------------------------------------------------------------------------------------ diff

const kinds = (ops: DiffOp[]) => ops.map((o) => `${o.kind === 'same' ? ' ' : o.kind === 'add' ? '+' : '-'}${o.text}`);

describe('splitLines', () => {
  it('splits on LF and CRLF and drops one trailing newline', () => {
    expect(splitLines('a\r\nb\nc\n')).toEqual(['a', 'b', 'c']);
    expect(splitLines('a\n\n')).toEqual(['a', '']);
    expect(splitLines('')).toEqual([]);
  });
});

describe('diffLines', () => {
  it('identical input → only same lines, numbered on both sides', () => {
    const ops = diffLines(['a', 'b'], ['a', 'b']);
    expect(ops).toEqual([
      { kind: 'same', text: 'a', a: 1, b: 1 },
      { kind: 'same', text: 'b', a: 2, b: 2 },
    ]);
  });

  it('a changed line is a removal then an addition', () => {
    const ops = diffLines(['a', '<div className="p-2">', 'c'], ['a', '<div className="p-4 md:p-6">', 'c']);
    expect(kinds(ops)).toEqual([' a', '-<div className="p-2">', '+<div className="p-4 md:p-6">', ' c']);
    expect(ops[1]).toEqual({ kind: 'del', text: '<div className="p-2">', a: 2 });
    expect(ops[2]).toEqual({ kind: 'add', text: '<div className="p-4 md:p-6">', b: 2 });
  });

  it('pure insertions and deletions', () => {
    expect(kinds(diffLines(['a', 'c'], ['a', 'b', 'c']))).toEqual([' a', '+b', ' c']);
    expect(kinds(diffLines(['a', 'b', 'c'], ['a', 'c']))).toEqual([' a', '-b', ' c']);
    expect(kinds(diffLines([], ['x', 'y']))).toEqual(['+x', '+y']);
    expect(kinds(diffLines(['x', 'y'], []))).toEqual(['-x', '-y']);
    expect(diffLines([], [])).toEqual([]);
  });

  it('is a minimal edit: the classic ABCABBA → CBABAC has 5 changes', () => {
    const ops = diffLines('ABCABBA'.split(''), 'CBABAC'.split(''));
    expect(ops.filter((o) => o.kind !== 'same').length).toBe(5);
    expect(ops.filter((o) => o.kind !== 'add').map((o) => o.text).join('')).toBe('ABCABBA');
    expect(ops.filter((o) => o.kind !== 'del').map((o) => o.text).join('')).toBe('CBABAC');
  });

  it('within a change block removals come before additions', () => {
    const ops = diffLines(['a', 'x1', 'x2', 'b'], ['a', 'y1', 'y2', 'b']);
    expect(kinds(ops)).toEqual([' a', '-x1', '-x2', '+y1', '+y2', ' b']);
  });

  it('line numbers stay correct through many changes', () => {
    const a = Array.from({ length: 50 }, (_, i) => `line ${i}`);
    const b = a.map((l, i) => (i % 10 === 3 ? `${l} changed` : l));
    const ops = diffLines(a, b);
    for (const o of ops) {
      if (o.a != null) expect(a[o.a - 1]).toBe(o.text);
      if (o.b != null) expect(b[o.b - 1]).toBe(o.text);
    }
    expect(diffStats(ops)).toEqual({ added: 5, removed: 5 });
  });

  it('falls back to replace-all when the edit distance exceeds the limit (still correct)', () => {
    const a = Array.from({ length: 30 }, (_, i) => `a${i}`);
    const b = Array.from({ length: 30 }, (_, i) => `b${i}`);
    const ops = diffLines(['top', ...a, 'end'], ['top', ...b, 'end'], 4);
    expect(ops[0]).toEqual({ kind: 'same', text: 'top', a: 1, b: 1 });
    expect(ops[ops.length - 1]).toEqual({ kind: 'same', text: 'end', a: 32, b: 32 });
    expect(diffStats(ops)).toEqual({ added: 30, removed: 30 });
  });

  it('handles a large, mostly equal file quickly', () => {
    const a = Array.from({ length: 6000 }, (_, i) => `  <div className="row-${i}">`);
    const b = a.map((l, i) => (i % 500 === 7 ? l.replace('row', 'md:row') : l));
    const t = Date.now();
    const ops = diffLines(a, b);
    expect(Date.now() - t).toBeLessThan(1000);
    expect(diffStats(ops)).toEqual({ added: 12, removed: 12 });
  });
});

describe('diffHunks', () => {
  const a = Array.from({ length: 20 }, (_, i) => `L${i + 1}`);

  it('no changes → no hunks', () => {
    expect(diffHunks(diffLines(a, a))).toEqual([]);
  });

  it('only changed hunks, 2 lines of context, correct ranges', () => {
    const b = a.map((l, i) => (i === 9 ? 'L10*' : l));
    const hs = diffHunks(diffLines(a, b));
    expect(hs).toHaveLength(1);
    expect(kinds(hs[0].lines)).toEqual([' L8', ' L9', '-L10', '+L10*', ' L11', ' L12']);
    expect(hs[0]).toMatchObject({ aStart: 8, aLines: 5, bStart: 8, bLines: 5 });
  });

  it('separate hunks for far-apart changes; merged when contexts touch', () => {
    const far = a.map((l, i) => (i === 2 || i === 15 ? `${l}*` : l));
    expect(diffHunks(diffLines(a, far))).toHaveLength(2);
    const near = a.map((l, i) => (i === 5 || i === 9 ? `${l}*` : l)); // 3 lines between: contexts of 2 overlap
    const hs = diffHunks(diffLines(a, near));
    expect(hs).toHaveLength(1);
    expect(hs[0].aStart).toBe(4);
    expect(hs[0].aLines).toBe(9); // L4–L12
  });

  it('context is cut at the file edges', () => {
    const b = a.map((l, i) => (i === 0 || i === 19 ? `${l}*` : l));
    const hs = diffHunks(diffLines(a, b));
    expect(hs).toHaveLength(2);
    expect(kinds(hs[0].lines)).toEqual(['-L1', '+L1*', ' L2', ' L3']);
    expect(hs[0]).toMatchObject({ aStart: 1, bStart: 1 });
    expect(kinds(hs[1].lines)).toEqual([' L18', ' L19', '-L20', '+L20*']);
  });

  it('custom context size', () => {
    const b = a.map((l, i) => (i === 9 ? 'L10*' : l));
    expect(diffHunks(diffLines(a, b), 0)[0].lines.map((o) => o.kind)).toEqual(['del', 'add']);
  });

  it('an insertion into an empty file starts at line 0 on the old side', () => {
    const hs = diffHunks(diffLines([], ['x']));
    expect(hs[0]).toMatchObject({ aStart: 0, aLines: 0, bStart: 1, bLines: 1 });
  });
});

describe('repairFileUrls', () => {
  it('both App.jsx files under the run folder', () => {
    expect(repairFileUrls('https://api.x', 'id 1', parseRepair(raw)!)).toEqual({
      repaired: 'https://api.x/api/runs/id%201/files/repair/App.jsx',
      original: 'https://api.x/api/runs/id%201/files/original/App.jsx',
    });
  });
  it('null when a path was rejected', () => {
    expect(repairFileUrls('', 'id1', parseRepair({ ...raw, code: '../x' })!)).toBeNull();
    expect(repairFileUrls('', 'id1', parseRepair({ ...raw, original: null })!)).toBeNull();
  });
});
