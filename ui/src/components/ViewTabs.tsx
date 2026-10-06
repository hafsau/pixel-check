import { useRef, type KeyboardEvent, type ReactNode } from 'react';

/** Segmented-control look, WAI-ARIA tabs behaviour (roving tabindex; ←/→/Home/End move and activate). */
export function ViewTabs<K extends string>({ id, label, tabs, value, onChange }: { id: string; label: string; tabs: { key: K; label: ReactNode }[]; value: K; onChange: (k: K) => void }) {
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
    <div role="tablist" aria-label={label} className="seg" onKeyDown={onKey}>
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
          className="seg-item min-h-[34px] px-3.5 text-[13px] aria-selected:bg-surface aria-selected:text-ink aria-selected:shadow-card"
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
