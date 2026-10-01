export type CompareMode = 'slider' | 'difference';

export function CompareModeToggle({ mode, onChange }: { mode: CompareMode; onChange: (m: CompareMode) => void }) {
  return (
    <div className="seg" role="radiogroup" aria-label="Comparison mode">
      {(['slider', 'difference'] as const).map((m) => (
        <button key={m} type="button" role="radio" aria-checked={mode === m} className="seg-item" onClick={() => onChange(m)}>
          {m === 'slider' ? 'Slider' : 'Difference'}
        </button>
      ))}
    </div>
  );
}
