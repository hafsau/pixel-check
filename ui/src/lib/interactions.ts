// Turns an interaction verdict (orchestrator/acceptance.py, exported by tools/export_interaction.py) into what the
// Interactions view shows: a checklist of the generated tests per breakpoint, and the attempt timeline.
//
// The verdict stores scores for opens / closes / escape / keyboard and a list of failure sentences, most of them
// prefixed "<bp>: ". Checks without a score (aria, trigger look, base) are derived from those sentences.

import type { Attempt, BpName, PerBp, RepeatSet, Variant } from './types';

export const STATE_MIN = 75; // acceptance.STATE_MIN — an opened state must match its frame at least this well

export type CheckId = 'base' | 'opens' | 'closes' | 'escape' | 'keyboard' | 'aria' | 'look';
export type CellStatus = 'pass' | 'fail' | 'skipped';

export interface ChecklistCell {
  status: CellStatus;
  score?: number;
  reasons: string[];
  note?: string;
}

export interface ChecklistRow {
  id: CheckId;
  label: string;
  detail: string;
  cells: Partial<Record<BpName, ChecklistCell>>;
}

export const CHECKS: { id: CheckId; label: string; detail: string }[] = [
  { id: 'base', label: 'Untouched page', detail: 'Before any click the page still matches the design like the static page (within 3 points).' },
  { id: 'opens', label: 'Opens', detail: `Click the trigger: the page matches the state frame (score ≥ ${STATE_MIN}).` },
  { id: 'closes', label: 'Closes', detail: 'Click the trigger again: the page is restored.' },
  { id: 'escape', label: 'Escape', detail: 'Open, press Escape: the page is restored. Runs once the state opens.' },
  { id: 'keyboard', label: 'Keyboard', detail: `Focus the trigger, press Enter: it opens (score ≥ ${STATE_MIN}).` },
  { id: 'aria', label: 'ARIA', detail: 'aria-expanded follows the state; aria-controls names the rendered panel; ids are unique.' },
  { id: 'look', label: 'Trigger look', detail: "The trigger's open look matches the design (e.g. hamburger → X), checked when the design's trigger changes." },
];

/** Phrases (after the "<bp>: " prefix) that belong to each check. Order matters: the first match wins. */
const RULES: { id: CheckId; test: (s: string) => boolean }[] = [
  { id: 'aria', test: (s) => /aria-/.test(s) && !/^the panel #/.test(s) },
  { id: 'base', test: (s) => s.startsWith('before any click') || s.startsWith('the page did not render') },
  { id: 'look', test: (s) => s.startsWith("the trigger's open look") },
  { id: 'closes', test: (s) => s.startsWith('clicking the trigger again') },
  { id: 'escape', test: (s) => s.startsWith('pressing Escape') || s.startsWith('opening then pressing Escape') },
  { id: 'keyboard', test: (s) => s.startsWith('keyboard') },
  {
    id: 'opens',
    test: (s) => s.startsWith('after clicking the trigger') || s.startsWith('clicking the trigger failed') || s.startsWith('the panel #'),
  },
];

const GLOBAL_ARIA = /ids must be unique/;
const NOTHING_RAN = /^(the code does not build|infrastructure:|format:)/;

function splitBp(f: string, bps: BpName[]): { bp: BpName | null; text: string } {
  for (const bp of bps) if (f.startsWith(`${bp}: `)) return { bp, text: f.slice(bp.length + 2) };
  return { bp: null, text: f };
}

export function buildChecklist(a: Attempt, bps: BpName[], stateMin = STATE_MIN): { rows: ChecklistRow[]; general: string[] } {
  const general: string[] = [];
  const reasons = new Map<string, string[]>(); // `${id}|${bp}` → reasons
  const add = (id: CheckId, bp: BpName, r: string) => {
    const k = `${id}|${bp}`;
    reasons.set(k, [...(reasons.get(k) ?? []), r]);
  };
  const nothingRan = a.infra || a.failures.some((f) => NOTHING_RAN.test(f));

  for (const f of a.failures) {
    const { bp, text } = splitBp(f, bps);
    if (bp == null) {
      if (GLOBAL_ARIA.test(text)) bps.forEach((b) => add('aria', b, text));
      else general.push(f);
      continue;
    }
    const rule = RULES.find((r) => r.test(text));
    if (rule) add(rule.id, bp, text);
    else general.push(f);
  }

  const score = (bp: BpName, check: string) => a.checks.find((c) => c.bp === bp && c.check === check)?.score;

  const rows: ChecklistRow[] = CHECKS.map((c) => {
    const cells: Partial<Record<BpName, ChecklistCell>> = {};
    for (const bp of bps) {
      const rs = reasons.get(`${c.id}|${bp}`) ?? [];
      const opened = score(bp, 'opens');
      let cell: ChecklistCell;
      if (nothingRan) cell = { status: 'skipped', reasons: [], note: 'Not run' };
      else if (c.id === 'base') {
        const s = a.base_scores?.[bp];
        cell = { status: rs.length ? 'fail' : s != null ? 'pass' : 'skipped', score: s, reasons: rs };
      } else if (c.id === 'aria' || c.id === 'look') {
        cell = { status: rs.length ? 'fail' : opened != null ? 'pass' : 'skipped', reasons: rs };
      } else {
        const s = score(bp, c.id);
        if (c.id === 'keyboard' && s != null && s < stateMin) cell = { status: 'fail', score: s, reasons: rs, note: rs.length ? undefined : 'Clicking does not open it either' };
        else if (rs.length) cell = { status: 'fail', score: s, reasons: rs };
        else if (s != null) cell = { status: 'pass', score: s, reasons: [] };
        else cell = { status: 'skipped', reasons: [], note: c.id === 'escape' && opened != null ? 'Runs once the state opens' : 'Not run' };
      }
      cells[bp] = cell;
    }
    return { id: c.id, label: c.label, detail: c.detail, cells };
  });
  return { rows, general };
}

// ------------------------------------------------------------------------------------------------

export type TimelineStep =
  | {
      kind: 'attempt';
      index: number;
      label: string;
      pass: boolean;
      infra: boolean;
      failureCount: number;
      worstScore: number | null;
      worstBp: BpName | null;
      sandboxS: number | null;
      sandboxUsd: number | null;
    }
  | { kind: 'revise'; by: string; infra: boolean; fedBack: string[] }
  | { kind: 'outcome'; pass: boolean; attempts: number };

export function writerName(w: string): string {
  return w === 'nemotron' ? 'Nemotron' : w === 'template' ? 'Template' : w;
}

function worst(scores: PerBp): { bp: BpName | null; score: number | null } {
  let bp: BpName | null = null;
  let s: number | null = null;
  for (const [k, v] of Object.entries(scores ?? {})) if (v != null && (s == null || v < s)) [bp, s] = [k, v];
  return { bp, score: s };
}

export function buildTimeline(v: Variant): TimelineStep[] {
  const out: TimelineStep[] = [];
  v.attempts.forEach((a, i) => {
    const w = worst(a.state_scores);
    out.push({
      kind: 'attempt',
      index: i,
      label: `Attempt ${i + 1}`,
      pass: a.pass,
      infra: a.infra,
      failureCount: a.failures.length,
      worstScore: w.score,
      worstBp: w.bp,
      sandboxS: a.sandbox?.wall_s ?? null,
      sandboxUsd: a.sandbox?.cost ?? null,
    });
    if (i < v.attempts.length - 1 && !a.pass) out.push({ kind: 'revise', by: writerName(v.writer), infra: a.infra, fedBack: a.infra ? [] : a.failures });
  });
  if (v.attempts.length) out.push({ kind: 'outcome', pass: v.pass, attempts: v.attempts.length });
  return out;
}

export function bestAttempt(v: Variant): Attempt | null {
  if (!v.attempts.length) return null;
  const i = v.best_attempt;
  return i != null && i >= 0 && i < v.attempts.length ? v.attempts[i] : v.attempts[v.attempts.length - 1];
}

// ------------------------------------------------------------------------------------------------

export interface RepeatSummary {
  label: string;
  writer: string;
  runs: number;
  passed: number;
  firstTry: number;
  attemptsToPass: number[];
  meanUsd: number | null;
  meanSeconds: number | null;
}

const mean = (xs: (number | null | undefined)[]): number | null => {
  const v = xs.filter((x): x is number => x != null);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
};

export function summarizeRepeats(sets: RepeatSet[]): RepeatSummary[] {
  return sets.map((s) => ({
    label: s.label,
    writer: s.writer,
    runs: s.runs.length,
    passed: s.runs.filter((r) => r.pass).length,
    firstTry: s.runs.filter((r) => r.pass && r.first_pass_attempt === 0).length,
    attemptsToPass: s.runs.filter((r) => r.pass && r.first_pass_attempt != null).map((r) => (r.first_pass_attempt as number) + 1),
    meanUsd: mean(s.runs.map((r) => r.usd)),
    meanSeconds: mean(s.runs.map((r) => r.seconds)),
  }));
}

export function compareWriters(vs: Variant[]): { template: Variant | null; nemotron: Variant | null; delta: PerBp } {
  const template = vs.find((v) => v.writer === 'template') ?? null;
  const nemotron = vs.find((v) => v.writer === 'nemotron') ?? null;
  const delta: PerBp = {};
  const t = template && bestAttempt(template);
  const n = nemotron && bestAttempt(nemotron);
  if (t && n) for (const [bp, s] of Object.entries(n.state_scores)) if (s != null && t.state_scores[bp] != null) delta[bp] = s - (t.state_scores[bp] as number);
  return { template, nemotron, delta };
}

/** One sentence comparing the two writers, from the recorded numbers only (no rounding up, no adjectives). */
export function verdictLine(vs: Variant[]): string | null {
  const c = compareWriters(vs);
  if (!c.template || !c.nemotron) return null;
  const t = c.template.pass;
  const n = c.nemotron.pass;
  if (t && !n) return `The template passes; Nemotron fails in this run after ${c.nemotron.attempts.length} attempts.`;
  if (!t && n) return 'Nemotron passes; the template fails.';
  if (!t && !n) return 'Neither passes in these runs.';
  const ds = Object.values(c.delta).filter((x): x is number => x != null);
  const max = ds.length ? Math.max(...ds.map(Math.abs)) : 0;
  if (max < 0.05) return 'Both pass with identical state scores.';
  if (ds.every((d) => d <= 0.05)) return `Both pass; the template scores up to ${max.toFixed(1)} points higher.`;
  if (ds.every((d) => d >= -0.05)) return `Both pass; Nemotron scores up to ${max.toFixed(1)} points higher.`;
  return `Both pass; state scores differ by up to ${max.toFixed(1)} points, in both directions.`;
}
