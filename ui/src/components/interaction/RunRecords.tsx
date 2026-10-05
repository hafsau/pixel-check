import type { Interaction, Variant } from '../../lib/types';
import { fmtSecs, fmtUsd } from '../../lib/format';
import { writerName } from '../../lib/interactions';
import { PassPill } from '../PassPill';

/** Proof of the sandbox runs behind the selected writer, and every recorded repeat of the same configuration. */
export function RunRecords({ ix, v }: { ix: Interaction; v: Variant }) {
  const sets = ix.repeats;
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 [&>*]:min-w-0">
      <section aria-labelledby="sbx-title" className="card card-pad">
        <h2 id="sbx-title" className="h2">
          Sandbox runs
        </h2>
        <p className="mt-1 text-xs text-ink-muted">
          {writerName(v.writer)}: {v.sandbox.runs} runs in Token Factory Sandboxes, VM time {fmtSecs(v.sandbox.vm_s)}, wall {fmtSecs(v.sandbox.wall_s)}, {fmtUsd(v.sandbox.usd, 4)}.
        </p>
        <div className="relative mt-4 overflow-x-auto rounded-md border border-line">
          <table className="table">
            <caption className="sr-only">Sandbox operations for this writer</caption>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Status</th>
                <th scope="col" className="text-right">VM</th>
                <th scope="col" className="text-right">Wall</th>
                <th scope="col" className="text-right">$</th>
                <th scope="col">Operation</th>
              </tr>
            </thead>
            <tbody>
              {v.static && (
                <tr>
                  <td>Static page (reference)</td>
                  <td className="text-ink-muted">—</td>
                  <td className="text-right num">{fmtSecs(v.static.sandbox.vm_s)}</td>
                  <td className="text-right num">{fmtSecs(v.static.sandbox.wall_s)}</td>
                  <td className="text-right num">{fmtUsd(v.static.sandbox.usd)}</td>
                  <td className="text-ink-faint">—</td>
                </tr>
              )}
              {v.attempts.map((a) => (
                <tr key={a.attempt}>
                  <td>Attempt {a.attempt + 1} tests</td>
                  <td className="text-ink-muted">{a.sandbox?.status ?? '—'}</td>
                  <td className="text-right num">{fmtSecs(a.sandbox?.elapsed_s)}</td>
                  <td className="text-right num">{fmtSecs(a.sandbox?.wall_s)}</td>
                  <td className="text-right num">{fmtUsd(a.sandbox?.cost)}</td>
                  <td className="font-mono text-[11px] text-ink-muted">{a.sandbox?.op_id ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {sets.length > 0 && (
        <section aria-labelledby="rep-title" className="card card-pad">
          <h2 id="rep-title" className="h2">
            All recorded runs
          </h2>
          <p className="mt-1 text-xs text-ink-muted">Repeats of the same configuration. Captures were kept only for the run marked “shown”.</p>
          <div className="relative mt-4 max-h-[22rem] overflow-auto rounded-md border border-line">
            <table className="table">
              <caption className="sr-only">Recorded runs per writer</caption>
              <thead className="sticky top-0 z-10">
                <tr>
                  <th scope="col">Set</th>
                  <th scope="col">Writer</th>
                  <th scope="col">Result</th>
                  <th scope="col" className="text-right">Attempts</th>
                  <th scope="col" className="text-right">$ all-in</th>
                  <th scope="col" className="text-right">Wall</th>
                </tr>
              </thead>
              <tbody>
                {sets.flatMap((s) =>
                  s.runs.map((r) => (
                    <tr key={`${s.label}-${r.name}`} className={r.matches_variant === v.key ? 'bg-accent/5' : ''}>
                      <td className="text-ink-muted">
                        {s.label}
                        {r.matches_variant && <span className="chip ml-1.5">shown</span>}
                      </td>
                      <td>{writerName(s.writer)}</td>
                      <td>
                        <PassPill status={r.pass ? 'pass' : 'fail'} />
                      </td>
                      <td className="text-right num">
                        {r.pass && r.first_pass_attempt != null ? `passed at ${r.first_pass_attempt + 1}` : r.attempts}
                      </td>
                      <td className="text-right num">{fmtUsd(r.usd, 3)}</td>
                      <td className="text-right num">{fmtSecs(r.seconds)}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
