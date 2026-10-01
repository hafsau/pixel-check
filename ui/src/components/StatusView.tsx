/** Loading / error placeholders for data-driven pages. */
export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="page py-16 text-sm text-ink-muted" role="status" aria-live="polite">
      {label}
    </div>
  );
}

export function ErrorView({ title = 'Something went wrong', detail }: { title?: string; detail?: string }) {
  return (
    <div className="page py-16">
      <div className="card card-pad max-w-xl" role="alert">
        <h1 className="h2">{title}</h1>
        {detail && <p className="mt-2 font-mono text-xs text-ink-muted break-words">{detail}</p>}
      </div>
    </div>
  );
}
