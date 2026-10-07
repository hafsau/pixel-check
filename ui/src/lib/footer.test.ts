import { describe, expect, it } from 'vitest';
import { footerNote } from './footer';

describe('footerNote', () => {
  it('live runs and check results called real models', () => {
    expect(footerNote('/live/20261006-101740-bcabfc')).toMatch(/^Live mode/);
    expect(footerNote('/check/20261006-113849-46f352')).toMatch(/^Live mode/);
  });
  it('replays and other pages call nothing', () => {
    expect(footerNote('/')).toMatch(/^Replay mode/);
    expect(footerNote('/run/netflix')).toMatch(/^Replay mode/);
    expect(footerNote('/check')).toMatch(/^Replay mode/);
  });
});
