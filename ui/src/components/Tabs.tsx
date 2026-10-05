import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';

/** WAI-ARIA tabs: roving tabindex, ←/→ (and Home/End) move and activate. */
export function Tabs<K extends string>({
  label,
  tabs,
  value,
  onChange,
  children,
  size = 'sm',
}: {
  label: string;
  tabs: { key: K; label: ReactNode }[];
  value: K;
  onChange: (k: K) => void;
  children: ReactNode;
  size?: 'sm' | 'md';
}) {
  const id = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const i = Math.max(0, tabs.findIndex((t) => t.key === value));
  const onKey = (e: KeyboardEvent) => {
    const n = tabs.length;
    const to = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i - 1 + n) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
    if (to < 0) return;
    e.preventDefault();
    onChange(tabs[to].key);
    refs.current[to]?.focus();
  };
  return (
    <div>
      <div role="tablist" aria-label={label} className="relative flex gap-1 overflow-x-auto border-b border-line" onKeyDown={onKey}>
        {tabs.map((t, j) => (
          <button
            key={t.key}
            ref={(el) => {
              refs.current[j] = el;
            }}
            type="button"
            role="tab"
            id={`${id}-tab-${t.key}`}
            aria-selected={t.key === value}
            aria-controls={`${id}-panel`}
            tabIndex={t.key === value ? 0 : -1}
            onClick={() => onChange(t.key)}
            className={`-mb-px shrink-0 whitespace-nowrap border-b-2 px-2.5 font-medium transition-colors ${size === 'md' ? 'py-2 text-sm' : 'py-1.5 text-xs'} ${
              t.key === value ? 'border-accent text-ink' : 'border-transparent text-ink-muted hover:text-ink'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-tab-${value}`} tabIndex={0} className="pt-3 outline-none">
        {children}
      </div>
    </div>
  );
}
