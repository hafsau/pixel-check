import type { Critique } from '../lib/types';
import { IconChevron } from './Icons';

/** Per round: the critic's diagnosis, the strategies it proposed, and the measured feedback it was given. */
export function CritiquePanel({ critiques, activeRound }: { critiques: Critique[]; activeRound: number }) {
  return (
    <section aria-labelledby="crit-title" className="card card-pad">
      <h2 id="crit-title" className="h2">
        Critiques
      </h2>
      <p className="mt-1 text-xs text-ink-muted">Before each round, the critic reads measured feedback on the current best and proposes different strategies.</p>
      {critiques.length === 0 ? (
        <p className="mt-4 text-sm text-ink-muted">No critiques in this run.</p>
      ) : (
        <ol className="mt-4 flex flex-col gap-2">
          {critiques.map((c, i) => (
            <li key={`${c.round}-${i}`}>
              <details
                className={`group rounded-md border bg-surface ${c.round === activeRound ? 'border-accent' : 'border-line'}`}
                open={i === 0 ? true : undefined}
              >
                <summary className="flex cursor-pointer list-none items-center gap-2 rounded-md px-3 py-2.5 text-sm [&::-webkit-details-marker]:hidden">
                  <span className="transition-transform group-open:rotate-90">
                    <IconChevron />
                  </span>
                  <span className="font-semibold">Round {c.round}</span>
                  {c.parent && (
                    <span className="text-xs text-ink-muted">
                      on <code className="font-mono">{c.parent}</code>
                    </span>
                  )}
                  {c.round === activeRound && <span className="chip ml-auto border-accent/30 bg-accent/10 text-accent-strong">Now playing</span>}
                </summary>
                <div className="flex flex-col gap-4 border-t border-line px-3 py-3">
                  {c.diagnosis && (
                    <div>
                      <h3 className="eyebrow">Diagnosis</h3>
                      <p className="mt-1 text-sm leading-relaxed">{c.diagnosis}</p>
                    </div>
                  )}
                  {c.strategies.length > 0 && (
                    <div>
                      <h3 className="eyebrow">Strategies</h3>
                      <ol className="mt-1 flex flex-col gap-1.5">
                        {c.strategies.map((s, j) => (
                          <li key={j}>
                            <details className="rounded-sm bg-surface-2">
                              <summary className="cursor-pointer px-2.5 py-1.5 text-sm font-medium">{s.title ?? `Strategy ${j + 1}`}</summary>
                              <p className="whitespace-pre-wrap px-2.5 pb-2.5 text-xs leading-relaxed text-ink-muted">{s.instructions}</p>
                            </details>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}
                  {c.feedback && (
                    <details>
                      <summary className="eyebrow cursor-pointer">Measured feedback</summary>
                      <pre className="mt-2 max-h-80 overflow-auto rounded-sm bg-surface-2 p-3 text-[11px] leading-relaxed text-ink-muted">{c.feedback}</pre>
                    </details>
                  )}
                </div>
              </details>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
