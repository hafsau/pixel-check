import { describe, expect, it } from 'vitest';
import { EXAMPLE, checkDurationNote, exampleFrameUrls } from './check';

// Live-deploy council (Oct 21): judges have no design frames, and the free server reads frames in ~9 minutes.
describe('the example', () => {
  it('is the author’s dashboard frames and its Lovable build', () => {
    expect(EXAMPLE.url).toBe('https://adaptable-hub-central.lovable.app/');
    expect(exampleFrameUrls('')).toEqual({ mobile: '/examples/dashboard/mobile.png', tablet: '/examples/dashboard/tablet.png', desktop: '/examples/dashboard/desktop.png' });
    expect(exampleFrameUrls('/app/').mobile).toBe('/app/examples/dashboard/mobile.png');
  });
});

describe('how long a check takes, said honestly', () => {
  it('names the slow part for your own frames and the fast paths', () => {
    expect(checkDurationNote({ audit: true })).toMatch(/under a minute/);
    const own = checkDurationNote({ audit: false });
    expect(own).toMatch(/several minutes/);
    expect(own).toMatch(/example/);
    expect(checkDurationNote({ audit: false, repairing: true })).toMatch(/repair/);
    expect(own).not.toMatch(/1–3 minutes/);
  });
});
