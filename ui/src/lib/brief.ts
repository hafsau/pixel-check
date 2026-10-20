/** Fix brief (orchestrator/brief.py, Oct 20): what to do next, written by NVIDIA Nemotron 3 Super from the check's
 *  measured facts; a verifier outside the model keeps only claims the facts back. Never part of the score. */

export interface BriefFact {
  id: string;
  bp: string | null;
  kind: string;
  text: string;
}
export interface BriefItem {
  text: string;
  facts: BriefFact[];
}
export interface Brief {
  source: 'nemotron' | 'template' | 'none';
  model: string | null;
  intro: string;
  summary: BriefItem[];
  fix: BriefItem[];
  /** platform badges: not your layout, so never part of the paste-in message */
  notes: BriefItem[];
  dropped: number;
  /** claims the verifier dropped, with the reason */
  droppedItems: { text: string; why: string }[];
  /** instructions written from the measurements where Nemotron's were dropped or missing */
  added: number;
  facts: BriefFact[];
}

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => !!x && typeof x === 'object' && !Array.isArray(x);
const SOURCES = ['nemotron', 'template', 'none'] as const;

export function parseBrief(raw: unknown): Brief | null {
  if (!isObj(raw) || !SOURCES.includes(raw.source as Brief['source'])) return null;
  const facts = (Array.isArray(raw.facts) ? raw.facts : []).flatMap((f): BriefFact[] =>
    isObj(f) && typeof f.id === 'string' && typeof f.text === 'string'
      ? [{ id: f.id, bp: typeof f.bp === 'string' ? f.bp : null, kind: typeof f.kind === 'string' ? f.kind : '', text: f.text }]
      : [],
  );
  const byId = new Map(facts.map((f) => [f.id, f]));
  const items = (x: unknown): BriefItem[] =>
    (Array.isArray(x) ? x : []).flatMap((it): BriefItem[] => {
      if (!isObj(it) || typeof it.text !== 'string' || !it.text.trim()) return [];
      const linked = (Array.isArray(it.facts) ? it.facts : []).flatMap((id) => (typeof id === 'string' && byId.has(id) ? [byId.get(id)!] : []));
      return [{ text: it.text, facts: linked }];
    });
  return {
    source: raw.source as Brief['source'],
    model: typeof raw.model === 'string' ? raw.model : null,
    intro: typeof raw.intro === 'string' ? raw.intro : '',
    summary: items(raw.summary),
    fix: items(raw.fix),
    notes: items(raw.notes),
    dropped: typeof raw.dropped === 'number' && raw.dropped > 0 ? Math.round(raw.dropped) : 0,
    droppedItems: (Array.isArray(raw.dropped_items) ? raw.dropped_items : []).flatMap((d) =>
      isObj(d) && typeof d.text === 'string' && typeof d.why === 'string' ? [{ text: d.text, why: d.why }] : [],
    ),
    added: typeof raw.added === 'number' && raw.added > 0 ? Math.round(raw.added) : 0,
    facts,
  };
}

/** The message to paste into the AI builder: the intro, then one line per instruction. */
export function pasteText(b: Brief): string {
  return [b.intro, ...b.fix.map((i) => `- ${i.text}`)].filter(Boolean).join('\n');
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** Who wrote the brief and what the verifier did. */
export function briefFooter(b: Brief): string {
  if (b.source === 'none') return 'Nothing to fix: no differences worth acting on.';
  const facts = plural(b.facts.length, 'measured fact');
  if (b.source === 'template') return `Written from the ${facts} (Nemotron was unavailable or none of its claims could be backed).`;
  const tail = b.dropped
    ? `A check outside the model dropped ${plural(b.dropped, 'claim')} the measurements did not back.`
    : 'Every claim is backed by a measurement.';
  const added = b.added ? `; ${plural(b.added, 'line')} added from the measurements where its own were dropped or missing` : '';
  return `Written by NVIDIA Nemotron 3 Super from ${facts}${added}. ${tail}`;
}
