import type { ReactNode } from 'react';

export function StatTile({ label, value, hint, tone = '' }: { label: string; value: ReactNode; hint?: ReactNode; tone?: string }) {
  return (
    <div className="card card-pad">
      <dt className="eyebrow">{label}</dt>
      <dd className={`mt-1.5 text-2xl font-semibold tracking-tight num ${tone}`}>{value}</dd>
      {hint && <dd className="mt-0.5 text-xs text-ink-muted">{hint}</dd>}
    </div>
  );
}
