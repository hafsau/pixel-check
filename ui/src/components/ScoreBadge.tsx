import { BAND_SOFT, bandLabel, bandOf, fmtScore } from '../lib/score';

/** Pill with a score coloured by band. `dq` renders a red "DQ" pill instead. */
export function ScoreBadge({
  score,
  dq = false,
  empty = false,
  size = 'sm',
  className = '',
}: {
  score: number | null | undefined;
  dq?: boolean;
  empty?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}) {
  const pad = size === 'md' ? 'px-2 py-0.5 text-sm' : 'px-1.5 py-px text-xs';
  if (dq)
    return (
      <span className={`inline-flex items-center rounded-pill border font-semibold num ${pad} ${BAND_SOFT.bad} ${className}`}>
        DQ
      </span>
    );
  if (empty)
    return (
      <span className={`inline-flex items-center rounded-pill border border-line font-semibold text-ink-faint ${pad} ${className}`}>
        —
      </span>
    );
  return (
    <span
      className={`inline-flex items-center rounded-pill border font-semibold num ${pad} ${BAND_SOFT[bandOf(score)]} ${className}`}
      title={bandLabel(score)}
    >
      {fmtScore(score)}
    </span>
  );
}
