// The browser checks and explains frames exactly like the server (orchestrator/frames.py, Oct 12): any width
// 320–1600, any height ≤ 6000, PNG / JPEG / WebP; labelled by width (swaps fixed and said); full pages scored on
// their first screen; the standard Tailwind screen per width. Written before the code (TDD).
import { describe, expect, it } from 'vitest';
import { checkFrameFile, inferFrames, prefixFor } from './frames';

const f = (width: number, height: number, extra: Partial<{ type: string; name: string; size: number }> = {}) => ({
  type: 'image/png', name: 'f.png', size: 300_000, width, height, ...extra,
});

describe('checkFrameFile', () => {
  it('accepts PNG, JPEG and WebP of any size within the bounds', () => {
    expect(checkFrameFile('mobile', f(402, 2453))).toBeNull();
    expect(checkFrameFile('mobile', f(390, 844, { type: 'image/jpeg', name: 'a.jpg' }))).toBeNull();
    expect(checkFrameFile('mobile', f(390, 844, { type: '', name: 'a.webp' }))).toBeNull();
  });
  it('refuses other files, huge files and sizes outside the bounds, with a reason', () => {
    expect(checkFrameFile('mobile', f(390, 844, { type: 'image/gif', name: 'a.gif' }))).toMatch(/PNG, JPEG or WebP/);
    expect(checkFrameFile('mobile', f(390, 844, { size: 9 * 1024 * 1024 }))).toMatch(/8 MB/);
    expect(checkFrameFile('tablet', f(300, 1024))).toMatch(/320–1600 px wide/);
    expect(checkFrameFile('desktop', f(1280, 6001))).toMatch(/6000 px tall/);
    expect(checkFrameFile('mobile', f(0, 0))).toMatch(/not a readable image/);
  });
});

describe('inferFrames', () => {
  it("reads Hafsa's exports: labelled by width, full pages scored on the first screen", () => {
    const r = inferFrames({ mobile: f(402, 2453, { name: 'mobile.png' }), tablet: f(768, 1936, { name: 'tablet.png' }),
                            desktop: f(1071, 1177, { name: 'desktop.png' }) });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.rows.map((x) => [x.bp, x.width, x.scoredHeight, x.prefix])).toEqual([
      ['mobile', 402, 870, ''], ['tablet', 768, 1024, 'md:'], ['desktop', 1071, 1177, 'lg:'],
    ]);
    expect(r.rows[0].cropped).toBe(true);
    expect(r.rows[2].cropped).toBe(false);
    expect(r.notes.join(' ')).toMatch(/first screen/);
  });
  it('fixes swapped files by width and says so', () => {
    const r = inferFrames({ mobile: f(402, 900), tablet: f(1071, 1177, { name: 'tablet.png' }), desktop: f(768, 1024, { name: 'desktop.png' }) });
    expect(r.ok && r.rows.map((x) => x.source)).toEqual(['mobile', 'desktop', 'tablet']);
    expect(r.ok && r.notes.join(' ')).toMatch(/tablet\.png is 1071 px wide → used as the desktop frame/);
  });
  it('refuses frames that do not make three sizes', () => {
    expect(inferFrames({ mobile: f(390, 900), tablet: f(400, 900), desktop: f(1280, 800) })).toMatchObject({ ok: false });
    const r = inferFrames({ mobile: f(700, 900), tablet: f(768, 900), desktop: f(1280, 800) });
    expect(!r.ok && r.error).toMatch(/mobile width/);
  });
  it('maps widths to the standard Tailwind screens', () => {
    expect([320, 639, 640, 768, 1071, 1280, 1536].map(prefixFor)).toEqual(['', '', 'sm:', 'md:', 'lg:', 'xl:', '2xl:']);
  });
});
