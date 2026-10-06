import { useState } from 'react';
import type { Group, GroupVariant } from '../lib/types';
import { runAsset, useGroup } from '../lib/data';
import { Link } from '../lib/router';
import { splitTitle } from '../lib/bundle';
import { bpBg, cap, fmtDate, fmtUsd } from '../lib/format';
import { fmtScore } from '../lib/score';
import { Loading, ErrorView } from '../components/StatusView';
import { Tabs } from '../components/Tabs';
import { FittedFrame, FrameEmpty, FrameImage } from '../components/FittedFrame';
import { CompareSlider } from '../components/CompareSlider';
import { PassPill } from '../components/PassPill';
import { IconAlert, IconArrowLeft } from '../components/Icons';

export function GroupPage({ id }: { id: string }) {
  const r = useGroup(id);
  if (r.status === 'loading') return <Loading label="Loading experiment…" />;
  if (r.status === 'error') return <ErrorView title="Experiment not found" detail={r.error} />;
  if (!r.data.variants?.length) return <ErrorView title="No recorded runs" />;
  return <GroupView g={r.data} />;
}

const PLANNER: Record<string, string> = { nemotron: 'Nemotron planner', repeat: 'Repeat detector (no model)', template: 'Template (no model)' };

function signed(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(1)}`;
}

function GroupView({ g }: { g: Group }) {
  const [vkey, setVkey] = useState(g.variants[0].key);
  const v = g.variants.find((x) => x.key === vkey) ?? g.variants[0];
  const [member, setMember] = useState(g.held[0] ?? g.members[0]);

  return (
    <div className="page pt-6">
      <header className="flex flex-col gap-2">
        <Link to="/#experiments" className="inline-flex w-fit items-center gap-1 rounded-sm text-xs font-medium text-ink-muted hover:text-ink">
          <IconArrowLeft /> All runs
        </Link>
        <p className="eyebrow mt-1">Experiment</p>
        <h1 className="display text-2xl sm:text-3xl">{splitTitle(g.title).title}</h1>
        <div className="flex flex-wrap items-center gap-1.5">
          {splitTitle(g.title).note && <span className="chip border-dashed">{splitTitle(g.title).note}</span>}
          <span className="chip">Given: {g.given ? cap(g.given) : '—'}</span>
          <span className="chip">Held out: {g.held.map(cap).join(', ')}</span>
          <span className="font-mono text-[11px] text-ink-faint">
            {g.id} · {fmtDate(g.created)}
          </span>
        </div>
        <p className="mt-2 max-w-3xl text-sm text-ink-muted">
          The designer shows one opened tab and writes short notes. A planner wires the sibling tabs; their states were captured but never shown to
          any planner, so they test the plan. Δ = state score minus the untouched page's score at the same breakpoint.
        </p>
      </header>

      {g.review && (
        <div role="note" className="mt-5 flex max-w-3xl gap-3 rounded-lg border border-warn/40 bg-warn/10 p-4 text-sm">
          <span className="mt-0.5 text-warn">
            <IconAlert />
          </span>
          <p className="text-ink">{g.review}</p>
        </div>
      )}

      <section aria-labelledby="planners-title" className="section">
        <h2 id="planners-title" className="h2">
          Planners compared
        </h2>
        <div className="relative mt-3 overflow-x-auto rounded-md border border-line bg-surface">
          <table className="table">
            <caption className="sr-only">Planner runs: held-out results and costs. Select a row to see its renders.</caption>
            <thead>
              <tr>
                <th scope="col">Planner</th>
                <th scope="col">Facts</th>
                <th scope="col">Notes</th>
                <th scope="col" className="text-right">Held out</th>
                <th scope="col" className="text-right">Mean Δ</th>
                <th scope="col" className="text-right">Model $</th>
                <th scope="col" className="text-right">Sandbox $</th>
              </tr>
            </thead>
            <tbody>
              {g.variants.map((x) => (
                <tr key={x.key} className={x.key === v.key ? 'bg-accent/5' : ''}>
                  <td>
                    <button type="button" aria-pressed={x.key === v.key} onClick={() => setVkey(x.key)} className="rounded-sm text-left font-medium text-accent-strong underline-offset-2 hover:underline aria-pressed:text-ink aria-pressed:no-underline">
                      {PLANNER[x.planner] ?? x.planner}
                    </button>
                  </td>
                  <td className="text-ink-muted">{x.oracle ? 'DOM oracle' : 'Perception'}</td>
                  <td className="text-ink-muted">{x.notes === 'notes_prose' ? 'Free-form' : 'Structured'}</td>
                  <td className="text-right">
                    <PassPill status={x.held_out_pass === x.held_out_total ? 'pass' : 'fail'} label={`${x.held_out_pass}/${x.held_out_total}`} />
                  </td>
                  <td className="text-right num">{x.held_out_delta <= -100 ? 'not wired' : signed(x.held_out_delta)}</td>
                  <td className="text-right num">{fmtUsd(x.model_usd, 4)}</td>
                  <td className="text-right num">{fmtUsd(x.sandbox_usd, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="members-title" className="section">
        <h2 id="members-title" className="h2">
          {PLANNER[v.planner] ?? v.planner} · {v.oracle ? 'DOM oracle facts' : 'perception facts'}
        </h2>
        <div className="mt-3">
          <Tabs
            label="Tab state"
            size="md"
            value={member}
            onChange={setMember}
            tabs={g.members.map((m) => ({ key: m, label: `${cap(m)}${g.held.includes(m) ? ' · held out' : m === g.given ? ' · given' : ''}` }))}
          >
            <MemberRows g={g} v={v} member={member} />
          </Tabs>
        </div>
      </section>
    </div>
  );
}

function MemberRows({ g, v, member }: { g: Group; v: GroupVariant; member: string }) {
  const m = v.members[member];
  return (
    <div className="flex flex-col gap-3">
      {!m?.planned && <p className="text-sm text-bad">This planner did not wire “{cap(member)}”.</p>}
      {g.breakpoints.map((bp) => {
        const d = g.design[bp.name]?.[member];
        const r = v.renders[bp.name]?.[member];
        const design = d ? runAsset(g.id, d) : null;
        const render = r ? runAsset(g.id, r) : null;
        return (
          <section key={bp.name} aria-label={`${cap(bp.name)}`} className="card card-pad">
            <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-pill ${bpBg(bp.name)}`} aria-hidden="true" />
                <h3 className="text-sm font-semibold">{cap(bp.name)}</h3>
                <span className="font-mono text-[11px] text-ink-faint">
                  {bp.width}×{bp.height}
                </span>
              </div>
              <p className="text-xs text-ink-muted num">
                Score <strong className="font-semibold text-ink">{fmtScore(m?.scores[bp.name])}</strong> · untouched page {fmtScore(v.base_scores[bp.name])} · Δ{' '}
                <strong className="font-semibold text-ink">{signed(m?.delta[bp.name])}</strong>
              </p>
            </header>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Fig title="Design (captured, never shown to the planner)">
                <FittedFrame width={bp.width} height={bp.height}>{design ? <FrameImage src={design} alt={`${cap(bp.name)} design, ${member} tab`} /> : <FrameEmpty>No frame</FrameEmpty>}</FittedFrame>
              </Fig>
              <Fig title="Sandbox render after clicking the tab">
                <FittedFrame width={bp.width} height={bp.height}>{render ? <FrameImage src={render} alt={`${cap(bp.name)} render, ${member} tab`} /> : <FrameEmpty>Not rendered</FrameEmpty>}</FittedFrame>
              </Fig>
              <Fig title="Compare">
                {design && render ? (
                  <CompareSlider design={design} render={render} width={bp.width} height={bp.height} label={`${cap(bp.name)}: design versus render`} />
                ) : (
                  <FittedFrame width={bp.width} height={bp.height}>
                    <FrameEmpty>Nothing to compare</FrameEmpty>
                  </FittedFrame>
                )}
              </Fig>
            </div>
          </section>
        );
      })}
    </div>
  );
}

function Fig({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <figure className="flex min-w-0 flex-col gap-1.5">
      <figcaption className="text-[11px] font-medium uppercase tracking-[0.06em] text-ink-muted">{title}</figcaption>
      {children}
    </figure>
  );
}
