import type { ModelCall, Run } from '../lib/types';
import { fmtInt, fmtUsd } from '../lib/format';
import { ModelName } from './ModelName';

/** Every model call made through Nebius Token Factory, with totals. */
export function AgentLog({ run }: { run: Run }) {
  const calls = run.calls;
  const t0 = calls.length ? Math.min(...calls.map((c) => c.t)) : 0;
  const sum = (f: (c: ModelCall) => number) => calls.reduce((a, c) => a + (f(c) || 0), 0);
  const roles = Object.entries(run.models ?? {});

  return (
    <section aria-labelledby="log-title" className="card card-pad">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="log-title" className="h2">
            Agent log
          </h2>
          <p className="mt-1 text-xs text-ink-muted">
            Every model call ran on <strong className="font-semibold text-ink">Nebius Token Factory</strong>.
          </p>
        </div>
        {roles.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            {roles.map(([role, id]) => (
              <div key={role} className="contents">
                <dt className="text-ink-muted">{role}</dt>
                <dd>
                  <ModelName id={id} />
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      <div className="mt-4 max-h-[28rem] overflow-auto rounded-md border border-line">
        <table className="table">
          <caption className="sr-only">Model calls: step, model, thinking mode, tokens in and out, cost, latency</caption>
          <thead className="sticky top-0 z-10">
            <tr>
              <th scope="col">+t</th>
              <th scope="col">Step</th>
              <th scope="col">Model</th>
              <th scope="col">Thinking</th>
              <th scope="col" className="text-right">In</th>
              <th scope="col" className="text-right">Out</th>
              <th scope="col" className="text-right">$</th>
              <th scope="col" className="text-right">Latency</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((c, i) => (
              <tr key={i} className="hover:bg-surface-2/60">
                <td className="font-mono text-[11px] text-ink-faint num">{(c.t - t0).toFixed(0)}s</td>
                <td className="font-medium">{c.step}</td>
                <td>
                  <ModelName id={c.model} />
                </td>
                <td className="text-ink-muted">{c.thinking ?? '—'}</td>
                <td className="text-right num">{fmtInt(c.in)}</td>
                <td className="text-right num">{fmtInt(c.out)}</td>
                <td className="text-right num">{fmtUsd(c.usd)}</td>
                <td className="text-right num">{c.latency_s?.toFixed(1)} s</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="sticky bottom-0 bg-surface-2">
            <tr>
              <td colSpan={4}>{calls.length} calls</td>
              <td className="text-right num">{fmtInt(sum((c) => c.in))}</td>
              <td className="text-right num">{fmtInt(sum((c) => c.out))}</td>
              <td className="text-right num">{fmtUsd(sum((c) => c.usd))}</td>
              <td className="text-right num">{sum((c) => c.latency_s).toFixed(0)} s</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
