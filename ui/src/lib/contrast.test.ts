import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { blend, contrast, luminance, parseThemes, type Rgb } from './contrast';

const css = readFileSync(resolve(__dirname, '../styles/tokens.css'), 'utf8');
const themes = parseThemes(css);

describe('contrast maths', () => {
  it('matches the WCAG reference values', () => {
    expect(luminance([255, 255, 255])).toBeCloseTo(1, 5);
    expect(luminance([0, 0, 0])).toBe(0);
    expect(contrast([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 5);
    expect(contrast([118, 118, 118], [255, 255, 255])).toBeCloseTo(4.54, 2);
  });
  it('blends a translucent colour over a background', () => {
    expect(blend([255, 0, 0], [255, 255, 255], 0.1)).toEqual([255, 230, 230]);
  });
  it('reads both themes from tokens.css', () => {
    expect(Object.keys(themes.light)).toContain('ink');
    expect(Object.keys(themes.dark)).toContain('ink');
    expect(themes.light.bg).toEqual([244, 242, 238]); // Signal palette: warm paper
    expect(themes.light.accent).toEqual([229, 72, 15]); // signal orange
    expect(themes.dark.bg).toEqual([14, 13, 11]);
    expect(themes.dark.accent).toEqual([255, 106, 43]);
  });
});

/** [foreground, background, minimum ratio, optional: background is fg-tint at alpha over this surface] */
type Pair = { fg: string; bg: string; min: number; tint?: number; why: string };

const BODY = 4.5;
const LARGE_UI = 3;
const surfaces = ['bg', 'surface'];
const pairs: Pair[] = [
  ...['ink', 'ink-muted'].flatMap((fg) => [...surfaces, 'surface-2'].map((bg) => ({ fg, bg, min: BODY, why: 'body text' }))),
  ...surfaces.map((bg) => ({ fg: 'ink-faint', bg, min: BODY, why: 'meta text (11–12 px)' })),
  ...['good', 'ok', 'warn', 'bad', 'accent-strong'].flatMap((fg) => surfaces.map((bg) => ({ fg, bg, min: BODY, why: 'status / link text' }))),
  // chips: text-good on bg-good/10 over a card
  ...['good', 'ok', 'warn', 'bad'].map((fg) => ({ fg, bg: 'surface', tint: 0.1, min: BODY, why: 'status chip' })),
  { fg: 'accent-strong', bg: 'surface', tint: 0.1, min: BODY, why: '"Current best" chip' },
  { fg: 'accent-ink', bg: 'accent', min: BODY, why: 'primary button label' },
  // the orange accent is for fills, focus rings and large text only
  ...surfaces.map((bg) => ({ fg: 'accent', bg, min: LARGE_UI, why: 'fills, focus ring, large text' })),
  ...['good', 'bad', 'bp-mobile', 'bp-tablet', 'bp-desktop'].flatMap((fg) => surfaces.map((bg) => ({ fg, bg, min: LARGE_UI, why: 'chart marks / heat cells' }))),
];

describe.each(['light', 'dark'] as const)('WCAG contrast — %s theme', (name) => {
  const t = themes[name];
  it.each(pairs.map((p) => [`${p.fg} on ${p.tint ? `${p.fg}/${p.tint * 100} over ` : ''}${p.bg} ≥ ${p.min} (${p.why})`, p] as const))('%s', (_label, p) => {
    const fg = t[p.fg] as Rgb;
    const base = t[p.bg] as Rgb;
    expect(fg, `missing --c-${p.fg}`).toBeDefined();
    expect(base, `missing --c-${p.bg}`).toBeDefined();
    const bg = p.tint ? blend(fg, base, p.tint) : base;
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(p.min);
  });
});
