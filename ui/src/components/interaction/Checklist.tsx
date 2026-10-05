import type { Breakpoint } from '../../lib/types';
import type { ChecklistRow } from '../../lib/interactions';
import { bpBg, cap } from '../../lib/format';
import { StatusIcon } from '../PassPill';

/** The tests generated from the state frames, pass / fail per breakpoint, and the failure sentences the writer saw. */
export function Checklist({ rows, general, bps, writer, fedBack }: { rows: ChecklistRow[]; general: string[]; bps: Breakpoint[]; writer: string; fedBack: boolean }) {
  const failing = rows.flatMap((r) => bps.flatMap((bp) => (r.cells[bp.name]?.reasons ?? []).map((t) => ({ check: r.label, bp: bp.name, t }))));
  const counts = rows.flatMap((r) => bps.map((bp) => r.cells[bp.name]?.status));
  const passed = counts.filter((s) => s === 'pass').length;
  const ran = counts.filter((s) => s !== 'skipped').length;
  return (
    <section aria-labelledby="tests-title" className="card card-pad">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="tests-title" className="h2">
          Tests
        </h2>
        <p className="text-sm text-ink-muted num">
          <strong className="font-semibold text-ink">{passed}</strong> of {ran} checks pass{ran < counts.length ? ` · ${counts.length - ran} not run` : ''}
        </p>
      </div>
      <p className="mt-1 text-xs text-ink-muted">Generated from the state frames and run in the sandbox (Playwright, network off). Scores use the same scorer as the static pipeline.</p>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:items-start">
      <div className="relative overflow-x-auto rounded-md border border-line">
        <table className="table [&_td]:whitespace-normal">
          <caption className="sr-only">Generated interaction tests: result per breakpoint</caption>
          <thead>
            <tr>
              <th scope="col">Check</th>
              {bps.map((bp) => (
                <th key={bp.name} scope="col" className="w-20 text-center">
                  <span className="inline-flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-pill ${bpBg(bp.name)}`} aria-hidden="true" />
                    {cap(bp.name)}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <th scope="row" className="min-w-[11rem] !whitespace-normal border-b border-line !bg-transparent px-3 py-2 text-left align-top text-sm font-medium text-ink">
                  {r.label}
                  <span className="mt-0.5 block text-xs font-normal text-ink-muted">{r.detail}</span>
                </th>
                {bps.map((bp) => {
                  const c = r.cells[bp.name];
                  if (!c) return <td key={bp.name} />;
                  return (
                    <td key={bp.name} title={c.note} className={`w-20 text-center align-top ${c.status === 'fail' ? 'bg-bad/5' : ''}`}>
                      <span className="inline-flex flex-col items-center gap-0.5">
                        <StatusIcon status={c.status} />
                        <span className={`text-[11px] num ${c.status === 'fail' ? 'font-semibold text-bad' : 'text-ink-muted'}`}>
                          {c.score != null ? c.score.toFixed(1) : c.status === 'skipped' ? 'not run' : ''}
                        </span>
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {failing.length === 0 && general.length === 0 && <p className="text-sm text-ink-muted">No failures: every check that ran passed.</p>}
      {(failing.length > 0 || general.length > 0) && (
        <div>
          <h3 className="text-sm font-semibold">{fedBack && writer === 'nemotron' ? 'Failures fed back to Nemotron for the next attempt' : 'Failures'}</h3>
          <ul className="mt-2 flex flex-col gap-1.5">
            {failing.map((f, i) => (
              <li key={i} className="flex gap-2 rounded-md bg-bad/5 px-3 py-2 text-xs leading-relaxed">
                <span className="shrink-0 font-semibold text-bad">
                  {cap(f.bp)} · {f.check}
                </span>
                <span className="min-w-0 break-words text-ink">{f.t}</span>
              </li>
            ))}
            {general.map((t, i) => (
              <li key={`g${i}`} className="flex gap-2 rounded-md bg-bad/5 px-3 py-2 text-xs leading-relaxed">
                <span className="shrink-0 font-semibold text-bad">All</span>
                <span className="min-w-0 break-words font-mono text-[11px] text-ink">{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      </div>
    </section>
  );
}
