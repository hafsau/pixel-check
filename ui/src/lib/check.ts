// Check mode ("Check a build"): any build — a public URL or one App.jsx — measured against the three design frames.
// Pure functions only: request validation, a defensive check.json parser, the width-strip mapping and plain-word hints.
import { LIVE_BPS, joinUrl, liveFilesBase, progressOf, validatePageUrl, type LiveBp, type LiveStatus } from './live';
import { fmtScore } from './score';
import type { CellState, StripCell } from './viz';
import { parseRepair, REPAIR_ROUNDS, type Repair } from './repair';
import { parseDiagnostics, type Diagnostics } from './diagnostics';
import { parseBrief, type Brief } from './brief';

export const MAX_CODE_CHARS = 300_000; // api.MAX_CODE
/** Every width the check reports on: the three design sizes plus the sandbox's in-between sweep. */
export const CHECK_WIDTHS = [360, 375, 390, 500, 768, 1024, 1280, 1600] as const;
export const DESIGN_AT: Record<number, LiveBp> = { 390: 'mobile', 768: 'tablet', 1280: 'desktop' };
/** fluidity.py's tolerance for content drifting from where the nearest frame puts it. */
const DRIFT_TOLERANCE = 0.05;

export type CheckSource = 'url' | 'code';
type FrameStatus = 'ok' | 'error' | 'empty';
export type Box = [number, number, number, number];

const fmtN = (n: number) => n.toLocaleString('en-US');
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

// ------------------------------------------------------------------------------------------------ request

export function validateCode(code: string): string | null {
  if (!code.trim()) return 'Paste your App.jsx.';
  if (code.length > MAX_CODE_CHARS) return `App.jsx is over ${fmtN(MAX_CODE_CHARS)} characters.`;
  return null;
}

/** The character counter under the code box: shown prominently from 90 % of the limit. */
export function codeCounter(len: number): { label: string; near: boolean; over: boolean } {
  return { label: `${fmtN(len)} / ${fmtN(MAX_CODE_CHARS)}`, near: len >= MAX_CODE_CHARS * 0.9, over: len > MAX_CODE_CHARS };
}

export interface CheckDraft {
  frames: Record<LiveBp, FrameStatus>;
  source: CheckSource;
  url: string;
  code: string;
  owns: boolean;
  passcode: string;
  /** "Also repair it" (App.jsx only). */
  repair?: boolean;
  /** No design frames: the URL is measured on its own (width breaks, warnings, what vanishes) — no match score. */
  audit?: boolean;
  /** open live mode: the server needs no passcode */
  noPasscode?: boolean;
}

/** What still stops the form from being sent, in words ("Still needed: …"). Only the active source counts. */
export function checkMissing(d: CheckDraft): string[] {
  const out = d.audit ? [] : LIVE_BPS.filter((bp) => d.frames[bp] !== 'ok').map((bp) => `a valid ${bp} frame`);
  if (d.audit && d.source !== 'url') out.push('a build address (an audit needs a URL)');
  else if (d.source === 'url') {
    if (validatePageUrl(d.url)) out.push('a valid build address');
  } else if (!d.code.trim()) out.push('your App.jsx');
  else if (d.code.length > MAX_CODE_CHARS) out.push(`an App.jsx under ${fmtN(MAX_CODE_CHARS)} characters`);
  if (!d.owns) out.push('the ownership confirmation');
  if (!d.noPasscode && !d.passcode.trim()) out.push('the passcode');
  return out;
}

export function checkReady(d: CheckDraft): boolean {
  return checkMissing(d).length === 0;
}

/** Exactly one of url / code goes to the server — the one on the active tab. */
export function checkFields(source: CheckSource, url: string, code: string): { url: string } | { code: string } {
  return source === 'url' ? { url: url.trim() } : { code };
}

/** Repair works on code only: the checkbox counts on the App.jsx tab and is never sent with a URL (the API answers 422). */
export function wantsRepair(source: CheckSource, repair: boolean | undefined): boolean {
  return source === 'code' && !!repair;
}

export function checkFormData(frames: Record<LiveBp, Blob> | null, d: Pick<CheckDraft, 'source' | 'url' | 'code' | 'owns' | 'passcode' | 'repair' | 'audit'>): FormData {
  const fd = new FormData();
  if (!d.audit && frames) LIVE_BPS.forEach((bp) => fd.append(bp, frames[bp], `${bp}.png`));   // an audit sends none
  Object.entries(checkFields(d.source, d.url, d.code)).forEach(([k, v]) => fd.append(k, v));
  fd.append('owns', d.owns ? 'true' : 'false');
  fd.append('passcode', d.passcode);
  if (wantsRepair(d.source, d.repair)) fd.append('repair', 'true');
  return fd;
}

/** Where the form goes after starting a check. `?repair=1` lets the progress page list the repair stage up front. */
export function checkPath(id: string, repair: boolean): string {
  return `/check/${encodeURIComponent(id)}${repair ? '?repair=1' : ''}`;
}

export function repairRequested(search: string): boolean {
  return new URLSearchParams(search).get('repair') === '1';
}

// ------------------------------------------------------------------------------------------------ check.json

/** Where to fetch check.json: the status's `bundle` when it is a plain API path, else the run's own files folder. */
export function checkBundleUrl(base: string, id: string, bundle: string | null | undefined): string {
  if (bundle && /^\/api\/runs\/[^?#]+$/.test(bundle) && !bundle.split('/').includes('..')) return joinUrl(base, bundle);
  return `${liveFilesBase(base, id)}check.json`;
}

export interface CheckComponents {
  structure: number | null;
  layout: number | null;
  color: number | null;
  content_color: number | null;
  bg_match: number | null;
}
export interface CheckRegion {
  kind: string;
  box: Box;
  area: number | null;
}
export interface CheckBp {
  score: number | null;
  components: CheckComponents;
  missingText: string[];
  offset: [number, number] | null;
  regions: CheckRegion[];
}
export interface CheckWidthRow {
  overflow: number | null;
  overlaps: number | null;
  centreDrift: number | null;
  maxGap: number | null;
  bgCovers: boolean | null;
  ok: boolean | null;
}
export interface CheckReport {
  /** 'audit': no design frames — measured on its own, no score */
  mode: 'check' | 'audit';
  warnings: string[];
  /** text visible on a larger size but not on this one (audit) */
  vanished: Partial<Record<LiveBp, string[]>>;
  match: number | null;
  mean: number | null;
  worst: LiveBp | null;
  perBp: Record<LiveBp, number | null>;
  bps: Partial<Record<LiveBp, CheckBp>>;
  fluidity: { pass: boolean | null; fails: string[]; widths: Record<string, CheckWidthRow> };
  runtimeErrors: string[];
}
export interface DesignText {
  text: string;
  box: Box;
}
export interface CheckBundle {
  id: string;
  source: { url: string } | { code: true } | null;
  design: Partial<Record<LiveBp, string>>;
  build: Partial<Record<LiveBp, string>>;
  designTexts: Partial<Record<LiveBp, DesignText[]>>;
  usd: number | null;
  report: CheckReport;
  /** Nemotron's repair of the App.jsx; null when not requested. */
  repair: Repair | null;
  /** readings that explain the score (orchestrator/diagnose.py); {} for older bundles and audits */
  diagnostics: Diagnostics;
  /** the run's frame sizes (scored first screen); null for older bundles and audits */
  sizes: FrameSizes;
  /** what to do next (orchestrator/brief.py); null for older bundles */
  brief: Brief | null;
}

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => !!x && typeof x === 'object' && !Array.isArray(x);
const num = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null);
const bool = (x: unknown): boolean | null => (typeof x === 'boolean' ? x : null);
const obj = (x: unknown): Obj => (isObj(x) ? x : {});
const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const isBp = (x: unknown): x is LiveBp => typeof x === 'string' && (LIVE_BPS as string[]).includes(x);

function box(x: unknown): Box | null {
  const a = arr(x);
  if (a.length !== 4) return null;
  const n = a.map(num);
  return n.every((v): v is number => v != null) ? (n as Box) : null;
}

/** A bundle-relative file path, or null when it is not one (absolute, a scheme, or leaves the folder). */
function relPath(x: unknown): string | null {
  if (typeof x !== 'string' || !x || /^[a-z][a-z0-9+.-]*:/i.test(x) || x.startsWith('/') || x.startsWith('\\')) return null;
  return x.split('/').some((p) => p === '..' || p === '') ? null : x;
}

function perSize<T>(x: unknown, f: (v: unknown) => T | null): Partial<Record<LiveBp, T>> {
  const o = obj(x);
  const out: Partial<Record<LiveBp, T>> = {};
  for (const bp of LIVE_BPS) {
    const v = f(o[bp]);
    if (v != null) out[bp] = v;
  }
  return out;
}

function parseBp(x: unknown): CheckBp {
  const o = obj(x);
  const c = obj(o.components);
  const off = arr(o.offset_px).map(num);
  return {
    score: num(o.score),
    components: { structure: num(c.structure), layout: num(c.layout), color: num(c.color), content_color: num(c.content_color), bg_match: num(c.bg_match) },
    missingText: arr(o.missing_text).filter((t): t is string => typeof t === 'string' && t.trim().length > 0),
    offset: off.length === 2 && off[0] != null && off[1] != null ? [off[0], off[1]] : null,
    regions: arr(o.regions).flatMap((r) => {
      const b = box(obj(r).box);
      if (!b) return [];
      const kind = obj(r).kind;
      return [{ kind: typeof kind === 'string' && kind ? kind : 'region', box: b, area: num(obj(r).area) }];
    }),
  };
}

function parseRow(x: Obj): CheckWidthRow {
  return { overflow: num(x.overflow), overlaps: num(x.overlaps), centreDrift: num(x.centre_drift), maxGap: num(x.max_gap), bgCovers: bool(x.bg_covers), ok: bool(x.ok) };
}

function parseReport(x: unknown, fallbackPerBp?: Partial<Record<LiveBp, number | null>> | null): CheckReport {
  const r = obj(x);
  const bpsRaw = obj(r.breakpoints);
  const bps: Partial<Record<LiveBp, CheckBp>> = {};
  for (const bp of LIVE_BPS) if (bpsRaw[bp] !== undefined) bps[bp] = parseBp(bpsRaw[bp]);
  const perBp = Object.fromEntries(LIVE_BPS.map((bp) => [bp, bps[bp]?.score ?? num(fallbackPerBp?.[bp])])) as Record<LiveBp, number | null>;
  const scored = LIVE_BPS.filter((bp) => perBp[bp] != null);
  const lowest = scored.length ? scored.reduce((a, b) => ((perBp[b] as number) < (perBp[a] as number) ? b : a)) : null;
  const fl = obj(r.fluidity);
  const widths: Record<string, CheckWidthRow> = {};
  for (const [k, v] of Object.entries(obj(fl.widths))) if (isObj(v)) widths[k] = parseRow(v);
  const vanishedRaw = obj(r.vanished);
  const vanished: Partial<Record<LiveBp, string[]>> = {};
  for (const bp of LIVE_BPS) if (Array.isArray(vanishedRaw[bp])) vanished[bp] = arr(vanishedRaw[bp]).filter((t): t is string => typeof t === 'string');
  return {
    mode: r.mode === 'audit' ? 'audit' : 'check',
    warnings: arr(r.warnings).filter((w): w is string => typeof w === 'string'),
    vanished,
    match: num(r.match) ?? (lowest ? perBp[lowest] : null),
    mean: num(r.mean),
    worst: isBp(r.worst) ? r.worst : lowest,
    perBp,
    bps,
    fluidity: {
      pass: bool(fl.pass),
      fails: arr(fl.fails).filter((f) => typeof f === 'string' || num(f) != null).map(String),
      widths,
    },
    runtimeErrors: arr(r.runtime_errors).flatMap((e) => (typeof e === 'string' ? [e] : typeof obj(e).message === 'string' ? [obj(e).message as string] : [])),
  };
}

/** check.json → a fully-typed bundle. Every field is optional on the wire; wrong types become null / empty. */
export function parseCheck(raw: unknown, fallbackPerBp?: Partial<Record<LiveBp, number | null>> | null): CheckBundle {
  if (!isObj(raw) || (raw.type !== undefined && raw.type !== 'check')) throw new Error('This file is not a check result.');
  const src = obj(raw.source);
  return {
    id: typeof raw.id === 'string' ? raw.id : '',
    source: typeof src.url === 'string' && src.url ? { url: src.url } : src.code === true ? { code: true } : null,
    design: perSize(raw.design, relPath),
    build: perSize(raw.build, relPath),
    designTexts: perSize(raw.design_texts, (v) => {
      if (!Array.isArray(v)) return null;
      return v.flatMap((t) => {
        const b = box(obj(t).box);
        const text = obj(t).text;
        return b && typeof text === 'string' && text.trim() ? [{ text, box: b }] : [];
      });
    }),
    usd: num(raw.usd),
    report: parseReport(raw.report, fallbackPerBp),
    repair: parseRepair(raw.repair),
    diagnostics: parseDiagnostics(raw.diagnostics),
    sizes: parseSizes(raw.sizes),
    brief: parseBrief(raw.brief),
  };
}

function parseSizes(x: unknown): FrameSizes {
  if (!isObj(x)) return null;
  const out: Partial<Record<LiveBp, [number, number]>> = {};
  for (const bp of LIVE_BPS) {
    const v = x[bp];
    if (Array.isArray(v) && v.length === 2 && v.every((n) => typeof n === 'number' && n > 0)) out[bp] = [v[0], v[1]];
  }
  return Object.keys(out).length ? out : null;
}

// ------------------------------------------------------------------------------------------------ width strip

export type ReasonKind = 'scroll' | 'overlap' | 'shift' | 'background' | 'gap' | 'other';
export interface Reason {
  kind: ReasonKind;
  text: string;
}
/** Short words for the copy-able summary line. */
const SHORT: Record<ReasonKind, string> = {
  scroll: 'sideways scroll',
  overlap: 'overlapping text',
  shift: 'content shifted',
  background: 'background ends early',
  gap: 'empty gap',
  other: 'check failed',
};

/** Why a width failed, in plain words with its number. `failed` = the server failed it (a gap is then the cause left). */
export function widthReasons(row: CheckWidthRow, failed: boolean = row.ok === false): Reason[] {
  const out: Reason[] = [];
  if ((row.overflow ?? 0) > 0) out.push({ kind: 'scroll', text: `${Math.round(row.overflow!)} px sideways scroll` });
  if ((row.overlaps ?? 0) > 0) out.push({ kind: 'overlap', text: `${plural(row.overlaps!, 'overlapping text')}` });
  if ((row.centreDrift ?? 0) > DRIFT_TOLERANCE) out.push({ kind: 'shift', text: `content shifted ${Math.round(row.centreDrift! * 100)} %` });
  if (row.bgCovers === false) out.push({ kind: 'background', text: 'background ends early' });
  if (failed && !out.length) out.push(row.maxGap != null ? { kind: 'gap', text: `${Math.round(row.maxGap)} px empty gap` } : { kind: 'other', text: 'check failed' });
  return out;
}

export interface CheckCell extends StripCell {
  kind: 'design' | 'between';
  bp?: LiveBp;
  score?: number | null;
  reasons: Reason[];
}

/** The report → one cell per width (360 … 1600). Design sizes carry their score; failures carry their reasons. */
export type FrameSizes = Partial<Record<LiveBp, [number, number]>> | null;

/** The strip's widths: what the sweep measured plus the run's frame widths (frames come at any width); bundles
 *  from before Oct 13 have no sizes and keep the standard layout. */
function stripLayout(report: CheckReport, sizes?: FrameSizes): { widths: number[]; at: Record<number, LiveBp> } {
  if (!sizes) return { widths: [...CHECK_WIDTHS], at: DESIGN_AT };
  const at: Record<number, LiveBp> = Object.fromEntries(LIVE_BPS.flatMap((b) => (sizes[b] ? [[sizes[b]![0], b]] : [])));
  const measured = Object.keys(report.fluidity.widths).map(Number).filter((n) => Number.isFinite(n) && n > 0);
  const widths = [...new Set([...measured, ...Object.keys(at).map(Number)])].sort((a, b) => a - b);
  return widths.length ? { widths, at } : { widths: [...CHECK_WIDTHS], at: DESIGN_AT };
}

export function checkCells(report: CheckReport, sizes?: FrameSizes): CheckCell[] {
  const { widths, fails } = report.fluidity;
  const layout = stripLayout(report, sizes);
  return layout.widths.map((width) => {
    const bp = layout.at[width];
    const key = bp ?? String(width);
    const row = widths[key];
    const base = bp ? { width, kind: 'design' as const, bp, score: report.perBp[bp] } : { width, kind: 'between' as const };
    if (!row) return { ...base, state: 'pending' as CellState, reasons: [] };
    const listed = fails.includes(key);
    const failed = bp ? listed || (row.overflow ?? 0) > 0 || row.bgCovers === false : row.ok != null ? !row.ok : listed || widthReasons(row, false).length > 0;
    const reasons = failed ? widthReasons(row, true) : [];
    return { ...base, state: (failed ? 'fail' : 'pass') as CellState, reasons, detail: reasons.length ? reasons.map((r) => r.text).join(' · ') : undefined };
  });
}

/** One copy-able line: "Worst size 64.2 (mobile) · fails at 360 px: sideways scroll (+2 more)". */
export function checkSummary(report: CheckReport, sizes?: FrameSizes): string {
  const head = `Worst size ${fmtScore(report.match)}${report.worst ? ` (${report.worst})` : ''}`;
  const cells = checkCells(report, sizes);
  const fails = cells.filter((c) => c.state === 'fail');
  if (fails.length) {
    const f = fails[0];
    const why = f.reasons[0] ? SHORT[f.reasons[0].kind] : SHORT.other;
    return `${head} · fails at ${f.width} px: ${why}${fails.length > 1 ? ` (+${fails.length - 1} more)` : ''}`;
  }
  const between = cells.filter((c) => c.kind === 'between');
  const allPass = report.fluidity.pass === true || (between.length > 0 && between.every((c) => c.state === 'pass'));
  return allPass ? `${head} · fits ${cells[0].width}–${cells[cells.length - 1].width} px` : head;
}

// ------------------------------------------------------------------------------------------------ what hurt the score

export interface Hurt {
  key: 'structure' | 'layout' | 'color';
  label: string;
  hint: string;
  value: number;
  bp: LiveBp;
}
const HURT: Record<Hurt['key'], { label: string; hint: string }> = {
  structure: { label: 'Structure', hint: 'blocks and sections differ from the design' },
  layout: { label: 'Layout', hint: 'things sit in a different place' },
  color: { label: 'Colour', hint: 'colours differ from the design' },
};

/** The weakest of structure / layout / colour (lowest across sizes), below `under`, worst first — at most 3. */
export function hurtList(report: CheckReport, under = 0.95): Hurt[] {
  const out: Hurt[] = [];
  for (const key of ['structure', 'layout', 'color'] as const) {
    let best: { value: number; bp: LiveBp } | null = null;
    for (const bp of LIVE_BPS) {
      const c = report.bps[bp]?.components;
      const v = c ? (key === 'color' ? (c.color ?? c.content_color) : c[key]) : null;
      if (v != null && (!best || v < best.value)) best = { value: v, bp };
    }
    if (best && best.value < under) out.push({ key, ...HURT[key], ...best });
  }
  return out.sort((a, b) => a.value - b.value).slice(0, 3);
}

// ------------------------------------------------------------------------------------------------ overlays

const norm = (s: string) => s.trim().replace(/\s+/g, ' ').toLowerCase();

/** Design boxes of the texts the build is missing (each design text used once), to mark them on the design frame. */
export function missingBoxes(missing: string[], texts: DesignText[]): DesignText[] {
  const used = new Set<number>();
  const out: DesignText[] = [];
  for (const m of missing) {
    const k = norm(m);
    let i = texts.findIndex((t, j) => !used.has(j) && norm(t.text) === k);
    if (i < 0) i = texts.findIndex((t, j) => !used.has(j) && norm(t.text).includes(k));
    if (i < 0) continue;
    used.add(i);
    out.push(texts[i]);
  }
  return out;
}

/** A pixel box → CSS percentages of the frame, clamped inside it. */
export function boxPct(b: Box, frame: [number, number]): { left: number; top: number; width: number; height: number } {
  const [W, H] = frame;
  const x0 = Math.max(0, Math.min(W, b[0]));
  const y0 = Math.max(0, Math.min(H, b[1]));
  const x1 = Math.max(x0, Math.min(W, b[0] + b[2]));
  const y1 = Math.max(y0, Math.min(H, b[1] + b[3]));
  return { left: (x0 / W) * 100, top: (y0 / H) * 100, width: ((x1 - x0) / W) * 100, height: ((y1 - y0) / H) * 100 };
}

// ------------------------------------------------------------------------------------------------ progress

const CHECK_CAPTURE = { id: 'capture', label: 'Capturing your build' };
const CHECK_RENDER = { id: 'render', label: 'Rendering your App.jsx' };
const CHECK_REST = [
  { id: 'read design', label: 'Reading your frames' },
  { id: 'score', label: 'Measuring every size' },
];

const CHECK_REPAIR = { id: 'repair', label: `Repairing (≤ ${REPAIR_ROUNDS} rounds)` };
const CHECK_BRIEF = { id: 'brief', label: 'Writing the fix brief (Nemotron)' };

/** The check's stages; App.jsx checks add "repair" when it was asked for or the server already reports it. */
const AUDIT_STAGE = { id: 'audit', label: 'Measuring every width (no designs)' };

export function checkStages(st: Pick<LiveStatus, 'state' | 'stages' | 'source'> & { audit?: boolean }, opts: { repair?: boolean } = {}) {
  if (st.audit) return progressOf([CHECK_CAPTURE, AUDIT_STAGE, CHECK_BRIEF], st);
  const isUrl = !!st.source?.url;
  const repair = !isUrl && (!!opts.repair || st.stages.some((s) => s.stage === 'repair'));
  return progressOf([isUrl ? CHECK_CAPTURE : CHECK_RENDER, ...CHECK_REST, ...(repair ? [CHECK_REPAIR] : []), CHECK_BRIEF], st);
}

// ------------------------------------------------------------------------------------------------ the example (Oct 21)

/** The author's own dashboard frames and its Lovable build (her app — published with her permission). The server
 *  ships these frames' reading (orchestrator/spec_cache), so a live check of the example takes about a minute. */
export const EXAMPLE = {
  url: 'https://adaptable-hub-central.lovable.app/',
  note: 'Example: the author’s dashboard frames and its Lovable build (her own app). Its frames were read in advance, so this check takes about a minute.',
} as const;

export function exampleFrameUrls(base: string): Record<LiveBp, string> {
  const b = base.replace(/\/$/, '');
  return Object.fromEntries(LIVE_BPS.map((bp) => [bp, `${b}/examples/dashboard/${bp}.png`])) as Record<LiveBp, string>;
}

/** How long it takes, honestly: on the free server, reading your own frames is the slow part (~10 minutes). */
export function checkDurationNote({ audit, repairing = false }: { audit: boolean; repairing?: boolean }): string {
  const base = audit
    ? 'An audit usually takes under a minute'
    : 'Reading your own frames takes several minutes on this free server (about 10 for three full pages); the example’s frames are read in advance, so it takes about a minute';
  return `${base}${repairing ? `, plus a few minutes for the repair (≤ ${REPAIR_ROUNDS} Nemotron rounds)` : ''} — keep this page open.`;
}
