// Parsing of ui/public/runs/index.json. Tolerates entries from older exporters (no "type" = static run).
import type { BundleType, IndexEntry } from './types';

const TYPES: BundleType[] = ['static', 'interaction', 'group'];

type Raw = Record<string, unknown>;

function isObj(x: unknown): x is Raw {
  return typeof x === 'object' && x !== null && !Array.isArray(x);
}

export function normalizeIndex(raw: unknown): IndexEntry[] {
  if (!Array.isArray(raw)) return [];
  const out: IndexEntry[] = [];
  for (const r of raw) {
    if (!isObj(r) || typeof r.id !== 'string' || !r.id) continue;
    const type = (r.type ?? 'static') as BundleType;
    if (!TYPES.includes(type)) continue;
    const base = { ...r, id: r.id, title: typeof r.title === 'string' ? r.title : r.id, created: Number(r.created) || 0 };
    if (type === 'static') out.push({ ...base, type, match: Number(r.match) || 0, per_bp: isObj(r.per_bp) ? r.per_bp : {} } as IndexEntry);
    else if (type === 'interaction')
      out.push({ ...base, type, variants: Array.isArray(r.variants) ? r.variants : [], bps: Array.isArray(r.bps) ? r.bps : [], page: String(r.page ?? ''), state: String(r.state ?? ''), kind: (r.kind as string) ?? null } as IndexEntry);
    else out.push({ ...base, type, variants: Array.isArray(r.variants) ? r.variants : [], held: Array.isArray(r.held) ? r.held : [], given: (r.given as string) ?? null, page: String(r.page ?? '') } as IndexEntry);
  }
  return out.sort((a, b) => b.created - a.created);
}

export function splitIndex(entries: IndexEntry[]) {
  return {
    static: entries.filter((e) => e.type === 'static'),
    interaction: entries.filter((e) => e.type === 'interaction'),
    group: entries.filter((e) => e.type === 'group'),
  } as {
    static: Extract<IndexEntry, { type: 'static' }>[];
    interaction: Extract<IndexEntry, { type: 'interaction' }>[];
    group: Extract<IndexEntry, { type: 'group' }>[];
  };
}

export function entryHref(e: { type: BundleType; id: string }): string {
  const id = encodeURIComponent(e.id);
  if (e.type === 'interaction') return `/interaction/${id}`;
  if (e.type === 'group') return `/group/${id}`;
  return `/run/${id}`;
}

export function pageLabel(slug: string | undefined): string {
  return slug ?? '';
}

/** "Sign-up page (dev capture)" → title "Sign-up page" + note "dev capture" (shown as a chip). */
export function splitTitle(t: string): { title: string; note: string | null } {
  const m = t.match(/^(.*\S)\s*\(([^()]+)\)\s*$/);
  return m ? { title: m[1], note: m[2] } : { title: t, note: null };
}
