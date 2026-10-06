// Owned sites (run.json "display" + "real", tools/export_run.py). Both are null for every other run and absent in
// older bundles. display = the delivered App.jsx (the scored code with the page's own images put back into the grey
// placeholder boxes); real = screenshots of the owner's page ("Your site").
import type { BpName, Display, Run } from './types';
import type { Load } from './data';

/** The only asset paths a bundle may list: content-addressed images under assets/. */
export const ASSET_RE = /^assets\/[0-9a-f]{64}\.(png|jpg|gif|webp|avif|svg)$/;
const DISPLAY_CODE_RE = /^display\/[A-Za-z0-9_-]+\.jsx$/;
const REAL_RE = /^real\/[A-Za-z0-9_-]+\.(webp|png|jpg|jpeg|avif)$/;
const BP_KEY_RE = /^[a-z][a-z0-9_-]*$/;

export type { Display };

export type Real = Partial<Record<BpName, string>>;

export type OwnedRun = Run & { display: Display | null; real: Real | null };

const isObj = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null && !Array.isArray(x);

export function parseDisplay(raw: unknown): Display | null {
  if (!isObj(raw) || typeof raw.code !== 'string' || !DISPLAY_CODE_RE.test(raw.code)) return null;
  const assets = Array.isArray(raw.assets) ? [...new Set(raw.assets.filter((a): a is string => typeof a === 'string' && ASSET_RE.test(a)))] : [];
  const n = typeof raw.images === 'number' && Number.isFinite(raw.images) ? Math.floor(raw.images) : 0;
  return { code: raw.code, assets, images: Math.max(0, n), candidate: typeof raw.candidate === 'string' ? raw.candidate : null };
}

export function parseReal(raw: unknown): Real | null {
  if (!isObj(raw)) return null;
  const out: Real = {};
  for (const [k, v] of Object.entries(raw)) if (BP_KEY_RE.test(k) && typeof v === 'string' && REAL_RE.test(v)) out[k] = v;
  return Object.keys(out).length ? out : null;
}

/** run.json as loaded → the same run with display / real sanitised (absent → null). Does not mutate. */
export function normalizeRun(raw: Run): OwnedRun {
  const r = raw as Run & { display?: unknown; real?: unknown };
  return { ...raw, display: parseDisplay(r.display), real: parseReal(r.real) };
}

export type CodeVersion = 'delivered' | 'scored';

/** Bundle paths of the best candidate's scored App.jsx and of the delivered one (null when absent). */
export function codeSources(run: Run): { scored: string | null; delivered: string | null } {
  const best = run.candidates.find((c) => c.id === run.result.best);
  return { scored: best?.code ?? null, delivered: run.display?.code ?? null };
}

export type BestCode = { status: 'loading' } | { status: 'error'; error: string } | { status: 'ready'; scored: string | null; delivered: string | null };

/** Both loads → one state. The delivered code is optional: if it fails or is empty, the scored code stands alone. */
export function combineCode(scored: Load<string>, delivered: Load<string>): BestCode {
  if (scored.status === 'loading' || delivered.status === 'loading') return { status: 'loading' };
  if (scored.status === 'error') return { status: 'error', error: scored.error };
  return { status: 'ready', scored: scored.data || null, delivered: delivered.status === 'ready' && delivered.data ? delivered.data : null };
}

/** "Your site" · "What we verify against" · "Rebuild" for one breakpoint; null when the run has no real screenshots. */
export function threeUp(run: Run, bp: BpName): { real: string | null; design: string | null; rebuild: string | null } | null {
  if (!run.real) return null;
  const best = run.candidates.find((c) => c.id === run.result.best);
  return { real: run.real[bp] ?? null, design: run.design?.[bp] ?? null, rebuild: best?.renders?.[bp] ?? null };
}
