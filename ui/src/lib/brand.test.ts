import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const UI = resolve(__dirname, '../..');
const read = (p: string) => readFileSync(join(UI, p), 'utf8');

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    if (f === 'node_modules') return [];
    return statSync(p).isDirectory() ? walk(p) : /\.(tsx?|css|html)$/.test(f) ? [p] : [];
  });
}

describe('brand name: PixelCheck', () => {
  it('no user-facing "Pixel-Check" is left in the app', () => {
    const files = [...walk(join(UI, 'src')), join(UI, 'index.html')].filter((f) => !f.endsWith('brand.test.ts'));
    const hits = files.filter((f) => readFileSync(f, 'utf8').includes('Pixel-Check'));
    expect(hits).toEqual([]);
  });
  it('the page title and description say PixelCheck', () => {
    const html = read('index.html');
    expect(html).toMatch(/<title>PixelCheck[^<]*<\/title>/);
    expect(html).toMatch(/<meta name="description" content="PixelCheck/);
  });
});

describe('type: self-hosted Geist', () => {
  it('index.html loads no Google Fonts', () => {
    expect(read('index.html')).not.toMatch(/fonts\.(googleapis|gstatic)\.com/);
  });
  it('tokens define Geist Sans / Mono / Pixel', () => {
    const t = read('src/styles/tokens.css');
    expect(t).toMatch(/--font-sans:\s*'Geist'/);
    expect(t).toMatch(/--font-mono:\s*'Geist Mono'/);
    expect(t).toMatch(/--font-pixel:\s*'Geist Pixel'/);
  });
  it('previews keep Inter + IBM Plex Mono (the scored code fonts never change)', () => {
    const p = read('src/lib/previewDoc.ts');
    expect(p).toContain('family=Inter');
    expect(p).toContain('IBM+Plex+Mono');
    expect(p).not.toMatch(/Geist/);
  });
  it('every @font-face is latin-only woff2 with font-display: swap, and the total is ≤ 120 KB', () => {
    const css = read('src/styles/fonts.css');
    const faces = css.match(/@font-face\s*{[^}]*}/g) ?? [];
    expect(faces.length).toBeGreaterThanOrEqual(3);
    let total = 0;
    for (const f of faces) {
      expect(f).toMatch(/font-display:\s*swap/);
      const urls = [...f.matchAll(/url\(['"]?([^'")]+)['"]?\)/g)].map((m) => m[1]);
      expect(urls.length).toBe(1);
      expect(urls[0]).toMatch(/latin-[\w-]*\.woff2$/);
      expect(urls[0]).not.toMatch(/latin-ext/);
      const file = urls[0].startsWith('.') ? resolve(dirname(join(UI, 'src/styles/fonts.css')), urls[0]) : join(UI, 'node_modules', urls[0]);
      total += statSync(file).size;
    }
    expect(total).toBeLessThanOrEqual(120 * 1024);
  });
});

describe('logo: the Pixel mark is THE mark', () => {
  it('Pixel is the default variant and listed first on /brand', async () => {
    const { DEFAULT_MARK, MARK_VARIANTS } = await import('../components/Logo');
    expect(DEFAULT_MARK).toBe('pixel');
    expect(MARK_VARIANTS[0].key).toBe('pixel');
  });
  it('header and footer use the default mark (no variant override)', () => {
    expect(read('src/components/SiteHeader.tsx')).toMatch(/<Logo \/>/);
    expect(read('src/components/SiteFooter.tsx')).not.toMatch(/variant=/);
  });
  it('the favicon is the small Pixel mark: the same bold 8-bit cells', async () => {
    const { SMALL_CELLS } = await import('../components/Logo');
    const svg = read('public/favicon.svg');
    expect(svg).toContain('data-variant="pixel"');
    const rects = [...svg.matchAll(/<rect x="(\d+)" y="(\d+)" width="4" height="4"\/>/g)].map((m) => `${m[1]},${m[2]}`).sort();
    expect(rects).toEqual(SMALL_CELLS.map(([c, r]) => `${4 + c * 4},${6 + r * 4}`).sort());
  });
  it('the wordmark is Geist Pixel at 24 px (20 px on phones)', () => {
    const logo = read('src/components/Logo.tsx');
    expect(logo).toMatch(/pixel text-\[20px\][^"]*sm:text-\[24px\]/);
  });
});

describe('logo assets', () => {
  it('ships an SVG favicon with the new mark (no third-party captures)', () => {
    const svg = read('public/favicon.svg');
    expect(svg).toMatch(/^<svg[^>]+viewBox="0 0 32 32"/);
    expect(svg).toContain('data-mark="pixelcheck"');
    expect(svg).not.toMatch(/runs\//);
  });
});
