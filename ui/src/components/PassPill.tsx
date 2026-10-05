import { IconCheck, IconMinus, IconX } from './Icons';

export type PillStatus = 'pass' | 'fail' | 'skipped';

const TONE: Record<PillStatus, string> = {
  pass: 'border-good/30 bg-good/10 text-good',
  fail: 'border-bad/30 bg-bad/10 text-bad',
  skipped: 'border-line bg-surface-2 text-ink-muted',
};
const WORD: Record<PillStatus, string> = { pass: 'Pass', fail: 'Fail', skipped: 'Not run' };

/** Pass / fail / not-run pill: icon + word, never colour alone. */
export function PassPill({ status, label, size = 'sm', className = '' }: { status: PillStatus; label?: string; size?: 'sm' | 'md'; className?: string }) {
  const pad = size === 'md' ? 'px-2.5 py-1 text-sm gap-1.5' : 'px-1.5 py-px text-xs gap-1';
  return (
    <span className={`inline-flex items-center rounded-pill border font-semibold ${pad} ${TONE[status]} ${className}`}>
      {status === 'pass' ? <IconCheck /> : status === 'fail' ? <IconX /> : <IconMinus />}
      {label ?? WORD[status]}
    </span>
  );
}

export function StatusIcon({ status, className = '' }: { status: PillStatus; className?: string }) {
  const tone = status === 'pass' ? 'text-good' : status === 'fail' ? 'text-bad' : 'text-ink-faint';
  return (
    <span className={`inline-flex ${tone} ${className}`}>
      {status === 'pass' ? <IconCheck /> : status === 'fail' ? <IconX /> : <IconMinus />}
      <span className="sr-only">{WORD[status]}</span>
    </span>
  );
}
