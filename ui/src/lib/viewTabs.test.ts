import { describe, expect, it } from 'vitest';
import { RUN_TABS, hashForTab, tabFromHash } from './viewTabs';
import { codeHref } from './bundle';
import type { IndexEntry } from './types';

describe('run view tabs ↔ URL hash', () => {
  it('Replay · Preview · Code, in that order', () => {
    expect(RUN_TABS.map((t) => t.label)).toEqual(['Replay', 'Preview', 'Code']);
  });
  it('maps hashes to tabs, defaulting to replay', () => {
    expect(tabFromHash('#code')).toBe('code');
    expect(tabFromHash('#preview')).toBe('preview');
    expect(tabFromHash('code')).toBe('code');
    expect(tabFromHash('')).toBe('replay');
    expect(tabFromHash('#replay')).toBe('replay');
    expect(tabFromHash('#runs')).toBe('replay');
    expect(tabFromHash('#CODE')).toBe('code');
  });
  it('maps tabs back to hashes (replay = no hash)', () => {
    expect(hashForTab('replay')).toBe('');
    expect(hashForTab('preview')).toBe('#preview');
    expect(hashForTab('code')).toBe('#code');
  });
  it('round-trips', () => {
    for (const t of RUN_TABS) expect(tabFromHash(hashForTab(t.key))).toBe(t.key);
  });
});

describe('"Code" links on cards', () => {
  const base = { title: 't', created: 1 };
  it('static runs open the run page on the Code tab', () => {
    expect(codeHref({ ...base, type: 'static', id: 'abl-plan-lambda-203138', match: 70, per_bp: {} } as IndexEntry)).toBe('/run/abl-plan-lambda-203138#code');
  });
  it('encodes ids', () => {
    expect(codeHref({ ...base, type: 'static', id: 'a b/c', match: 70, per_bp: {} } as IndexEntry)).toBe('/run/a%20b%2Fc#code');
  });
  it('interactions open their assembled App.jsx', () => {
    expect(codeHref({ ...base, type: 'interaction', id: 'ix-lambda-menu', page: '', state: '', kind: null, bps: [], variants: [] } as IndexEntry)).toBe('/interaction/ix-lambda-menu#code');
  });
  it('groups have no code link', () => {
    expect(codeHref({ ...base, type: 'group', id: 'g', page: '', given: null, held: [], variants: [] } as IndexEntry)).toBeNull();
  });
});
