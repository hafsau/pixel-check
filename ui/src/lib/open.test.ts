import { describe, expect, it } from 'vitest';
import { checkMissing, type CheckDraft } from './check';
import { framesReady, urlReady } from './live';
import { passcodeNeeded, showPasscodeField } from './liveApi';

// Open live mode (Hafsa, Oct 21): judges type nothing; the server says so in /api/health.
const ok = { mobile: 'ok', tablet: 'ok', desktop: 'ok' } as const;
const draft: CheckDraft = { frames: { ...ok }, source: 'url', url: 'https://build.example.com', code: '', owns: true, passcode: '' };

describe('open live mode', () => {
  it('the passcode is needed unless the server says it is not (older servers say nothing)', () => {
    expect(passcodeNeeded({ live: true, runs_left_today: 5, runs_left_total: 40, passcode: false })).toBe(false);
    expect(passcodeNeeded({ live: true, runs_left_today: 5, runs_left_total: 40, passcode: true })).toBe(true);
    expect(passcodeNeeded({ live: true, runs_left_today: 5, runs_left_total: 40 })).toBe(true);
    expect(passcodeNeeded(null)).toBe(true);
  });

  it('the check form does not ask for a passcode in open mode', () => {
    expect(checkMissing(draft)).toEqual(['the passcode']);
    expect(checkMissing({ ...draft, noPasscode: true })).toEqual([]);
  });

  it('rebuild forms are ready without a passcode in open mode', () => {
    expect(framesReady(ok, '')).toBe(false);
    expect(framesReady(ok, '', false)).toBe(true);
    expect(urlReady('https://example.com', true, '')).toBe(false);
    expect(urlReady('https://example.com', true, '', false)).toBe(true);
  });
});

describe('the passcode field', () => {
  it('appears only once the server has said it wants one (never while waking, never in open mode)', () => {
    expect(showPasscodeField(null)).toBe(false);
    expect(showPasscodeField({ live: true, runs_left_today: 5, runs_left_total: 40, passcode: false })).toBe(false);
    expect(showPasscodeField({ live: true, runs_left_today: 5, runs_left_total: 40, passcode: true })).toBe(true);
    expect(showPasscodeField({ live: true, runs_left_today: 5, runs_left_total: 40 })).toBe(true);
  });
});
