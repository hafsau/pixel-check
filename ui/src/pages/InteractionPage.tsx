import { useEffect, useMemo, useState } from 'react';
import type { Interaction, ScenarioSlot } from '../lib/types';
import { useInteraction } from '../lib/data';
import { Link } from '../lib/router';
import { splitTitle } from '../lib/bundle';
import { cap, fmtDate } from '../lib/format';
import { bestAttempt, buildChecklist, verdictLine } from '../lib/interactions';
import { Loading, ErrorView } from '../components/StatusView';
import { CompareModeToggle, type CompareMode } from '../components/CompareModeToggle';
import { IconArrowLeft } from '../components/Icons';
import { WriterCompare } from '../components/interaction/WriterCompare';
import { AttemptTimeline } from '../components/interaction/AttemptTimeline';
import { ScenarioRows, SCENARIOS } from '../components/interaction/ScenarioRows';
import { Checklist } from '../components/interaction/Checklist';
import { SectionsView } from '../components/interaction/SectionsView';
import { RunRecords } from '../components/interaction/RunRecords';

export function InteractionPage({ id }: { id: string }) {
  const r = useInteraction(id);
  if (r.status === 'loading') return <Loading label="Loading interaction…" />;
  if (r.status === 'error') return <ErrorView title="Interaction not found" detail={r.error} />;
  if (!r.data.variants?.length) return <ErrorView title="This interaction has no recorded runs" />;
  return <InteractionView ix={r.data} />;
}

const KIND: Record<string, string> = {
  overlay: 'Full-screen overlay',
  drawer: 'Side drawer',
  inline: 'Inline disclosure',
};

function InteractionView({ ix }: { ix: Interaction }) {
  const initial = ix.variants.find((v) => v.writer === 'nemotron') ?? ix.variants[0];
  const [vkey, setVkey] = useState(initial.key);
  const v = ix.variants.find((x) => x.key === vkey) ?? initial;
  const [ai, setAi] = useState(() => v.attempts.indexOf(bestAttempt(v)!));
  const [slot, setSlot] = useState<ScenarioSlot>('open');
  const [mode, setMode] = useState<CompareMode>('slider');

  useEffect(() => {
    const b = bestAttempt(v);
    setAi(b ? v.attempts.indexOf(b) : 0);
  }, [v]);

  const attempt = v.attempts[Math.max(0, Math.min(ai, v.attempts.length - 1))];
  const bps = ix.breakpoints.map((b) => b.name);
  const checklist = useMemo(() => (attempt ? buildChecklist(attempt, bps) : { rows: [], general: [] }), [attempt, bps.join()]); // eslint-disable-line react-hooks/exhaustive-deps
  const line = verdictLine(ix.variants);

  return (
    <div className="page pt-6">
      <header className="flex flex-col gap-2">
        <Link to="/#interactions" className="inline-flex w-fit items-center gap-1 rounded-sm text-xs font-medium text-ink-muted hover:text-ink">
          <IconArrowLeft /> All runs
        </Link>
        <p className="eyebrow mt-1">Interaction</p>
        <h1 className="display text-2xl sm:text-3xl">{splitTitle(ix.title).title}</h1>
        <div className="flex flex-wrap items-center gap-1.5">
          {splitTitle(ix.title).note && <span className="chip border-dashed">{splitTitle(ix.title).note}</span>}
          {ix.kind && <span className="chip">{KIND[ix.kind] ?? cap(ix.kind)}</span>}
          <span className="chip">State frames: {bps.map(cap).join(' + ')}</span>
          <span className="chip">State “{ix.state}”</span>
          <span className="font-mono text-[11px] text-ink-faint">
            {ix.id} · {fmtDate(ix.created)}
          </span>
        </div>
        {line && (
          <p className="mt-2 max-w-3xl text-sm text-ink-muted" aria-live="polite">
            <strong className="font-semibold text-ink">{line}</strong> Recorded sandbox runs; replay calls nothing.
          </p>
        )}
      </header>

      <div className="mt-6">
        <WriterCompare ix={ix} selected={v.key} onSelect={setVkey} />
      </div>

      {attempt ? (
        <>
          <div className="mt-6">
            <AttemptTimeline v={v} selected={ai} onSelect={setAi} />
          </div>

          <section aria-labelledby="captures-title" className="section">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="captures-title" className="h2">
                  Design vs render · attempt {ai + 1}
                </h2>
                <p className="mt-1 text-xs text-ink-muted">
                  {SCENARIOS.find((s) => s.slot === slot)?.steps}. The outlined box is the trigger in the design.
                </p>
              </div>
              <CompareModeToggle mode={mode} onChange={setMode} />
            </div>
            <div className="mt-3">
              <ScenarioRows ix={ix} attempt={attempt} rows={checklist.rows} slot={slot} onSlot={setSlot} mode={mode} />
            </div>
          </section>

          <div className="section flex flex-col gap-4 [&>*]:min-w-0">
            <Checklist rows={checklist.rows} general={checklist.general} bps={ix.breakpoints} writer={v.writer} fedBack={ai < v.attempts.length - 1 && !attempt.infra} />
            <SectionsView key={`${v.key}-${ai}`} ix={ix} attempt={attempt} writer={v.writer} />
          </div>
        </>
      ) : (
        <p className="mt-6 text-sm text-ink-muted">No attempts recorded for this writer.</p>
      )}

      <div className="section">
        <RunRecords ix={ix} v={v} />
      </div>
    </div>
  );
}
