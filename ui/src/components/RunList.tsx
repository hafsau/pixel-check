import type { ReactNode } from 'react';
import { useRunIndex } from '../lib/data';
import { splitIndex } from '../lib/bundle';
import { RunCard } from './RunCard';
import { InteractionCard } from './InteractionCard';
import { GroupCard } from './GroupCard';

export function RunList() {
  const idx = useRunIndex();
  const s = idx.status === 'ready' ? splitIndex(idx.data) : null;
  return (
    <section id="runs" aria-labelledby="runs-title" className="section scroll-mt-6" tabIndex={-1}>
      <h2 id="runs-title" className="h2">
        Replay a run
      </h2>
      <p className="mt-1 text-sm text-ink-muted">Recorded runs, played back step by step. No models or sandboxes are called in replay.</p>
      {idx.status === 'loading' && <p className="mt-4 text-sm text-ink-muted" role="status">Loading runs…</p>}
      {idx.status === 'error' && (
        <p className="mt-4 text-sm text-bad" role="alert">
          Could not load runs: {idx.error}
        </p>
      )}
      {s && s.static.length + s.interaction.length + s.group.length === 0 && <p className="mt-4 text-sm text-ink-muted">No runs exported yet.</p>}
      {s && s.static.length > 0 && (
        <Group id="static" title="Static layout" intro="Three frames in, one responsive codebase out — rendered and scored at 390, 768 and 1280 px, plus fluidity checks between them.">
          {s.static.map((r) => (
            <RunCard key={r.id} run={r} />
          ))}
        </Group>
      )}
      {s && s.interaction.length > 0 && (
        <Group id="interactions" title="Interactions" intro="A state frame (the menu open, the disclosure expanded) in, working behaviour out — verified by tests generated from the frames and run in the sandbox.">
          {s.interaction.map((e) => (
            <InteractionCard key={e.id} e={e} />
          ))}
        </Group>
      )}
      {s && s.group.length > 0 && (
        <Group id="experiments" title="Experiments" intro="Work in progress, shown with its review.">
          {s.group.map((e) => (
            <GroupCard key={e.id} e={e} />
          ))}
        </Group>
      )}
    </section>
  );
}

function Group({ id, title, intro, children }: { id: string; title: string; intro: string; children: ReactNode[] }) {
  return (
    <div className="mt-8" aria-labelledby={`${id}-title`} role="group">
      <div className="flex items-baseline justify-between gap-3 border-b border-line pb-2">
        <h3 id={`${id}-title`} className="eyebrow">
          {title}
        </h3>
        <span className="text-xs text-ink-faint num">{children.length}</span>
      </div>
      <p className="mt-2 max-w-2xl text-sm text-ink-muted">{intro}</p>
      <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {children.map((c, i) => (
          <li key={i} className="min-w-0 [&>*]:h-full">
            {c}
          </li>
        ))}
      </ul>
    </div>
  );
}
