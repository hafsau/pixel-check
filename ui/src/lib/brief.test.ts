import { describe, expect, it } from 'vitest';
import { briefFooter, parseBrief, pasteText } from './brief';
import { parseCheck, checkStages } from './check';
import { checkLabel, parseDiagnostics } from './diagnostics';

// Oct 20: Nemotron writes what to do next from the check's facts; a verifier outside the model drops unbacked claims.
const RAW = {
  source: 'nemotron',
  model: 'nvidia/nemotron-3-super-120b-a12b',
  intro: 'Please update this page so it matches my design frames at every screen size:',
  summary: [{ text: 'Phones drift about 20% tighter.', facts: ['F3'] }],
  fix: [
    { text: 'Use the Lato font everywhere instead of Roboto.', facts: ['F1'] },
    { text: 'On mobile, make the text about 12% larger.', facts: ['F2', 'F9'] },
  ],
  dropped: 2,
  facts: [
    { id: 'F1', bp: null, kind: 'font', text: 'The build uses the Roboto font; the design uses Lato.', nums: [] },
    { id: 'F2', bp: 'mobile', kind: 'text_size', text: 'On mobile, text is about 11% smaller than in the design.', nums: [11, 12] },
    { id: 'F3', bp: 'mobile', kind: 'drift', text: 'On mobile, vertical spacing is about 20% tighter.', nums: [20] },
  ],
};

describe('parseBrief', () => {
  it('keeps the brief and links each item to its facts (unknown ids dropped from the links)', () => {
    const b = parseBrief(RAW)!;
    expect(b.source).toBe('nemotron');
    expect(b.fix[1].facts.map((f) => f.id)).toEqual(['F2']);
    expect(b.summary[0].facts[0].text).toContain('20% tighter');
    expect(b.dropped).toBe(2);
  });

  it('is null for junk and old bundles; read from check.json', () => {
    expect(parseBrief(null)).toBeNull();
    expect(parseBrief({ source: 'weird' })).toBeNull();
    expect(parseCheck({ type: 'check', report: {}, brief: RAW }).brief?.fix).toHaveLength(2);
    expect(parseCheck({ type: 'check', report: {} }).brief).toBeNull();
  });
});

describe('notes', () => {
  it('platform-badge notes are kept apart and never pasted into the AI builder', () => {
    const b = parseBrief({ ...RAW, notes: [{ text: 'On mobile, the "Edit with Lovable" badge covers "Weekly Activity". It is the platform\'s badge.', facts: ['F1'] }] })!;
    expect(b.notes).toHaveLength(1);
    expect(pasteText(b)).not.toContain('badge');
    expect(parseBrief(RAW)!.notes).toEqual([]);
  });
});

describe('pasteText', () => {
  it('is the intro then one line per instruction, ready for an AI builder', () => {
    expect(pasteText(parseBrief(RAW)!)).toBe(
      'Please update this page so it matches my design frames at every screen size:\n- Use the Lato font everywhere instead of Roboto.\n- On mobile, make the text about 12% larger.',
    );
  });
});

describe('added lines and dropped claims', () => {
  it('reads how many lines came from the measurements and why each claim was dropped', () => {
    const b = parseBrief({ ...RAW, added: 2, dropped_items: [{ text: 'Increase the font size by about 12%.', why: 'does not say which size it applies to' }, { nope: 1 }] })!;
    expect(b.added).toBe(2);
    expect(b.droppedItems).toEqual([{ text: 'Increase the font size by about 12%.', why: 'does not say which size it applies to' }]);
    expect(briefFooter(b)).toBe(
      'Written by NVIDIA Nemotron 3 Super from 3 measured facts; 2 lines added from the measurements where its own were dropped or missing. A check outside the model dropped 2 claims the measurements did not back.',
    );
  });
});

describe('briefFooter', () => {
  it('says who wrote it and what the verifier dropped', () => {
    expect(briefFooter(parseBrief(RAW)!)).toBe('Written by NVIDIA Nemotron 3 Super from 3 measured facts. A check outside the model dropped 2 claims the measurements did not back.');
    expect(briefFooter(parseBrief({ ...RAW, dropped: 0 })!)).toBe('Written by NVIDIA Nemotron 3 Super from 3 measured facts. Every claim is backed by a measurement.');
    expect(briefFooter(parseBrief({ ...RAW, source: 'template', dropped: 1 })!)).toBe('Written from the 3 measured facts (Nemotron was unavailable or none of its claims could be backed).');
    expect(briefFooter(parseBrief({ ...RAW, source: 'none', fix: [], summary: [], facts: [] })!)).toBe('Nothing to fix: no differences worth acting on.');
  });
});

describe('progress', () => {
  it('shows the fix brief as the last stage of a check and an audit', () => {
    const url = checkStages({ state: 'running', stages: [], source: { url: 'https://x.dev' } });
    expect(url.at(-1)).toMatchObject({ id: 'brief', label: 'Writing the fix brief (Nemotron)' });
    const audit = checkStages({ state: 'running', stages: [], source: { url: 'https://x.dev' }, audit: true });
    expect(audit.at(-1)?.id).toBe('brief');
  });
});

describe('checkLabel (drift-aware)', () => {
  const diag = (scale: number, statuses: string[] = ['moved']) =>
    parseDiagnostics({ mobile: { text: statuses.map((s) => ({ text: 'x', status: s })), drift: { bands: [{ y0: 0, y1: 100, dy: -150 }], scale } } }).mobile;
  it('says "Same layout, drifting" when spacing drifts ≥ 5% and everything is in the build', () => {
    expect(checkLabel(38.5, diag(0.803))).toBe('Same layout, drifting');
    expect(checkLabel(38.5, diag(1.06, []))).toBe('Same layout, drifting');
  });
  it('keeps the band label otherwise', () => {
    expect(checkLabel(38.5, diag(0.803, ['moved', 'missing']))).toBe('Not the design');
    expect(checkLabel(38.5, diag(1.01))).toBe('Not the design');
    expect(checkLabel(38.5, undefined)).toBe('Not the design');
    expect(checkLabel(95, diag(0.9))).toBe('Visually the same');
    expect(checkLabel(80, diag(0.9))).toBe('Same page, small slips');
  });
});
