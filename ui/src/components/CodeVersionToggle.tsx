import type { CodeVersion } from '../lib/owned';

/** Owned sites: the delivered code (the page's own images) or the code exactly as scored (grey image blocks). */
export function CodeVersionToggle({ value, onChange, className = '' }: { value: CodeVersion; onChange: (v: CodeVersion) => void; className?: string }) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <div className="seg w-fit" role="radiogroup" aria-label="Code version">
        {(
          [
            ['delivered', 'With your images'],
            ['scored', 'As scored'],
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" role="radio" aria-checked={value === k} className="seg-item" onClick={() => onChange(k)}>
            {label}
          </button>
        ))}
      </div>
      <p className="text-xs text-ink-muted">Scored with images as grey blocks, like the capture. The delivered code puts your images back in those boxes.</p>
    </div>
  );
}
