import type { BpName } from './types';

export function fmtUsd(v: number | null | undefined, digits = 4): string {
  if (v == null) return '—';
  return `$${v.toFixed(digits)}`;
}

export function fmtInt(v: number | null | undefined): string {
  if (v == null) return '—';
  return v.toLocaleString('en-US');
}

export function fmtSecs(v: number | null | undefined): string {
  if (v == null) return '—';
  if (v < 60) return `${v.toFixed(1)} s`;
  const m = Math.floor(v / 60);
  const s = Math.round(v - m * 60);
  return `${m} min ${s.toString().padStart(2, '0')} s`;
}

export function fmtDate(unix: number): string {
  return new Date(unix * 1000).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Tailwind classes per breakpoint series. Unknown breakpoints fall back to ink. */
export const BP_TEXT: Record<string, string> = {
  mobile: 'text-bp-mobile',
  tablet: 'text-bp-tablet',
  desktop: 'text-bp-desktop',
};
export const BP_BG: Record<string, string> = {
  mobile: 'bg-bp-mobile',
  tablet: 'bg-bp-tablet',
  desktop: 'bg-bp-desktop',
};
export const BP_STROKE_VAR: Record<string, string> = {
  mobile: 'rgb(var(--c-bp-mobile))',
  tablet: 'rgb(var(--c-bp-tablet))',
  desktop: 'rgb(var(--c-bp-desktop))',
};
export function bpText(bp: BpName): string {
  return BP_TEXT[bp] ?? 'text-ink';
}
export function bpBg(bp: BpName): string {
  return BP_BG[bp] ?? 'bg-ink';
}

/** Default breakpoints, used when a run does not list them. */
export const DEFAULT_BPS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 800 },
] as const;

/** Split "nvidia/Nemotron-3-Ultra-550b-a55b" into vendor + model name. */
export function splitModel(id: string): { vendor: string; name: string } {
  const i = id.indexOf('/');
  return i < 0 ? { vendor: '', name: id } : { vendor: id.slice(0, i), name: id.slice(i + 1) };
}
