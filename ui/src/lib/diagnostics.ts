import type { LiveBp } from './live';

/** Check diagnostics (orchestrator/diagnose.py, Oct 13 council): readings beside the score that explain it — what
 *  happened to each text the scorer could not credit, how far the build drifts band by band, named differences and
 *  the points each factor cost. They never change the score. */

export type TextStatusKind = 'missing' | 'moved' | 'below' | 'unreadable';
export interface TextStatus {
  text: string;
  status: TextStatusKind;
  dy?: number;
  dx?: number;
}
export interface DriftBand {
  y0: number;
  y1: number;
  dy: number | null;
  unsure?: boolean;
}
export interface Drift {
  bands: DriftBand[];
  scale: number | null;
}
export type LostKey = 'layout' | 'color' | 'text' | 'offset';
export interface SizeDiagnostics {
  text: TextStatus[];
  drift: Drift | null;
  lost: Partial<Record<LostKey, number>> | null;
  font: { design: string; build: string } | null;
  textSize: number | null;
}
export type Diagnostics = Partial<Record<LiveBp, SizeDiagnostics>>;

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => !!x && typeof x === 'object' && !Array.isArray(x);
const num = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null);
const KINDS: TextStatusKind[] = ['missing', 'moved', 'below', 'unreadable'];
const BPS: LiveBp[] = ['mobile', 'tablet', 'desktop'];

function parseDrift(x: unknown): Drift | null {
  if (!isObj(x) || !Array.isArray(x.bands)) return null;
  const bands = x.bands.flatMap((b): DriftBand[] => {
    if (!isObj(b) || num(b.y0) == null || num(b.y1) == null) return [];
    return [{ y0: b.y0 as number, y1: b.y1 as number, dy: num(b.dy), ...(b.unsure === true ? { unsure: true } : {}) }];
  });
  return { bands, scale: num(x.scale) };
}

export function parseDiagnostics(raw: unknown): Diagnostics {
  const out: Diagnostics = {};
  if (!isObj(raw)) return out;
  for (const bp of BPS) {
    const d = raw[bp];
    if (!isObj(d)) continue;
    const text = (Array.isArray(d.text) ? d.text : []).flatMap((t): TextStatus[] => {
      if (!isObj(t) || typeof t.text !== 'string' || !KINDS.includes(t.status as TextStatusKind)) return [];
      const dy = num(t.dy);
      const dx = num(t.dx);
      return [{ text: t.text, status: t.status as TextStatusKind, ...(dy != null ? { dy } : {}), ...(dx != null ? { dx } : {}) }];
    });
    const lost = isObj(d.lost)
      ? (Object.fromEntries((['layout', 'color', 'text', 'offset'] as LostKey[]).flatMap((k) => (num((d.lost as Obj)[k]) != null ? [[k, num((d.lost as Obj)[k])]] : []))) as SizeDiagnostics['lost'])
      : null;
    const f = isObj(d.font) && typeof d.font.design === 'string' && typeof d.font.build === 'string' ? { design: d.font.design, build: d.font.build } : null;
    out[bp] = { text, drift: parseDrift(d.drift), lost, font: f, textSize: num(d.text_size) };
  }
  return out;
}

/** What happened to a text the score could not credit — "missing" only when it is not in the build at all. */
export function textStatusLabel(t: TextStatus): string {
  if (t.status === 'missing') return 'not in the build';
  if (t.status === 'below') return 'in the build, below the first screen';
  if (t.status === 'unreadable') return 'in place, but covered or too faint to read';
  const dy = t.dy ?? 0;
  const dx = t.dx ?? 0;
  if (t.dy == null && t.dx == null) return 'in the build, elsewhere';
  if (Math.abs(dy) >= Math.abs(dx)) return `in the build, ${Math.abs(dy)} px ${dy < 0 ? 'higher' : 'lower'} than the design`;
  return `in the build, ${Math.abs(dx)} px ${dx < 0 ? 'left' : 'right'} of the design`;
}

/** Plain-language differences worth naming (small ones are left out). */
export function findings(d: SizeDiagnostics): string[] {
  const out: string[] = [];
  if (d.font) out.push(`Font: ${d.font.build} (design: ${d.font.design})`);
  if (d.textSize != null && Math.abs(1 - d.textSize) >= 0.08)
    out.push(`Text about ${Math.round(Math.abs(1 - d.textSize) * 100)}% ${d.textSize < 1 ? 'smaller' : 'larger'} than the design`);
  const last = [...(d.drift?.bands ?? [])].reverse().find((b) => b.dy != null)?.dy ?? null;
  const scale = d.drift?.scale ?? null;
  if (scale != null && last != null && Math.abs(1 - scale) >= 0.015 && Math.abs(last) >= 12)
    out.push(
      `Spacing about ${Math.round(Math.abs(1 - scale) * 100)}% ${scale < 1 ? 'tighter' : 'looser'}: by the bottom of the screen the build sits ${Math.abs(last)} px ${last < 0 ? 'higher' : 'lower'}`,
    );
  return out;
}

const LOST_LABEL: Record<LostKey, string> = { layout: 'Layout and edges', color: 'Colour', text: 'Text', offset: 'Alignment shift' };

/** Points each factor cost (they add up to 100 − score), biggest first; under half a point left out. */
export function lostRows(lost: SizeDiagnostics['lost']): { key: LostKey; label: string; points: number }[] {
  if (!lost) return [];
  return (Object.entries(lost) as [LostKey, number][])
    .filter(([, v]) => v >= 0.5)
    .sort((a, b) => b[1] - a[1])
    .map(([key, v]) => ({ key, label: LOST_LABEL[key], points: Math.round(v) }));
}

const signed = (v: number) => (v > 0 ? `+${v}` : v < 0 ? `−${Math.abs(v)}` : '0');

/** "−14 · ? · −150 px": the build's offset from the design, band by band from the top of the screen. */
export function driftLine(d: Drift | null): string | null {
  if (!d || !d.bands.length) return null;
  return `${d.bands.map((b) => (b.dy == null ? '?' : signed(b.dy))).join(' · ')} px`;
}
