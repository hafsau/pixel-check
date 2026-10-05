import { useState } from 'react';
import type { Attempt, Interaction } from '../../lib/types';
import { runAsset, useText } from '../../lib/data';
import { Tabs } from '../Tabs';
import { CodeViewer } from '../CodeViewer';

const ORDER = ['HOOKS', 'TRIGGER_PROPS', 'TRIGGER_OPEN', 'OVERLAY', 'INLINE'];
const HELP: Record<string, string> = {
  HOOKS: 'State and effects (open flag, Escape listener)',
  TRIGGER_PROPS: 'Props on the compiled trigger button',
  TRIGGER_OPEN: "The trigger's open look",
  OVERLAY: 'Panel and backdrop rendered when open',
  INLINE: 'Content inserted in the page flow',
};

/** The sections the writer returned; the app assembles them deterministically into App.jsx. */
export function SectionsView({ ix, attempt, writer }: { ix: Interaction; attempt: Attempt; writer: string }) {
  const keys = [...ORDER.filter((k) => k in attempt.sections), ...Object.keys(attempt.sections).filter((k) => !ORDER.includes(k))];
  const [tab, setTab] = useState<string>(keys[0] ?? 'HOOKS');
  const [full, setFull] = useState(false);
  const code = useText(full && attempt.code ? runAsset(ix.id, attempt.code) : null);
  const cur = keys.includes(tab) ? tab : keys[0];
  return (
    <section aria-labelledby="sections-title" className="card card-pad">
      <h2 id="sections-title" className="h2">
        Code
      </h2>
      <p className="mt-1 text-xs text-ink-muted">
        {writer === 'nemotron' ? 'The four sections Nemotron wrote in this attempt' : 'The sections the template filled in'}; they are assembled
        deterministically into the compiled page.
      </p>
      {keys.length > 0 ? (
        <div className="mt-3">
          <Tabs label="Code sections" tabs={keys.map((k) => ({ key: k, label: <span className="font-mono">{k}</span> }))} value={cur} onChange={setTab}>
            <p className="mb-2 text-xs text-ink-muted">{HELP[cur] ?? ''}</p>
            <pre className="relative max-h-80 overflow-auto rounded-md border border-line bg-surface-2 p-3 text-[12px] leading-[1.6]">
              <code className="whitespace-pre">{attempt.sections[cur]?.trim() || '(empty)'}</code>
            </pre>
          </Tabs>
        </div>
      ) : (
        <p className="mt-3 text-sm text-ink-muted">No sections recorded for this attempt.</p>
      )}
      {attempt.code && (
        <div className="mt-4">
          <button type="button" className="btn" aria-expanded={full} onClick={() => setFull((f) => !f)}>
            {full ? 'Hide' : 'Show'} the assembled App.jsx
          </button>
          {full && (
            <div className="mt-3">
              {code.status === 'ready' && code.data ? <CodeViewer code={code.data} /> : code.status === 'error' ? <p className="text-sm text-bad">{code.error}</p> : <p className="text-sm text-ink-muted" role="status">Loading…</p>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
