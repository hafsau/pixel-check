import { describe, expect, it } from 'vitest';
import { driftLine, findings, lostRows, parseDiagnostics, textStatusLabel } from './diagnostics';
import { parseCheck } from './check';

// Oct 13 council (the Lovable build): explain the score beside it — never call moved text "missing".
const MOBILE = {
  text: [
    { text: '1h 20m', status: 'moved', dy: -148, dx: 0 },
    { text: 'minutes moved each day', status: 'below', dy: 70, dx: 0 },
    { text: 'weekly activity', status: 'unreadable' },
    { text: 'streak bonus', status: 'missing' },
  ],
  drift: { bands: [{ y0: 0, y1: 144, dy: -14 }, { y0: 144, y1: 290, dy: null, unsure: true }, { y0: 290, y1: 436, dy: -150 }], scale: 0.803 },
  lost: { layout: 42.3, color: 13.6, text: 5.6, offset: 0 },
  font: { design: 'Lato', build: 'Roboto' },
  text_size: 0.82,
};

describe('parseDiagnostics', () => {
  it('keeps well-formed sizes and drops junk', () => {
    const d = parseDiagnostics({ mobile: MOBILE, tablet: 'junk', desktop: { text: [{ text: 'x', status: 'weird' }, { status: 'moved' }], drift: { bands: 'no' }, lost: null } });
    expect(d.mobile?.text.map((t) => t.status)).toEqual(['moved', 'below', 'unreadable', 'missing']);
    expect(d.mobile?.drift?.scale).toBe(0.803);
    expect(d.mobile?.drift?.bands[1]).toEqual({ y0: 144, y1: 290, dy: null, unsure: true });
    expect(d.mobile?.textSize).toBe(0.82);
    expect(d.tablet).toBeUndefined();
    expect(d.desktop?.text).toEqual([]);
    expect(d.desktop?.drift).toBeNull();
    expect(parseDiagnostics(undefined)).toEqual({});
  });

  it('is read from check.json (older bundles have none)', () => {
    const base = { type: 'check', report: { breakpoints: {} } };
    expect(parseCheck({ ...base, diagnostics: { mobile: MOBILE } }).diagnostics.mobile?.font).toEqual({ design: 'Lato', build: 'Roboto' });
    expect(parseCheck(base).diagnostics).toEqual({});
  });
});

describe('textStatusLabel', () => {
  it('says what happened to the text, in plain words', () => {
    const d = parseDiagnostics({ mobile: MOBILE }).mobile!;
    expect(d.text.map(textStatusLabel)).toEqual([
      'in the build, 148 px higher than the design',
      'in the build, below the first screen',
      'in place, but covered or too faint to read',
      'not in the build',
    ]);
    expect(textStatusLabel({ text: 'a', status: 'moved', dy: 30 })).toBe('in the build, 30 px lower than the design');
    expect(textStatusLabel({ text: 'a', status: 'moved', dy: 2, dx: -120 })).toBe('in the build, 120 px left of the design');
    expect(textStatusLabel({ text: 'a', status: 'moved' })).toBe('in the build, elsewhere');
  });
});

describe('findings', () => {
  it('names the font, the text size and the drift', () => {
    expect(findings(parseDiagnostics({ mobile: MOBILE }).mobile!)).toEqual([
      'Font: Roboto (design: Lato)',
      'Text about 18% smaller than the design',
      'Spacing about 20% tighter: by the bottom of the screen the build sits 150 px higher',
    ]);
  });

  it('says nothing for small differences', () => {
    const d = parseDiagnostics({ desktop: { text: [], drift: { bands: [{ y0: 0, y1: 100, dy: 2 }, { y0: 100, y1: 200, dy: 4 }], scale: 1.008 }, lost: null, font: null, text_size: 0.96 } }).desktop!;
    expect(findings(d)).toEqual([]);
  });

  it('describes looser spacing on a taller build', () => {
    const d = parseDiagnostics({ desktop: { drift: { bands: [{ y0: 0, y1: 196, dy: 6 }, { y0: 980, y1: 1176, dy: 36 }], scale: 1.027 } } }).desktop!;
    expect(findings(d)).toEqual(['Spacing about 3% looser: by the bottom of the screen the build sits 36 px lower']);
  });
});

describe('lostRows', () => {
  it('lists factors that cost at least half a point, biggest first, as whole points', () => {
    expect(lostRows({ layout: 42.3, color: 13.6, text: 5.6, offset: 0.2 })).toEqual([
      { key: 'layout', label: 'Layout and edges', points: 42 },
      { key: 'color', label: 'Colour', points: 14 },
      { key: 'text', label: 'Text', points: 6 },
    ]);
    expect(lostRows(null)).toEqual([]);
  });
});

describe('driftLine', () => {
  it('reads the band offsets top to bottom, unsure bands as a question mark', () => {
    const d = parseDiagnostics({ mobile: MOBILE }).mobile!;
    expect(driftLine(d.drift)).toBe('−14 · ? · −150 px');
    expect(driftLine(null)).toBeNull();
  });
});
