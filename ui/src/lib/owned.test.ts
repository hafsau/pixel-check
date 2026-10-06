import { describe, expect, it } from 'vitest';
import { ASSET_RE, codeSources, combineCode, normalizeRun, parseDisplay, parseReal, threeUp } from './owned';
import type { Run } from './types';

const H = 'a'.repeat(64);
const H2 = '0123456789abcdef'.repeat(4);

function run(extra: Record<string, unknown> = {}): Run {
  return {
    id: 'r1',
    title: 'T',
    created: 0,
    models: {},
    breakpoints: [
      { name: 'mobile', width: 390, height: 844 },
      { name: 'tablet', width: 768, height: 1024 },
      { name: 'desktop', width: 1280, height: 800 },
    ],
    design: { mobile: 'design/mobile.png', tablet: 'design/tablet.png', desktop: 'design/desktop.png' },
    result: { stop_reason: null, match: 90, per_bp: {}, best: 'c2', spend_usd: 0, wall_s: 0, history: [] },
    rounds: [],
    candidates: [
      { id: 'c1', parent: null, round: 0, strategy: null, match: 1, mean: 1, per_bp: {}, worst: null, disqualified: false, reason: null, checkpoint: 'x', sandbox_cost: 0, renders: { mobile: 'renders/c1/mobile.png' }, code: 'code/c1.jsx' },
      { id: 'c2', parent: 'c1', round: 1, strategy: null, match: 2, mean: 2, per_bp: {}, worst: null, disqualified: false, reason: null, checkpoint: 'y', sandbox_cost: 0, renders: { mobile: 'renders/c2/mobile.png', desktop: 'renders/c2/desktop.png' }, code: 'code/c2.jsx' },
    ],
    critiques: [],
    edits: [],
    calls: [],
    ...extra,
  } as Run;
}

describe('ASSET_RE', () => {
  it('accepts assets/<64 hex>.<image ext> only', () => {
    for (const ext of ['png', 'jpg', 'gif', 'webp', 'avif', 'svg']) expect(ASSET_RE.test(`assets/${H}.${ext}`)).toBe(true);
    expect(ASSET_RE.test(`assets/${H.slice(1)}.png`)).toBe(false); // 63 hex
    expect(ASSET_RE.test(`assets/${H}a.png`)).toBe(false); // 65 hex
    expect(ASSET_RE.test(`assets/${H.toUpperCase()}.png`)).toBe(false);
    expect(ASSET_RE.test(`assets/${H}.jpeg`)).toBe(false);
    expect(ASSET_RE.test(`assets/${H}.html`)).toBe(false);
    expect(ASSET_RE.test(`/assets/${H}.png`)).toBe(false);
    expect(ASSET_RE.test(`../assets/${H}.png`)).toBe(false);
    expect(ASSET_RE.test(`assets/${H}.png\n`)).toBe(false);
    expect(ASSET_RE.test(`x/assets/${H}.png`)).toBe(false);
  });
});

describe('parseDisplay', () => {
  it('keeps a well-formed display block', () => {
    expect(parseDisplay({ code: 'display/App.jsx', assets: [`assets/${H}.png`, `assets/${H2}.svg`], images: 2, candidate: 'c2' })).toEqual({
      code: 'display/App.jsx',
      assets: [`assets/${H}.png`, `assets/${H2}.svg`],
      images: 2,
      candidate: 'c2',
    });
  });
  it('drops asset paths that do not match, and duplicates', () => {
    const d = parseDisplay({ code: 'display/App.jsx', assets: [`assets/${H}.png`, '../etc/passwd', `https://x.test/assets/${H}.png`, 42, null, `assets/${H}.png`, `assets/${H2}.exe`], images: 1, candidate: 'c2' });
    expect(d?.assets).toEqual([`assets/${H}.png`]);
  });
  it('is null when absent, null or malformed', () => {
    expect(parseDisplay(undefined)).toBeNull();
    expect(parseDisplay(null)).toBeNull();
    expect(parseDisplay('display/App.jsx')).toBeNull();
    expect(parseDisplay([])).toBeNull();
    expect(parseDisplay({ assets: [] })).toBeNull();
    expect(parseDisplay({ code: 5 })).toBeNull();
  });
  it('rejects code paths outside display/*.jsx', () => {
    for (const code of ['../run.json', '/display/App.jsx', 'https://x.test/App.jsx', 'display/../App.jsx', 'display/sub/App.jsx', 'code/c2.jsx', 'display/App.js', ''])
      expect(parseDisplay({ code, assets: [] })).toBeNull();
  });
  it('defaults the optional fields', () => {
    expect(parseDisplay({ code: 'display/App.jsx' })).toEqual({ code: 'display/App.jsx', assets: [], images: 0, candidate: null });
    expect(parseDisplay({ code: 'display/App.jsx', assets: 'x', images: -3, candidate: 7 })).toEqual({ code: 'display/App.jsx', assets: [], images: 0, candidate: null });
    expect(parseDisplay({ code: 'display/App.jsx', images: 2.7 })?.images).toBe(2);
  });
});

describe('parseReal', () => {
  it('keeps real/<bp>.<image> paths per breakpoint', () => {
    expect(parseReal({ mobile: 'real/mobile.webp', tablet: 'real/tablet.webp', desktop: 'real/desktop.png' })).toEqual({ mobile: 'real/mobile.webp', tablet: 'real/tablet.webp', desktop: 'real/desktop.png' });
  });
  it('drops anything else', () => {
    expect(parseReal({ mobile: 'real/mobile.webp', tablet: '../x.webp', desktop: 'https://x.test/a.webp', wide: 3, huge: 'real/huge.html', 'bad key': 'real/x.webp' })).toEqual({ mobile: 'real/mobile.webp' });
  });
  it('is null when absent, null, malformed or empty after filtering', () => {
    expect(parseReal(undefined)).toBeNull();
    expect(parseReal(null)).toBeNull();
    expect(parseReal(['real/mobile.webp'])).toBeNull();
    expect(parseReal({})).toBeNull();
    expect(parseReal({ mobile: '/real/mobile.webp' })).toBeNull();
  });
});

describe('normalizeRun', () => {
  it('older bundles (fields absent) get display = real = null and are otherwise unchanged', () => {
    const r = run();
    const n = normalizeRun(r);
    expect(n.display).toBeNull();
    expect(n.real).toBeNull();
    const { display: _d, real: _r, ...rest } = n;
    expect(rest).toEqual(r);
  });
  it('explicit nulls stay null', () => {
    const n = normalizeRun(run({ display: null, real: null }));
    expect(n.display).toBeNull();
    expect(n.real).toBeNull();
  });
  it('sanitises the owned-site fields', () => {
    const n = normalizeRun(run({ display: { code: 'display/App.jsx', assets: [`assets/${H}.png`, 'evil'], images: 1, candidate: 'c2' }, real: { mobile: 'real/mobile.webp', tablet: 'nope' } }));
    expect(n.display?.assets).toEqual([`assets/${H}.png`]);
    expect(n.real).toEqual({ mobile: 'real/mobile.webp' });
  });
  it('does not mutate its input', () => {
    const r = run({ display: { code: 'display/App.jsx', assets: ['evil'] } });
    normalizeRun(r);
    expect((r as unknown as { display: { assets: string[] } }).display.assets).toEqual(['evil']);
  });
});

describe('codeSources', () => {
  it('scored = best candidate code; delivered = display.code', () => {
    expect(codeSources(normalizeRun(run({ display: { code: 'display/App.jsx' } })))).toEqual({ scored: 'code/c2.jsx', delivered: 'display/App.jsx' });
  });
  it('no display → delivered null (runs without the fields are unchanged)', () => {
    expect(codeSources(normalizeRun(run()))).toEqual({ scored: 'code/c2.jsx', delivered: null });
  });
  it('no best candidate code → scored null', () => {
    const r = run();
    r.result.best = 'missing';
    expect(codeSources(normalizeRun(r)).scored).toBeNull();
  });
});

describe('combineCode', () => {
  const ready = (data: string) => ({ status: 'ready' as const, data });
  it('loading while either is loading', () => {
    expect(combineCode({ status: 'loading' }, ready('d')).status).toBe('loading');
    expect(combineCode(ready('s'), { status: 'loading' }).status).toBe('loading');
  });
  it('scored error is an error', () => {
    expect(combineCode({ status: 'error', error: 'boom' }, ready('d'))).toEqual({ status: 'error', error: 'boom' });
  });
  it('delivered error or empty → fall back to scored only', () => {
    expect(combineCode(ready('s'), { status: 'error', error: 'x' })).toEqual({ status: 'ready', scored: 's', delivered: null });
    expect(combineCode(ready('s'), ready(''))).toEqual({ status: 'ready', scored: 's', delivered: null });
  });
  it('both ready', () => {
    expect(combineCode(ready('s'), ready('d'))).toEqual({ status: 'ready', scored: 's', delivered: 'd' });
  });
  it('empty scored → null', () => {
    expect(combineCode(ready(''), ready(''))).toEqual({ status: 'ready', scored: null, delivered: null });
  });
});

describe('threeUp', () => {
  const owned = normalizeRun(run({ real: { mobile: 'real/mobile.webp', desktop: 'real/desktop.webp' } }));
  it('real · design · best render for a breakpoint', () => {
    expect(threeUp(owned, 'mobile')).toEqual({ real: 'real/mobile.webp', design: 'design/mobile.png', rebuild: 'renders/c2/mobile.png' });
  });
  it('missing pieces are null', () => {
    expect(threeUp(owned, 'tablet')).toEqual({ real: null, design: 'design/tablet.png', rebuild: null });
  });
  it('null for runs without real screenshots', () => {
    expect(threeUp(normalizeRun(run()), 'mobile')).toBeNull();
  });
});
