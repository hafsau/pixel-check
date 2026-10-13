// Frames as designers export them — the browser mirror of orchestrator/frames.py (Oct 12): any width 320–1600 px,
// any height ≤ 6000 px, PNG / JPEG / WebP. The three frames are labelled by width (a swap is fixed and said); a
// full page taller than 1.5 screens is scored on its first screen; each width gets the standard Tailwind screen.
import type { LiveBp } from './live';

export const BPS: LiveBp[] = ['mobile', 'tablet', 'desktop'];
export const MAX_FRAME_BYTES = 8 * 1024 * 1024; // api.MAX_BYTES
const MIN_W = 320;
const MAX_W = 1600;
const MAX_H = 6000;
const KEEP_WHOLE = 1.5;
const STANDARD: Record<LiveBp, [number, number]> = { mobile: [390, 844], tablet: [768, 1024], desktop: [1280, 800] };
const SCREENS: [string, number][] = [['sm:', 640], ['md:', 768], ['lg:', 1024], ['xl:', 1280], ['2xl:', 1536]];

export interface FrameFile {
  type: string;
  name: string;
  size: number;
  width: number;
  height: number;
}

export interface FrameRow {
  bp: LiveBp;
  source: LiveBp; // the slot the file was picked in
  name: string;
  width: number;
  height: number;
  scoredHeight: number;
  cropped: boolean;
  prefix: string;
}

export type Inferred = { ok: true; rows: FrameRow[]; notes: string[] } | { ok: false; error: string };

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function prefixFor(width: number): string {
  let pre = '';
  for (const [p, w] of SCREENS) if (width >= w) pre = p;
  return pre;
}

export function screenHeight(bp: LiveBp, width: number): number {
  if (bp === 'desktop') return 800;
  const [w, h] = STANDARD[bp];
  return Math.round((width * h) / w);
}

/** One picked file, checked like the server checks it; null when fine. */
export function checkFrameFile(slot: LiveBp, f: FrameFile): string | null {
  const name = cap(slot);
  const okType = f.type ? /^image\/(png|jpeg|webp)$/.test(f.type) : /\.(png|jpe?g|webp)$/i.test(f.name);
  if (!okType) return `${name}: use a PNG, JPEG or WebP image.`;
  if (f.size > MAX_FRAME_BYTES) return `${name}: the frame is larger than ${MAX_FRAME_BYTES / (1024 * 1024)} MB.`;
  if (!f.width || !f.height) return `${name}: not a readable image.`;
  if (f.width < MIN_W || f.width > MAX_W) return `${name}: ${f.width} px wide — frames must be ${MIN_W}–${MAX_W} px wide (export at 1×).`;
  if (f.height > MAX_H) return `${name}: ${f.height} px tall — frames can be at most ${MAX_H} px tall.`;
  if (f.height < 200) return `${name}: ${f.height} px tall is too short for a screen.`;
  return null;
}

/** The three frames → how PixelCheck will read them (labels by width, first-screen crops, Tailwind screens). */
export function inferFrames(files: Record<LiveBp, FrameFile>): Inferred {
  const order = [...BPS].sort((a, b) => files[a].width - files[b].width);
  const widths = order.map((s) => files[s].width);
  if (prefixFor(widths[0]) !== '')
    return { ok: false, error: `The narrowest frame (${widths[0]} px) must be a mobile width (under 640 px).` };
  if (new Set(widths.map(prefixFor)).size !== 3)
    return {
      ok: false,
      error: `The frames (${widths.map((w) => `${w} px`).join(', ')}) must fall in three different Tailwind screens (under 640 · 640 · 768 · 1024 · 1280 · 1536 px): two are too close.`,
    };
  const rows: FrameRow[] = [];
  const notes: string[] = [];
  BPS.forEach((bp, k) => {
    const source = order[k];
    const f = files[source];
    const sh = screenHeight(bp, f.width);
    const cropped = f.height > KEEP_WHOLE * sh;
    rows.push({ bp, source, name: f.name, width: f.width, height: f.height, scoredHeight: cropped ? sh : f.height, cropped, prefix: prefixFor(f.width) });
    if (source !== bp) notes.push(`${source}.png is ${f.width} px wide → used as the ${bp} frame`);
    if (cropped) notes.push(`${source}.png is ${f.height} px tall (a full page) → scored on the first screen (${f.width}×${sh}); the full page is kept for display`);
  });
  return { ok: true, rows, notes };
}
