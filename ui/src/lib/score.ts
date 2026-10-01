// Score bands. Thresholds follow the scorer's calibration:
// 100 identical · ~93 visually the same · 80–86 same page with small slips · ~60 recognisable but off · <46 not the design.

export type Band = 'good' | 'ok' | 'warn' | 'bad';

export const BANDS: { band: Band; min: number; label: string }[] = [
  { band: 'good', min: 90, label: 'Visually the same' },
  { band: 'ok', min: 75, label: 'Same page, small slips' },
  { band: 'warn', min: 46, label: 'Recognisable but off' },
  { band: 'bad', min: -Infinity, label: 'Not the design' },
];

export function bandOf(score: number | null | undefined): Band {
  const s = score ?? 0;
  return (BANDS.find((b) => s >= b.min) ?? BANDS[BANDS.length - 1]).band;
}

export function bandLabel(score: number | null | undefined): string {
  const b = bandOf(score);
  return BANDS.find((x) => x.band === b)!.label;
}

/** Tailwind classes per band — kept here so they are statically discoverable. */
export const BAND_TEXT: Record<Band, string> = {
  good: 'text-good',
  ok: 'text-ok',
  warn: 'text-warn',
  bad: 'text-bad',
};
export const BAND_BG: Record<Band, string> = {
  good: 'bg-good',
  ok: 'bg-ok',
  warn: 'bg-warn',
  bad: 'bg-bad',
};
export const BAND_SOFT: Record<Band, string> = {
  good: 'bg-good/10 text-good border-good/30',
  ok: 'bg-ok/10 text-ok border-ok/30',
  warn: 'bg-warn/10 text-warn border-warn/30',
  bad: 'bg-bad/10 text-bad border-bad/30',
};

export function fmtScore(s: number | null | undefined, digits = 1): string {
  if (s == null || Number.isNaN(s)) return '—';
  return s.toFixed(digits);
}
