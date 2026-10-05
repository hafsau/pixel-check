import type { Candidate, Run } from '../lib/types';
import { cap, fmtUsd } from '../lib/format';
import { fmtScore } from '../lib/score';
import { ModelName } from './ModelName';
import { StatusIcon } from './PassPill';

/**
 * What produced this candidate, step by step: perception model, Nemotron's structure plans and whether they were
 * adopted, the deterministic compiler, and the sandbox checks between breakpoints (fluidity) and on controls.
 */
export function PipelinePanel({ run, shown }: { run: Run; shown: Candidate }) {
  const p = run.pipeline;
  if (!p) return null;
  const callsBy = (step: string) => run.calls.filter((c) => c.step === step);
  const intentCalls = callsBy('intent plan');
  const structCalls = callsBy('structure plan');
  const tags = [...new Set(p.structure_plans.flatMap((s) => Object.values(s.tags)))];
  const ad = p.intent_adoption;
  const fl = shown.fluidity;
  const ctl = shown.controls;
  const usd = (cs: typeof intentCalls) => cs.reduce((a, c) => a + (c.usd || 0), 0);

  return (
    <section aria-labelledby="pipe-title" className="card card-pad">
      <h2 id="pipe-title" className="h2">
        Pipeline
      </h2>
      <p className="mt-1 text-xs text-ink-muted">How this run was produced. Steps marked “no model” are deterministic.</p>
      <ol className="mt-4 flex flex-col gap-4">
        <Step n={1} title="Perceive">
          {run.models?.vision ? <ModelName id={run.models.vision} /> : 'Vision model'} reads the text; OCR and pixel measurement give boxes, colours and type.
        </Step>
        <Step n={2} title="Plan structure" meta={structCalls.length + intentCalls.length ? `${structCalls.length + intentCalls.length} calls · ${fmtUsd(usd(structCalls) + usd(intentCalls), 4)}` : undefined}>
          {p.structure_plans.length > 0 && (
            <p>
              {structCalls[0] ? <ModelName id={structCalls[0].model} /> : 'Nemotron'} names the regions:{' '}
              {tags.length ? tags.map((t) => <code key={t} className="mono-chip mr-1">{`<${t}>`}</code>) : 'none applied'}
            </p>
          )}
          {p.intent_plan && (
            <p className="mt-1.5">
              {intentCalls[0] ? <ModelName id={intentCalls[0].model} /> : 'Nemotron'} looks for repeated components:{' '}
              {p.intent_plan.cards.length ? p.intent_plan.cards.map((c) => `${c.name ?? 'group'} (${c.count})`).join(', ') : 'none found'}
              {Object.keys(p.intent_plan.bands).length ? ` · bands: ${bandSummary(p.intent_plan.bands)}` : ''}.
            </p>
          )}
          {ad && (
            <p className="mt-1.5">
              Verified before use: {ad.adopted ? <strong className="font-semibold text-ink">adopted</strong> : <strong className="font-semibold text-ink">not adopted</strong>} — winner
              “{ad.winner}” at {fmtScore(ad.match)}, {ad.fluid_fails} fluidity fails.
            </p>
          )}
        </Step>
        <Step n={3} title="Compile" meta="no model">
          {p.compiler === 'fluid' ? 'Fluid compiler' : p.compiler === 'scaffold' ? 'Measured scaffold' : 'Compiler'} writes one React + Tailwind file: centred bands, wrapping rows, grid columns per breakpoint, real
          inputs / buttons / links.
        </Step>
        <Step n={4} title="Render & check in the sandbox" meta={`${run.candidates.filter((c) => c.checkpoint).length} renders · ${fmtUsd(run.result.spend_sandbox_usd ?? run.candidates.reduce((a, c) => a + (c.sandbox_cost || 0), 0), 3)}`}>
          {fl ? (
            <>
              <p>
                Between breakpoints (candidate <code className="font-mono">{shown.id}</code>): no sideways scroll, no overlaps, content stays centred.
              </p>
              <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Fluidity per width">
                {Object.entries(fl.widths).filter(([w]) => /^\d+$/.test(w)).map(([w, x]) => (
                  <li key={w} className={`chip num ${x.ok ? '' : 'border-bad/30 bg-bad/10 text-bad'}`} title={`overflow ${x.overflow}px · overlaps ${x.overlaps} · centre drift ${x.centre_drift}`}>
                    <StatusIcon status={x.ok ? 'pass' : 'fail'} />
                    {w}px
                  </li>
                ))}
              </ul>
              {fl.fails.length > 0 && <p className="mt-1.5 text-xs text-bad">Fails at: {fl.fails.map((f) => (/^\d+$/.test(String(f)) ? `${f}px` : cap(String(f)))).join(', ')}</p>}
            </>
          ) : (
            <p>No fluidity record for this candidate.</p>
          )}
          {ctl && (
            <p className="mt-2 num">
              Controls: {ctl.buttons_focusable ?? 0}/{ctl.buttons ?? 0} buttons focusable · {ctl.links_with_href ?? 0}/{ctl.links ?? 0} links with href ·{' '}
              {ctl.inputs_typeable ?? 0}/{ctl.inputs ?? 0} inputs typeable{ctl.clickable_divs ? ` · ${ctl.clickable_divs} clickable divs` : ''}
            </p>
          )}
        </Step>
        <Step n={5} title="Score" meta="no model">
          Each render against its frame; Match = the worst breakpoint ({shown.worst ? cap(shown.worst) : '—'} for this candidate).
        </Step>
      </ol>
    </section>
  );
}

function bandSummary(b: Record<string, string>): string {
  const n = new Map<string, number>();
  Object.values(b).forEach((v) => n.set(v, (n.get(v) ?? 0) + 1));
  return [...n].map(([k, c]) => `${c} ${k}`).join(', ');
}

function Step({ n, title, meta, children }: { n: number; title: string; meta?: string; children: React.ReactNode }) {
  return (
    <li className="grid grid-cols-[1.75rem_1fr] gap-3">
      <span className="flex h-7 w-7 items-center justify-center rounded-pill border border-line bg-surface-2 text-xs font-semibold num" aria-hidden="true">
        {n}
      </span>
      <div className="min-w-0 text-sm text-ink-muted">
        <p className="flex flex-wrap items-baseline justify-between gap-x-3">
          <span className="font-semibold text-ink">{title}</span>
          {meta && <span className="text-[11px] text-ink-faint num">{meta}</span>}
        </p>
        <div className="mt-0.5">{children}</div>
      </div>
    </li>
  );
}
