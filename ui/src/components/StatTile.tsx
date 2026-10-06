import type { ReactNode } from 'react';

/** `pixel` sets the value in Geist Pixel (large score numerals only). */
export function StatTile({ label, value, hint, tone = '', pixel = false }: { label: string; value: ReactNode; hint?: ReactNode; tone?: string; pixel?: boolean }) {
  return (
    <div className="card card-pad">
      <dt className="eyebrow">{label}</dt>
      <dd className={`mt-1.5 num ${pixel ? 'pixel text-[32px] leading-none' : 'text-2xl font-semibold tracking-[-0.02em]'} ${tone}`}>{value}</dd>
      {hint && <dd className="mt-1 text-xs text-ink-muted">{hint}</dd>}
    </div>
  );
}
