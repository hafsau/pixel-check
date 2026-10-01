import { splitModel } from '../lib/format';

/** "nvidia/Nemotron-3-Ultra-550b-a55b" → vendor in caps + model name. NVIDIA models get a marker. */
export function ModelName({ id, className = '' }: { id: string; className?: string }) {
  const { vendor, name } = splitModel(id);
  const nvidia = vendor.toLowerCase() === 'nvidia';
  return (
    <span className={`inline-flex items-baseline gap-1.5 ${className}`}>
      {vendor && (
        <span className={`text-[10px] font-semibold uppercase tracking-[0.06em] ${nvidia ? 'text-good' : 'text-ink-faint'}`}>{vendor === 'nvidia' ? 'NVIDIA' : vendor}</span>
      )}
      <span className="font-mono text-xs">{name}</span>
    </span>
  );
}
