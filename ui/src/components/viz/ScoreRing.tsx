import { bandLabel, bandOf, fmtScore, type Band } from '../../lib/score';
import { ringModel } from '../../lib/viz';

const STROKE: Record<Band, string> = { good: 'stroke-good', ok: 'stroke-ok', warn: 'stroke-warn', bad: 'stroke-bad' };

/** One ring for the overall Match (= worst breakpoint): arc ∝ score, coloured by band, number in Geist Pixel. */
export function ScoreRing({ score, size = 64, label = 'Match', className = '' }: { score: number | null | undefined; size?: number; label?: string; className?: string }) {
  const stroke = Math.max(3, Math.round(size / 13));
  const r = (size - stroke) / 2;
  const m = ringModel(score, r);
  const band = bandOf(score);
  const big = size >= 80;
  return (
    <div className={`relative inline-grid shrink-0 place-items-center ${className}`} style={{ width: size, height: size }} role="img" aria-label={`${label} ${fmtScore(score)} of 100 — ${bandLabel(score)}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-ink/[0.08]" />
        {score != null && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${m.dash} ${m.gap}`}
            className={`${STROKE[band]} transition-[stroke-dasharray] duration-700`}
          />
        )}
      </svg>
      <span className="absolute inset-0 grid place-items-center" aria-hidden="true">
        <span className={`pixel leading-none num ${big ? 'text-[28px]' : size >= 56 ? 'text-[17px]' : 'text-[13px]'}`}>{fmtScore(score)}</span>
      </span>
    </div>
  );
}
