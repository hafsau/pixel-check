// WCAG 2.x contrast maths + a reader for the RGB-channel tokens in src/styles/tokens.css (used by contrast.test.ts).

export type Rgb = [number, number, number];

/** Relative luminance (WCAG 2.x). */
export function luminance([r, g, b]: Rgb): number {
  const f = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

export function contrast(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** `fg` at `alpha` painted over an opaque `bg` (what `bg-good/10` looks like on a card). */
export function blend(fg: Rgb, bg: Rgb, alpha: number): Rgb {
  return fg.map((c, i) => Math.round(c * alpha + bg[i] * (1 - alpha))) as Rgb;
}

function channels(block: string): Record<string, Rgb> {
  const out: Record<string, Rgb> = {};
  for (const m of block.matchAll(/--c-([\w-]+):\s*(\d+)\s+(\d+)\s+(\d+)\s*;/g)) out[m[1]] = [Number(m[2]), Number(m[3]), Number(m[4])];
  return out;
}

/** Light = the first `:root {…}` block; dark = light overridden by `:root[data-theme='dark'] {…}`. */
export function parseThemes(css: string): { light: Record<string, Rgb>; dark: Record<string, Rgb> } {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const light = channels(clean.match(/:root\s*{([^}]*)}/)?.[1] ?? '');
  const dark = { ...light, ...channels(clean.match(/:root\[data-theme=['"]dark['"]\]\s*{([^}]*)}/)?.[1] ?? '') };
  return { light, dark };
}
