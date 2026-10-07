import { describe, expect, it } from 'vitest';
import {
  CHECK_WIDTHS,
  MAX_CODE_CHARS,
  boxPct,
  checkBundleUrl,
  checkCells,
  checkFields,
  checkFormData,
  checkMissing,
  checkReady,
  checkStages,
  checkSummary,
  codeCounter,
  hurtList,
  missingBoxes,
  parseCheck,
  widthReasons,
  validateCode,
  type CheckDraft,
} from './check';

// ------------------------------------------------------------------------------------------------ fixtures

const fullReport = {
  mode: 'check',
  match: 86.97,
  mean: 91.34,
  worst: 'desktop',
  breakpoints: {
    mobile: {
      score: 94.16,
      components: { structure: 0.98, layout: 0.96, color: 0.98, content_color: 0.95, bg_match: 1.0 },
      missing_text: ['Start'],
      offset_px: [0, -2],
      regions: [{ kind: 'color', box: [240, 672, 16, 32], area: 512 }],
    },
    tablet: { score: 92.9, components: { structure: 0.91, layout: 0.97, color: 0.99 }, missing_text: [], offset_px: [0, 0] },
    desktop: { score: 86.97, components: { structure: 0.88, layout: 0.72, color: 0.93 }, missing_text: ['Pricing', 'Sign up'] },
  },
  fluidity: {
    pass: false,
    fails: [360, 'mobile'],
    widths: {
      '360': { overflow: 220, overlaps: 0, centre_drift: 0.03, max_gap: 112, bg_covers: true, ok: false },
      '375': { overflow: 0, overlaps: 3, centre_drift: 0.01, max_gap: 80, bg_covers: true, ok: false },
      '500': { overflow: 0, overlaps: 0, centre_drift: 0.08, max_gap: 80, bg_covers: true, ok: false },
      '1024': { overflow: 0, overlaps: 0, centre_drift: 0.0, max_gap: 80, bg_covers: true, ok: true },
      '1600': { overflow: 0, overlaps: 0, centre_drift: 0.0, max_gap: 80, bg_covers: false, ok: false },
      mobile: { overflow: 220, max_gap: 112, bg_covers: true },
      tablet: { overflow: 0, max_gap: 60, bg_covers: true },
      desktop: { overflow: 0, max_gap: 60, bg_covers: true },
    },
  },
  runtime_errors: [],
};

const fullBundle = {
  type: 'check',
  id: '20261006-101010-abcdef',
  source: { url: 'https://example.com/' },
  design: { mobile: 'design/mobile.webp', tablet: 'design/tablet.webp', desktop: 'design/desktop.webp' },
  build: { mobile: 'build/mobile.webp', tablet: 'build/tablet.webp', desktop: 'build/desktop.webp' },
  design_texts: { mobile: [{ text: 'Start', box: [20, 700, 80, 24] }], desktop: [{ text: 'Pricing', box: [900, 20, 60, 18] }] },
  usd: 0.003,
  report: fullReport,
};

const draft = (over: Partial<CheckDraft> = {}): CheckDraft => ({
  frames: { mobile: 'ok', tablet: 'ok', desktop: 'ok' },
  source: 'url',
  url: 'https://example.com/',
  code: '',
  owns: true,
  passcode: 'secret',
  ...over,
});

// ------------------------------------------------------------------------------------------------ request

describe('validateCode', () => {
  it('asks for code when empty or whitespace', () => {
    expect(validateCode('')).toBe('Paste your App.jsx.');
    expect(validateCode('   \n ')).toBe('Paste your App.jsx.');
  });
  it('accepts code up to the limit and refuses one character more', () => {
    expect(validateCode('x'.repeat(MAX_CODE_CHARS))).toBeNull();
    expect(validateCode('x'.repeat(MAX_CODE_CHARS + 1))).toBe('App.jsx is over 300,000 characters.');
  });
  it('uses the server limit', () => {
    expect(MAX_CODE_CHARS).toBe(300_000);
  });
});

describe('codeCounter', () => {
  it('is quiet far from the limit', () => {
    expect(codeCounter(1200)).toEqual({ label: '1,200 / 300,000', near: false, over: false });
  });
  it('warns from 90 % of the limit and flags over-limit', () => {
    expect(codeCounter(270_000).near).toBe(true);
    expect(codeCounter(269_999).near).toBe(false);
    expect(codeCounter(300_000)).toEqual({ label: '300,000 / 300,000', near: true, over: false });
    expect(codeCounter(300_001).over).toBe(true);
  });
});

describe('checkMissing / checkReady', () => {
  it('is ready with three frames, a valid URL, ownership and a passcode', () => {
    expect(checkMissing(draft())).toEqual([]);
    expect(checkReady(draft())).toBe(true);
  });
  it('lists every missing frame by size', () => {
    expect(checkMissing(draft({ frames: { mobile: 'ok', tablet: 'error', desktop: 'empty' } }))).toEqual(['a valid tablet frame', 'a valid desktop frame']);
  });
  it('needs a valid public URL in URL mode, ignoring the code box', () => {
    expect(checkMissing(draft({ url: 'http://localhost:3000', code: 'export default 1' }))).toEqual(['a valid build address']);
    expect(checkMissing(draft({ url: '' }))).toEqual(['a valid build address']);
  });
  it('needs code within the limit in code mode, ignoring the URL box', () => {
    expect(checkMissing(draft({ source: 'code', url: 'not a url', code: '' }))).toEqual(['your App.jsx']);
    expect(checkMissing(draft({ source: 'code', code: 'x'.repeat(MAX_CODE_CHARS + 1) }))).toEqual(['an App.jsx under 300,000 characters']);
    expect(checkReady(draft({ source: 'code', url: '', code: 'export default function App(){return null}' }))).toBe(true);
  });
  it('needs the ownership confirmation and a non-blank passcode', () => {
    expect(checkMissing(draft({ owns: false, passcode: '  ' }))).toEqual(['the ownership confirmation', 'the passcode']);
  });
});

describe('checkFields — exactly one of url / code is sent', () => {
  it('sends only the trimmed URL in URL mode', () => {
    expect(checkFields('url', '  https://example.com/a  ', 'some code')).toEqual({ url: 'https://example.com/a' });
  });
  it('sends only the code (untrimmed) in code mode', () => {
    expect(checkFields('code', 'https://example.com', ' code\n')).toEqual({ code: ' code\n' });
  });
});

describe('checkFormData', () => {
  const blob = () => new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' });
  it('carries three frames, the one active source, owns=true and the passcode', () => {
    const fd = checkFormData({ mobile: blob(), tablet: blob(), desktop: blob() }, draft({ code: 'ignored' }));
    expect([...fd.keys()].sort()).toEqual(['desktop', 'mobile', 'owns', 'passcode', 'tablet', 'url']);
    expect(fd.get('url')).toBe('https://example.com/');
    expect(fd.get('owns')).toBe('true');
    expect(fd.get('passcode')).toBe('secret');
    expect((fd.get('mobile') as File).name).toBe('mobile.png');
  });
  it('sends code and no url in code mode; owns=false when unchecked', () => {
    const fd = checkFormData({ mobile: blob(), tablet: blob(), desktop: blob() }, draft({ source: 'code', code: 'abc', owns: false }));
    expect(fd.has('url')).toBe(false);
    expect(fd.get('code')).toBe('abc');
    expect(fd.get('owns')).toBe('false');
  });
});

// ------------------------------------------------------------------------------------------------ parsing

describe('parseCheck', () => {
  it('normalises a full bundle', () => {
    const c = parseCheck(fullBundle);
    expect(c.id).toBe('20261006-101010-abcdef');
    expect(c.source).toEqual({ url: 'https://example.com/' });
    expect(c.design.mobile).toBe('design/mobile.webp');
    expect(c.build.desktop).toBe('build/desktop.webp');
    expect(c.usd).toBe(0.003);
    expect(c.report.match).toBe(86.97);
    expect(c.report.worst).toBe('desktop');
    expect(c.report.perBp).toEqual({ mobile: 94.16, tablet: 92.9, desktop: 86.97 });
    expect(c.report.bps.mobile?.missingText).toEqual(['Start']);
    expect(c.report.bps.mobile?.offset).toEqual([0, -2]);
    expect(c.report.bps.mobile?.regions).toEqual([{ kind: 'color', box: [240, 672, 16, 32], area: 512 }]);
    expect(c.report.bps.tablet?.regions).toEqual([]);
    expect(c.report.bps.desktop?.components.layout).toBe(0.72);
    expect(c.report.fluidity.pass).toBe(false);
    expect(c.report.fluidity.fails).toEqual(['360', 'mobile']);
    expect(c.report.fluidity.widths['360']).toEqual({ overflow: 220, overlaps: 0, centreDrift: 0.03, maxGap: 112, bgCovers: true, ok: false });
    expect(c.report.fluidity.widths.mobile).toEqual({ overflow: 220, overlaps: null, centreDrift: null, maxGap: 112, bgCovers: true, ok: null });
    expect(c.designTexts.mobile).toEqual([{ text: 'Start', box: [20, 700, 80, 24] }]);
    expect(c.report.runtimeErrors).toEqual([]);
  });

  it('survives an empty object and nulls everywhere', () => {
    const c = parseCheck({ type: 'check', report: { match: null, breakpoints: { mobile: { score: null, components: null, missing_text: null } }, fluidity: null } });
    expect(c.report.match).toBeNull();
    expect(c.report.perBp).toEqual({ mobile: null, tablet: null, desktop: null });
    expect(c.report.worst).toBeNull();
    expect(c.report.bps.mobile?.components).toEqual({ structure: null, layout: null, color: null, content_color: null, bg_match: null });
    expect(c.report.bps.mobile?.missingText).toEqual([]);
    expect(c.report.fluidity).toEqual({ pass: null, fails: [], widths: {} });
    expect(c.design).toEqual({});
    expect(c.usd).toBeNull();
    expect(parseCheck({}).report.perBp.mobile).toBeNull();
  });

  it('drops wrong types: non-numeric scores, unsafe image paths, bad boxes, non-string texts', () => {
    const c = parseCheck({
      type: 'check',
      design: { mobile: 'design/mobile.webp', tablet: 42, desktop: '../../etc/passwd', watch: 'x.webp' },
      design_texts: { mobile: [{ text: 'A', box: [1, 2, 3] }, { text: 7, box: [1, 2, 3, 4] }, { text: 'B', box: [1, 2, 3, 4] }] },
      report: {
        match: '90',
        worst: 'watch',
        breakpoints: { mobile: { score: NaN, missing_text: ['ok', 3, ''], regions: [{ kind: 'x', box: 'no' }, { box: [1, 2, 3, 4] }] } },
        fluidity: { pass: 'yes', fails: 'all', widths: { '360': 'bad', '375': { overflow: '12' } } },
        runtime_errors: ['TypeError: x', { message: 'y' }],
      },
    });
    expect(c.design).toEqual({ mobile: 'design/mobile.webp' });
    expect(c.designTexts.mobile).toEqual([{ text: 'B', box: [1, 2, 3, 4] }]);
    expect(c.report.match).toBeNull();
    expect(c.report.worst).toBeNull();
    expect(c.report.bps.mobile?.score).toBeNull();
    expect(c.report.bps.mobile?.missingText).toEqual(['ok']);
    expect(c.report.bps.mobile?.regions).toEqual([{ kind: 'region', box: [1, 2, 3, 4], area: null }]);
    expect(c.report.fluidity.pass).toBeNull();
    expect(c.report.fluidity.fails).toEqual([]);
    expect(Object.keys(c.report.fluidity.widths)).toEqual(['375']);
    expect(c.report.fluidity.widths['375'].overflow).toBeNull();
    expect(c.report.runtimeErrors).toEqual(['TypeError: x', 'y']);
  });

  it('derives the worst size from the scores when the report does not name it, and falls back to the status per_bp', () => {
    const c = parseCheck({ report: { breakpoints: { mobile: { score: 80 }, tablet: { score: 70 }, desktop: { score: 90 } } } });
    expect(c.report.worst).toBe('tablet');
    expect(c.report.match).toBe(70);
    const d = parseCheck({ report: {} }, { mobile: 50, tablet: 60, desktop: null });
    expect(d.report.perBp).toEqual({ mobile: 50, tablet: 60, desktop: null });
    expect(d.report.worst).toBe('mobile');
  });

  it('refuses something that is not a check bundle', () => {
    expect(() => parseCheck(null)).toThrow(/not a check result/i);
    expect(() => parseCheck('x')).toThrow(/not a check result/i);
    expect(() => parseCheck({ type: 'static' })).toThrow(/not a check result/i);
  });

  it('keeps a code source as { code: true }', () => {
    expect(parseCheck({ source: { code: true } }).source).toEqual({ code: true });
    expect(parseCheck({ source: 'x' }).source).toBeNull();
  });
});

// ------------------------------------------------------------------------------------------------ widths

describe('widthReasons', () => {
  const row = (o: Partial<Parameters<typeof widthReasons>[0]> = {}) => ({ overflow: 0, overlaps: 0, centreDrift: 0, maxGap: 50, bgCovers: true, ok: true, ...o });
  it('names each failure in plain words with its number', () => {
    expect(widthReasons(row({ overflow: 219.6, ok: false }))).toEqual([{ kind: 'scroll', text: '220 px sideways scroll' }]);
    expect(widthReasons(row({ overlaps: 3, ok: false }))).toEqual([{ kind: 'overlap', text: '3 overlapping texts' }]);
    expect(widthReasons(row({ overlaps: 1, ok: false }))).toEqual([{ kind: 'overlap', text: '1 overlapping text' }]);
    expect(widthReasons(row({ centreDrift: 0.08, ok: false }))).toEqual([{ kind: 'shift', text: 'content shifted 8 %' }]);
    expect(widthReasons(row({ bgCovers: false, ok: false }))).toEqual([{ kind: 'background', text: 'background ends early' }]);
  });
  it('lists several failures in order', () => {
    expect(widthReasons(row({ overflow: 30, overlaps: 2, ok: false })).map((r) => r.kind)).toEqual(['scroll', 'overlap']);
  });
  it('ignores a drift within the 5 % tolerance', () => {
    expect(widthReasons(row({ centreDrift: 0.05 }))).toEqual([]);
  });
  it('blames the empty gap when the row failed for no other visible reason', () => {
    expect(widthReasons(row({ maxGap: 1400, ok: false }), true)).toEqual([{ kind: 'gap', text: '1400 px empty gap' }]);
    expect(widthReasons(row({ maxGap: null, ok: false }), true)).toEqual([{ kind: 'other', text: 'check failed' }]);
  });
  it('returns nothing for a passing row', () => {
    expect(widthReasons(row())).toEqual([]);
  });
});

describe('checkCells', () => {
  const report = parseCheck(fullBundle).report;
  const cells = checkCells(report);

  it('covers 360 · 375 · 390 · 500 · 768 · 1024 · 1280 · 1600 in order', () => {
    expect(CHECK_WIDTHS).toEqual([360, 375, 390, 500, 768, 1024, 1280, 1600]);
    expect(cells.map((c) => c.width)).toEqual(CHECK_WIDTHS);
  });
  it('design sizes carry their score and size name', () => {
    const d = cells.filter((c) => c.kind === 'design');
    expect(d.map((c) => [c.width, c.bp, c.score])).toEqual([
      [390, 'mobile', 94.16],
      [768, 'tablet', 92.9],
      [1280, 'desktop', 86.97],
    ]);
  });
  it('marks failures with reasons; passes have none', () => {
    const at = (w: number) => cells.find((c) => c.width === w)!;
    expect(at(360)).toMatchObject({ kind: 'between', state: 'fail', detail: '220 px sideways scroll' });
    expect(at(375)).toMatchObject({ state: 'fail', detail: '3 overlapping texts' });
    expect(at(500)).toMatchObject({ state: 'fail', detail: 'content shifted 8 %' });
    expect(at(1024)).toMatchObject({ state: 'pass', reasons: [] });
    expect(at(1600)).toMatchObject({ state: 'fail', detail: 'background ends early' });
    expect(at(390)).toMatchObject({ kind: 'design', state: 'fail', detail: '220 px sideways scroll' });
    expect(at(768)).toMatchObject({ state: 'pass' });
  });
  it('a design size listed in fails without a visible reason fails on the gap', () => {
    const r = parseCheck({ report: { fluidity: { fails: ['tablet'], widths: { tablet: { overflow: 0, max_gap: 1900, bg_covers: true } } } } }).report;
    expect(checkCells(r).find((c) => c.width === 768)).toMatchObject({ state: 'fail', detail: '1900 px empty gap' });
  });
  it('unmeasured widths are pending, and design sizes still show their score', () => {
    const r = parseCheck({ report: { breakpoints: { mobile: { score: 70 } } } }).report;
    const c = checkCells(r);
    expect(c.every((x) => x.state === 'pending')).toBe(true);
    expect(c.find((x) => x.width === 390)?.score).toBe(70);
  });
  it('trusts fails when ok is missing', () => {
    const r = parseCheck({ report: { fluidity: { fails: [500], widths: { '500': { overflow: 0, overlaps: 0, centre_drift: 0.2 } } } } }).report;
    expect(checkCells(r).find((c) => c.width === 500)).toMatchObject({ state: 'fail', detail: 'content shifted 20 %' });
  });
});

// ------------------------------------------------------------------------------------------------ summary & hints

describe('checkSummary', () => {
  it('names the worst size and the first failing width with a short reason', () => {
    const r = parseCheck(fullBundle).report;
    expect(checkSummary(r)).toBe('Worst size 87.0 (desktop) · fails at 360 px: sideways scroll (+4 more)');
  });
  it('says it fits when every width passes', () => {
    const r = parseCheck({ report: { match: 64.2, worst: 'mobile', fluidity: { pass: true, fails: [], widths: { '360': { ok: true }, '1600': { ok: true } } } } }).report;
    expect(checkSummary(r)).toBe('Worst size 64.2 (mobile) · fits 360–1600 px');
  });
  it('handles a single failure and unknown scores', () => {
    const r = parseCheck({ report: { fluidity: { fails: [500], widths: { '500': { overlaps: 2, ok: false } } } } }).report;
    expect(checkSummary(r)).toBe('Worst size — · fails at 500 px: overlapping text');
  });
  it('omits the width part when nothing was measured', () => {
    expect(checkSummary(parseCheck({ report: { match: 50, worst: 'tablet' } }).report)).toBe('Worst size 50.0 (tablet)');
  });
});

describe('hurtList', () => {
  it('ranks structure / layout / colour by their lowest value across sizes, 1–3 items, below 95 %', () => {
    const h = hurtList(parseCheck(fullBundle).report);
    expect(h.map((x) => [x.key, x.value, x.bp])).toEqual([
      ['layout', 0.72, 'desktop'],
      ['structure', 0.88, 'desktop'],
      ['color', 0.93, 'desktop'],
    ]);
    expect(h[0].label).toBe('Layout');
    expect(h[0].hint).toMatch(/place/);
  });
  it('is empty when everything is close', () => {
    expect(hurtList(parseCheck({ report: { breakpoints: { mobile: { components: { structure: 0.99, layout: 0.97, color: 0.96 } } } } }).report)).toEqual([]);
  });
  it('falls back to content colour when colour is missing, and skips null components', () => {
    const h = hurtList(parseCheck({ report: { breakpoints: { tablet: { components: { structure: null, content_color: 0.6 } } } } }).report);
    expect(h).toEqual([expect.objectContaining({ key: 'color', value: 0.6, bp: 'tablet' })]);
  });
});

describe('missingBoxes', () => {
  const texts = [
    { text: 'Get  started', box: [10, 10, 100, 20] as [number, number, number, number] },
    { text: 'Pricing', box: [200, 10, 60, 20] as [number, number, number, number] },
    { text: 'Pricing', box: [200, 400, 60, 20] as [number, number, number, number] },
  ];
  it('finds design boxes for missing texts (case and spacing ignored), each box used once', () => {
    expect(missingBoxes(['get started', 'Pricing', 'pricing'], texts).map((b) => b.box)).toEqual([
      [10, 10, 100, 20],
      [200, 10, 60, 20],
      [200, 400, 60, 20],
    ]);
  });
  it('skips texts it cannot place', () => {
    expect(missingBoxes(['Nope'], texts)).toEqual([]);
    expect(missingBoxes(['x'], [])).toEqual([]);
  });
});

describe('boxPct', () => {
  it('turns a pixel box into percentages of the frame, clamped inside it', () => {
    const p = boxPct([39, 84.4, 39, 84.4], [390, 844]);
    for (const k of ['left', 'top', 'width', 'height'] as const) expect(p[k]).toBeCloseTo(10, 9);
    expect(boxPct([-10, 800, 500, 100], [390, 844])).toEqual({ left: 0, top: (800 / 844) * 100, width: 100, height: (44 / 844) * 100 });
  });
});

// ------------------------------------------------------------------------------------------------ progress

describe('checkStages', () => {
  it('URL checks: capture → read design → score', () => {
    const s = checkStages({ state: 'running', source: { url: 'https://a.com' }, stages: [{ stage: 'capture', t: 1 }, { stage: 'read design', t: 2 }] });
    expect(s.map((x) => [x.id, x.state])).toEqual([
      ['capture', 'done'],
      ['read design', 'active'],
      ['score', 'pending'],
    ]);
  });
  it('code checks: render → read design → score; done marks all done', () => {
    const s = checkStages({ state: 'done', source: { code: true }, stages: [] });
    expect(s.map((x) => [x.id, x.state])).toEqual([
      ['render', 'done'],
      ['read design', 'done'],
      ['score', 'done'],
    ]);
  });
  it('a failure marks the last reached stage failed', () => {
    const s = checkStages({ state: 'failed', source: { code: true }, stages: [{ stage: 'render', t: 1 }] });
    expect(s.map((x) => x.state)).toEqual(['failed', 'pending', 'pending']);
  });
});

describe('checkBundleUrl', () => {
  it('uses the API path the status gives', () => {
    expect(checkBundleUrl('https://api.x', 'id1', '/api/runs/id1/files/check.json')).toBe('https://api.x/api/runs/id1/files/check.json');
    expect(checkBundleUrl('', 'id1', '/api/runs/id1/files/check.json')).toBe('/api/runs/id1/files/check.json');
  });
  it('falls back to the run folder for anything else', () => {
    expect(checkBundleUrl('', 'id 1', 'https://evil.example/x.json')).toBe('/api/runs/id%201/files/check.json');
    expect(checkBundleUrl('', 'id1', null)).toBe('/api/runs/id1/files/check.json');
    expect(checkBundleUrl('', 'id1', '/api/runs/../../x')).toBe('/api/runs/id1/files/check.json');
  });
});
