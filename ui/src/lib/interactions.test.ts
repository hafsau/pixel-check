import { describe, expect, it } from 'vitest';
import type { Attempt, RepeatSet, Variant } from './types';
import { buildChecklist, buildTimeline, compareWriters, summarizeRepeats, bestAttempt, verdictLine } from './interactions';

function attempt(p: Partial<Attempt> = {}): Attempt {
  return {
    attempt: 0,
    pass: true,
    infra: false,
    failures: [],
    state_scores: {},
    base_scores: {},
    checks: [],
    sections: {},
    code: null,
    sandbox: null,
    captures: {},
    ...p,
  };
}

function variant(p: Partial<Variant> = {}): Variant {
  return {
    key: 'v',
    writer: 'nemotron',
    source: 'sandbox',
    oracle: false,
    pass: true,
    best_attempt: 0,
    model_usd: 0,
    sandbox_usd: 0,
    usd: 0,
    seconds: 0,
    base_expected: {},
    sandbox: { runs: 0, vm_s: 0, wall_s: 0, usd: 0 },
    static: null,
    attempts: [attempt()],
    ...p,
  };
}

// The template's passing verdict on lambda's menu (real numbers from the Gate B export).
const PASSING = attempt({
  state_scores: { mobile: 86.53, tablet: 83.84 },
  base_scores: { mobile: 71.06, tablet: 76.53 },
  checks: [
    { bp: 'mobile', check: 'opens', score: 86.53 },
    { bp: 'mobile', check: 'closes', score: 71.06 },
    { bp: 'mobile', check: 'escape', score: 71.06 },
    { bp: 'mobile', check: 'keyboard', score: 86.53 },
    { bp: 'tablet', check: 'opens', score: 83.84 },
    { bp: 'tablet', check: 'closes', score: 76.53 },
    { bp: 'tablet', check: 'escape', score: 76.53 },
    { bp: 'tablet', check: 'keyboard', score: 83.84 },
  ],
});

// Nemotron's failing first draft (lambda, attempt 0): opens fails on both, Escape never ran.
const FAILING = attempt({
  pass: false,
  failures: [
    'mobile: after clicking the trigger the page does not match the state frame (score 54.2 < 75) — differing regions',
    "mobile: the trigger's open look does not match the design (100 % of its ink differs inside the render's trigger box [335, 33, 40, 34])",
    'mobile: clicking the trigger again does not restore the page (score 4.5 vs 70.3)',
    'tablet: after clicking the trigger the page does not match the state frame (score 30.1 < 75)',
    'these classes produce no CSS (invalid arbitrary value — Tailwind or the browser drops it), so they have no effect: bg-[#000000/0.9]',
  ],
  state_scores: { mobile: 54.17, tablet: 30.06 },
  base_scores: { mobile: 70.32, tablet: 75.99 },
  checks: [
    { bp: 'mobile', check: 'opens', score: 54.17 },
    { bp: 'mobile', check: 'closes', score: 4.52 },
    { bp: 'mobile', check: 'keyboard', score: 54.17 },
    { bp: 'tablet', check: 'opens', score: 30.06 },
    { bp: 'tablet', check: 'closes', score: 75.99 },
    { bp: 'tablet', check: 'keyboard', score: 30.06 },
  ],
});

const cell = (rows: ReturnType<typeof buildChecklist>['rows'], id: string, bp: string) => rows.find((r) => r.id === id)!.cells[bp]!;

describe('buildChecklist', () => {
  it('has one row per generated test, in a fixed order', () => {
    const { rows } = buildChecklist(PASSING, ['mobile', 'tablet']);
    expect(rows.map((r) => r.id)).toEqual(['base', 'opens', 'closes', 'escape', 'keyboard', 'aria', 'look']);
  });

  it('marks every check passed for a passing verdict, with the measured scores', () => {
    const { rows, general } = buildChecklist(PASSING, ['mobile', 'tablet']);
    for (const r of rows) for (const bp of ['mobile', 'tablet']) expect(cell(rows, r.id, bp).status).toBe('pass');
    expect(cell(rows, 'opens', 'mobile').score).toBe(86.53);
    expect(cell(rows, 'base', 'tablet').score).toBe(76.53);
    expect(cell(rows, 'escape', 'tablet').score).toBe(76.53);
    expect(general).toEqual([]);
  });

  it('attributes bp-prefixed failures to the right check and breakpoint', () => {
    const { rows } = buildChecklist(FAILING, ['mobile', 'tablet']);
    expect(cell(rows, 'opens', 'mobile').status).toBe('fail');
    expect(cell(rows, 'opens', 'mobile').reasons[0]).toMatch(/does not match the state frame/);
    expect(cell(rows, 'opens', 'tablet').status).toBe('fail');
    expect(cell(rows, 'look', 'mobile').status).toBe('fail');
    expect(cell(rows, 'look', 'tablet').status).toBe('pass');
    expect(cell(rows, 'closes', 'mobile').status).toBe('fail');
    expect(cell(rows, 'closes', 'tablet').status).toBe('pass');
    expect(cell(rows, 'base', 'mobile').status).toBe('pass');
  });

  it('strips the "<bp>: " prefix from reasons shown in a cell', () => {
    const { rows } = buildChecklist(FAILING, ['mobile', 'tablet']);
    expect(cell(rows, 'closes', 'mobile').reasons[0].startsWith('clicking the trigger again')).toBe(true);
  });

  it('reports Escape as not run when the state never opened (the harness skips it)', () => {
    const { rows } = buildChecklist(FAILING, ['mobile', 'tablet']);
    expect(cell(rows, 'escape', 'mobile').status).toBe('skipped');
  });

  it('fails keyboard when its score is under the threshold even without its own failure line', () => {
    const { rows } = buildChecklist(FAILING, ['mobile', 'tablet']);
    expect(cell(rows, 'keyboard', 'mobile').status).toBe('fail');
    expect(cell(rows, 'keyboard', 'mobile').score).toBe(54.17);
  });

  it('keeps failures that belong to no breakpoint as general failures', () => {
    const { general } = buildChecklist(FAILING, ['mobile', 'tablet']);
    expect(general).toHaveLength(1);
    expect(general[0]).toMatch(/produce no CSS/);
  });

  it('puts aria failures under aria, and duplicate ids under aria on every breakpoint', () => {
    const a = attempt({
      pass: false,
      checks: [{ bp: 'mobile', check: 'opens', score: 90 }, { bp: 'tablet', check: 'opens', score: 90 }],
      base_scores: { mobile: 70, tablet: 70 },
      failures: [
        'mobile: aria-expanded on the trigger is null after opening (want "true")',
        'id "menu" is used by more than one element — ids must be unique (aria-controls names one element; give the id to a single container)',
      ],
    });
    const { rows, general } = buildChecklist(a, ['mobile', 'tablet']);
    expect(cell(rows, 'aria', 'mobile').status).toBe('fail');
    expect(cell(rows, 'aria', 'mobile').reasons).toHaveLength(2);
    expect(cell(rows, 'aria', 'tablet').status).toBe('fail');
    expect(general).toEqual([]);
  });

  it('marks the base check failed when the closed page no longer matches the static page', () => {
    const a = attempt({
      pass: false,
      base_scores: { mobile: 40 },
      checks: [{ bp: 'mobile', check: 'opens', score: 90 }],
      failures: ['mobile: before any click the page does not match the design (score 40.0; the page without the interaction scores 70.3)'],
    });
    expect(cell(buildChecklist(a, ['mobile']).rows, 'base', 'mobile').status).toBe('fail');
  });

  it('marks everything not run for an infrastructure error, and keeps the error as general', () => {
    const a = attempt({ pass: false, infra: true, failures: ['infrastructure: sandbox timed out'] });
    const { rows, general } = buildChecklist(a, ['mobile']);
    expect(rows.every((r) => r.cells.mobile!.status === 'skipped')).toBe(true);
    expect(general).toEqual(['infrastructure: sandbox timed out']);
  });

  it('marks every check not run when the code did not build', () => {
    const a = attempt({ pass: false, failures: ['the code does not build: SyntaxError'] });
    const { rows, general } = buildChecklist(a, ['mobile']);
    expect(cell(rows, 'opens', 'mobile').status).toBe('skipped');
    expect(general).toEqual(['the code does not build: SyntaxError']);
  });

  it('does not confuse breakpoints whose names share a prefix with other text', () => {
    const a = attempt({ pass: false, checks: [{ bp: 'tablet', check: 'opens', score: 50 }], failures: ['tablet: after clicking the trigger the page does not match the state frame (score 50.0 < 75)'] });
    const { rows } = buildChecklist(a, ['mobile', 'tablet']);
    expect(cell(rows, 'opens', 'mobile').status).toBe('skipped');
    expect(cell(rows, 'opens', 'tablet').status).toBe('fail');
  });
});

describe('buildTimeline', () => {
  it('template: one attempt, no model, outcome pass', () => {
    const t = buildTimeline(variant({ writer: 'template', attempts: [PASSING] }));
    expect(t.map((s) => s.kind)).toEqual(['attempt', 'outcome']);
    expect(t[0]).toMatchObject({ kind: 'attempt', label: 'Attempt 1', pass: true });
    expect(t[1]).toMatchObject({ kind: 'outcome', pass: true, attempts: 1 });
  });

  it('nemotron: failed draft → revision fed with the failures → passing attempt', () => {
    const t = buildTimeline(variant({ pass: true, best_attempt: 1, attempts: [FAILING, { ...PASSING, attempt: 1 }] }));
    expect(t.map((s) => s.kind)).toEqual(['attempt', 'revise', 'attempt', 'outcome']);
    expect(t[0]).toMatchObject({ label: 'Attempt 1', pass: false, failureCount: 5 });
    expect(t[1]).toMatchObject({ kind: 'revise', by: 'Nemotron', fedBack: FAILING.failures });
    expect(t[2]).toMatchObject({ label: 'Attempt 2', pass: true });
    expect(t[3]).toMatchObject({ kind: 'outcome', pass: true, attempts: 2 });
  });

  it('reports the lowest state score of an attempt', () => {
    const t = buildTimeline(variant({ attempts: [FAILING] }));
    expect(t[0]).toMatchObject({ worstScore: 30.06, worstBp: 'tablet' });
  });

  it('an infrastructure error re-tests the same code: nothing is fed back to the writer', () => {
    const infra = attempt({ pass: false, infra: true, failures: ['infrastructure: timeout'] });
    const t = buildTimeline(variant({ attempts: [infra, { ...PASSING, attempt: 1 }] }));
    expect(t[1]).toMatchObject({ kind: 'revise', infra: true, fedBack: [] });
  });

  it('all attempts failing ends in a failed outcome without a trailing revision', () => {
    const t = buildTimeline(variant({ pass: false, attempts: [FAILING, { ...FAILING, attempt: 1 }, { ...FAILING, attempt: 2 }] }));
    expect(t.map((s) => s.kind)).toEqual(['attempt', 'revise', 'attempt', 'revise', 'attempt', 'outcome']);
    expect(t[t.length - 1]).toMatchObject({ pass: false, attempts: 3 });
  });

  it('a variant with no attempts yields an empty timeline', () => {
    expect(buildTimeline(variant({ attempts: [] }))).toEqual([]);
  });
});

describe('bestAttempt', () => {
  it('uses best_attempt when valid, else the last attempt', () => {
    const v = variant({ best_attempt: 0, attempts: [FAILING, PASSING] });
    expect(bestAttempt(v)).toBe(FAILING);
    expect(bestAttempt(variant({ best_attempt: 7, attempts: [FAILING, PASSING] }))).toBe(PASSING);
    expect(bestAttempt(variant({ best_attempt: null, attempts: [] }))).toBeNull();
  });
});

describe('summarizeRepeats', () => {
  const reps: RepeatSet[] = [
    {
      label: 'Gate B ablation',
      writer: 'nemotron',
      source: 'sandbox',
      runs: [
        { name: 'a', pass: false, best_attempt: 0, attempts: 3, first_pass_attempt: null, usd: 0.0807, model_usd: 0.0069, sandbox_usd: 0.0738, seconds: 47.1, matches_variant: null, attempt_scores: [] },
        { name: 'b', pass: true, best_attempt: 1, attempts: 2, first_pass_attempt: 1, usd: 0.0795, model_usd: 0.0073, sandbox_usd: 0.0722, seconds: 47.1, matches_variant: 'v', attempt_scores: [] },
      ],
    },
  ];
  it('counts passes, first-try passes and mean cost / time', () => {
    const [s] = summarizeRepeats(reps);
    expect(s).toMatchObject({ label: 'Gate B ablation', writer: 'nemotron', runs: 2, passed: 1, firstTry: 0 });
    expect(s.meanUsd).toBeCloseTo(0.0801, 4);
    expect(s.meanSeconds).toBeCloseTo(47.1, 3);
    expect(s.attemptsToPass).toEqual([2]);
  });
  it('handles missing costs', () => {
    const [s] = summarizeRepeats([{ label: 'x', writer: 'template', source: 'sandbox', runs: [{ ...reps[0].runs[1], usd: null, seconds: null }] }]);
    expect(s.meanUsd).toBeNull();
    expect(s.meanSeconds).toBeNull();
  });
});

describe('compareWriters', () => {
  it('pairs template and Nemotron and computes per-bp state-score differences of their best attempts', () => {
    const tpl = variant({ key: 't', writer: 'template', attempts: [PASSING] });
    const nem = variant({ key: 'n', writer: 'nemotron', pass: false, best_attempt: 0, attempts: [FAILING] });
    const c = compareWriters([tpl, nem]);
    expect(c.template?.key).toBe('t');
    expect(c.nemotron?.key).toBe('n');
    expect(c.delta.mobile).toBeCloseTo(54.17 - 86.53, 2);
    expect(c.delta.tablet).toBeCloseTo(30.06 - 83.84, 2);
  });
  it('returns no deltas when only one writer exists', () => {
    const c = compareWriters([variant({ writer: 'template' })]);
    expect(c.nemotron).toBeNull();
    expect(c.delta).toEqual({});
  });
});

describe('verdictLine', () => {
  const tpl = (scores: Record<string, number>, pass = true) => variant({ key: 't', writer: 'template', pass, attempts: [attempt({ pass, state_scores: scores })] });
  const nem = (scores: Record<string, number>, pass = true, n = 1) =>
    variant({ key: 'n', writer: 'nemotron', pass, best_attempt: 0, attempts: Array.from({ length: n }, (_, i) => attempt({ attempt: i, pass, state_scores: scores })) });
  it('says which writer scores higher when both pass', () => {
    expect(verdictLine([tpl({ mobile: 88.1, tablet: 87.1 }), nem({ mobile: 81.2, tablet: 87.1 })])).toBe('Both pass; the template scores up to 6.9 points higher.');
    expect(verdictLine([tpl({ mobile: 80 }), nem({ mobile: 82.5 })])).toBe('Both pass; Nemotron scores up to 2.5 points higher.');
  });
  it('calls identical scores identical', () => {
    expect(verdictLine([tpl({ mobile: 96.4 }), nem({ mobile: 96.4 })])).toBe('Both pass with identical state scores.');
  });
  it('reports mixed differences honestly', () => {
    expect(verdictLine([tpl({ mobile: 80, tablet: 90 }), nem({ mobile: 83, tablet: 88 })])).toBe('Both pass; state scores differ by up to 3.0 points, in both directions.');
  });
  it('names the failing writer', () => {
    expect(verdictLine([tpl({ mobile: 87 }), nem({ mobile: 54 }, false, 3)])).toBe('The template passes; Nemotron fails in this run after 3 attempts.');
    expect(verdictLine([tpl({ mobile: 50 }, false), nem({ mobile: 80 })])).toBe('Nemotron passes; the template fails.');
  });
  it('returns null without both writers', () => {
    expect(verdictLine([tpl({ mobile: 80 })])).toBeNull();
  });
});
