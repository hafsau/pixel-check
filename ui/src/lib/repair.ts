// "Repair it": Nemotron's class-only repair loop on a checked App.jsx (orchestrator/repair.py).
// Pure functions only: a defensive parser for check.json's `repair`, the before → after summary and a line diff.
import { LIVE_BPS, liveFilesBase, resolveAsset, type LiveBp } from './live';
import { fmtScore } from './score';

/** The only two files a repair may point at (relative to /api/runs/{id}/files/). */
export const REPAIR_PATH = /^(repair|original)\/App\.jsx$/;
/** Rounds the loop runs at most (api.default_repairer). */
export const REPAIR_ROUNDS = 3;

export interface RepairSnapshot {
  worst: number | null;
  perBp: Record<LiveBp, number | null>;
  fluidFails: number;
  fails: string[];
}
export interface RepairRound {
  round: number;
  worst: number | null;
  fluidFails: number | null;
  applied: number | null;
  candidates: number | null;
}
export interface Repair {
  code: string | null;
  original: string | null;
  start: RepairSnapshot;
  best: RepairSnapshot;
  history: RepairRound[];
  linesKept: number | null;
  usd: number | null;
}

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => !!x && typeof x === 'object' && !Array.isArray(x);
const num = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null);
const obj = (x: unknown): Obj => (isObj(x) ? x : {});
const path = (x: unknown): string | null => (typeof x === 'string' && REPAIR_PATH.test(x) ? x : null);

function snapshot(x: unknown): RepairSnapshot {
  const o = obj(x);
  const per = obj(o.per_bp);
  const fails = (Array.isArray(o.fails) ? o.fails : []).filter((f) => (typeof f === 'string' && f !== '') || num(f) != null).map(String);
  const ff = num(o.fluid_fails);
  return {
    worst: num(o.worst),
    perBp: Object.fromEntries(LIVE_BPS.map((bp) => [bp, num(per[bp])])) as Record<LiveBp, number | null>,
    fluidFails: ff != null && ff >= 0 ? Math.round(ff) : fails.length,
    fails,
  };
}

/** check.json `repair` → a typed block, or null when the check had no repair. Wrong types become null / empty. */
export function parseRepair(x: unknown): Repair | null {
  if (!isObj(x)) return null;
  const rounds = new Map<number, RepairRound>();
  for (const h of Array.isArray(x.history) ? x.history : []) {
    const o = obj(h);
    const round = num(o.round);
    if (round == null || round < 0 || !Number.isInteger(round) || rounds.has(round)) continue;
    rounds.set(round, { round, worst: num(o.worst), fluidFails: num(o.fluid_fails), applied: num(o.applied), candidates: num(o.candidates) });
  }
  const kept = num(x.lines_kept);
  return {
    code: path(x.code),
    original: path(x.original),
    start: snapshot(x.start),
    best: snapshot(x.best),
    history: [...rounds.values()].sort((a, b) => a.round - b.round),
    linesKept: kept == null ? null : Math.min(1, Math.max(0, kept)),
    usd: num(x.usd),
  };
}

/** URLs of the repaired and the original App.jsx, or null when either path was rejected. */
export function repairFileUrls(base: string, id: string, r: Repair): { repaired: string; original: string } | null {
  if (!r.code || !r.original) return null;
  const files = liveFilesBase(base, id);
  const repaired = resolveAsset(files, r.code);
  const original = resolveAsset(files, r.original);
  return repaired && original ? { repaired, original } : null;
}

// ------------------------------------------------------------------------------------------------ outcome

export interface RepairOutcome {
  before: number | null;
  after: number | null;
  delta: number | null;
  /** The repair kept a round: the worst size went up, or stayed level with fewer width failures. */
  improved: boolean;
  /** No round improved it: the original code came back unchanged. */
  unchanged: boolean;
  fluidBefore: number;
  fluidAfter: number;
  /** The round whose code was kept (0 = the original). */
  keptRound: number | null;
}

export function repairOutcome(r: Repair): RepairOutcome {
  const before = r.start.worst;
  const after = r.best.worst;
  const delta = before != null && after != null ? after - before : null;
  const improved = delta != null && (delta > 0 || (delta >= -0.5 && r.best.fluidFails < r.start.fluidFails));
  let keptRound: number | null = null;
  const exact = r.history.find((h) => h.worst === after && (h.fluidFails == null || h.fluidFails === r.best.fluidFails));
  if (exact) keptRound = exact.round;
  else {
    const scored = r.history.filter((h) => h.worst != null);
    if (scored.length) keptRound = scored.reduce((a, b) => ((b.worst as number) > (a.worst as number) ? b : a)).round;
  }
  return { before, after, delta, improved, unchanged: !improved, fluidBefore: r.start.fluidFails, fluidAfter: r.best.fluidFails, keptRound };
}

/** "+9.0" / "−1.2" / "±0.0" (true minus sign). */
export function fmtDelta(d: number | null | undefined): string {
  if (d == null || Number.isNaN(d)) return '—';
  const s = Math.abs(d).toFixed(1);
  if (s === '0.0') return '±0.0';
  return `${d > 0 ? '+' : '−'}${s}`;
}

export function linesKeptLabel(k: number | null): string {
  return k == null ? '' : `lines kept ${Math.round(k * 100)} %`;
}

export function widthFailsLabel(before: number | null, after: number | null): string {
  return before == null || after == null ? '' : `width failures ${before} → ${after}`;
}

export interface RepairSize {
  bp: LiveBp;
  before: number | null;
  after: number | null;
  delta: number | null;
}

export function repairSizes(r: Repair): RepairSize[] {
  return LIVE_BPS.map((bp) => {
    const before = r.start.perBp[bp];
    const after = r.best.perBp[bp];
    return { bp, before, after, delta: before != null && after != null ? after - before : null };
  });
}

export interface RoundBar {
  round: number;
  worst: number | null;
  /** Bar height, 0–100 (the score scale). */
  pct: number;
  kept: boolean;
}

export function roundBars(r: Repair, keptRound: number | null): RoundBar[] {
  return r.history.map((h) => ({ round: h.round, worst: h.worst, pct: h.worst == null ? 0 : Math.min(100, Math.max(0, h.worst)), kept: h.round === keptRound }));
}

/** One copy-able line for the repair. */
export function repairSummary(r: Repair, o: RepairOutcome): string {
  if (o.unchanged) return `Repair: no round improved it (worst size ${fmtScore(o.before)}) — code unchanged`;
  const parts = [`Repair: worst size ${fmtScore(o.before)} → ${fmtScore(o.after)} (${fmtDelta(o.delta)})`, widthFailsLabel(o.fluidBefore, o.fluidAfter), linesKeptLabel(r.linesKept)];
  return parts.filter(Boolean).join(' · ');
}

// ------------------------------------------------------------------------------------------------ diff

export interface DiffOp {
  kind: 'same' | 'add' | 'del';
  text: string;
  /** 1-based line number in the original (same / del). */
  a?: number;
  /** 1-based line number in the repaired file (same / add). */
  b?: number;
}

export function splitLines(s: string): string[] {
  if (!s) return [];
  return s.replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n');
}

/**
 * Myers' O((N+M)·D) shortest edit script over lines. Common prefix / suffix are trimmed first; when the
 * edit distance of the middle exceeds `maxD` it becomes one block of removals then additions (still a valid diff).
 * Inside each change block removals come before additions.
 */
export function diffLines(a: string[], b: string[], maxD = 2000): DiffOp[] {
  let pre = 0;
  while (pre < a.length && pre < b.length && a[pre] === b[pre]) pre++;
  let suf = 0;
  while (suf < a.length - pre && suf < b.length - pre && a[a.length - 1 - suf] === b[b.length - 1 - suf]) suf++;
  const am = a.slice(pre, a.length - suf);
  const bm = b.slice(pre, b.length - suf);
  // middle as raw steps over indices local to am / bm
  const steps = myers(am, bm, maxD) ?? [...am.map((_, i) => ({ kind: 'del' as const, i, j: -1 })), ...bm.map((_, j) => ({ kind: 'add' as const, i: -1, j }))];

  const out: DiffOp[] = [];
  for (let i = 0; i < pre; i++) out.push({ kind: 'same', text: a[i], a: i + 1, b: i + 1 });
  let dels: DiffOp[] = [];
  let adds: DiffOp[] = [];
  const flush = () => {
    out.push(...dels, ...adds);
    dels = [];
    adds = [];
  };
  for (const s of steps) {
    if (s.kind === 'same') {
      flush();
      out.push({ kind: 'same', text: am[s.i], a: pre + s.i + 1, b: pre + s.j + 1 });
    } else if (s.kind === 'del') dels.push({ kind: 'del', text: am[s.i], a: pre + s.i + 1 });
    else adds.push({ kind: 'add', text: bm[s.j], b: pre + s.j + 1 });
  }
  flush();
  for (let k = 0; k < suf; k++) {
    const i = a.length - suf + k;
    const j = b.length - suf + k;
    out.push({ kind: 'same', text: a[i], a: i + 1, b: j + 1 });
  }
  return out;
}

type Step = { kind: 'same' | 'add' | 'del'; i: number; j: number };

function myers(a: string[], b: string[], maxD: number): Step[] | null {
  const n = a.length;
  const m = b.length;
  if (!n && !m) return [];
  const max = n + m;
  const off = max + 1;
  const v = new Int32Array(2 * max + 3);
  const trace: Int32Array[] = []; // trace[d] = v[-d-1 .. d+1] before round d
  let found = -1;
  for (let d = 0; d <= Math.min(max, maxD); d++) {
    trace.push(v.slice(off - d - 1, off + d + 2));
    for (let k = -d; k <= d; k += 2) {
      let x = k === -d || (k !== d && v[off + k - 1] < v[off + k + 1]) ? v[off + k + 1] : v[off + k - 1] + 1;
      let y = x - k;
      while (x < n && y < m && a[x] === b[y]) {
        x++;
        y++;
      }
      v[off + k] = x;
      if (x >= n && y >= m) {
        found = d;
        break;
      }
    }
    if (found >= 0) break;
  }
  if (found < 0) return null;

  const rev: Step[] = [];
  let x = n;
  let y = m;
  for (let d = found; d >= 0; d--) {
    const t = trace[d];
    const at = (k: number) => t[k + d + 1];
    const k = x - y;
    const prevK = k === -d || (k !== d && at(k - 1) < at(k + 1)) ? k + 1 : k - 1;
    const prevX = d === 0 ? 0 : at(prevK);
    const prevY = d === 0 ? 0 : prevX - prevK;
    while (x > prevX && y > prevY) {
      rev.push({ kind: 'same', i: x - 1, j: y - 1 });
      x--;
      y--;
    }
    if (d > 0) {
      if (x === prevX) rev.push({ kind: 'add', i: -1, j: y - 1 });
      else rev.push({ kind: 'del', i: x - 1, j: -1 });
    }
    x = prevX;
    y = prevY;
  }
  return rev.reverse();
}

export function diffStats(ops: DiffOp[]): { added: number; removed: number } {
  let added = 0;
  let removed = 0;
  for (const o of ops) {
    if (o.kind === 'add') added++;
    else if (o.kind === 'del') removed++;
  }
  return { added, removed };
}

export interface Hunk {
  aStart: number;
  aLines: number;
  bStart: number;
  bLines: number;
  lines: DiffOp[];
}

/** Only the changed parts, each with `context` unchanged lines around it; hunks whose context touches are merged. */
export function diffHunks(ops: DiffOp[], context = 2): Hunk[] {
  const changes = ops.flatMap((o, i) => (o.kind === 'same' ? [] : [i]));
  if (!changes.length) return [];
  const ranges: [number, number][] = [];
  for (const i of changes) {
    const lo = Math.max(0, i - context);
    const hi = Math.min(ops.length - 1, i + context);
    const last = ranges[ranges.length - 1];
    if (last && lo <= last[1] + 1) last[1] = Math.max(last[1], hi);
    else ranges.push([lo, hi]);
  }
  return ranges.map(([lo, hi]) => {
    const lines = ops.slice(lo, hi + 1);
    const before = ops.slice(0, lo);
    const firstA = lines.find((o) => o.a != null)?.a;
    const firstB = lines.find((o) => o.b != null)?.b;
    const prevA = [...before].reverse().find((o) => o.a != null)?.a ?? 0;
    const prevB = [...before].reverse().find((o) => o.b != null)?.b ?? 0;
    const aLines = lines.filter((o) => o.a != null).length;
    const bLines = lines.filter((o) => o.b != null).length;
    return { aStart: firstA ?? prevA, aLines, bStart: firstB ?? prevB, bLines, lines };
  });
}
