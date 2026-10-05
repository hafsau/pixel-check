import { usePath } from '../lib/router';

export function SiteFooter() {
  const live = usePath().startsWith('/live/');
  return (
    <footer className="mt-section border-t border-line">
      <div className="page flex flex-col gap-2 py-6 text-xs text-ink-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          Pixel-Check · built on <strong className="font-semibold text-ink">Nebius Token Factory</strong> with{' '}
          <strong className="font-semibold text-ink">NVIDIA Nemotron</strong> models and Token Factory Sandboxes.
        </p>
        <p>{live ? 'Live mode: this run called real models and sandboxes.' : 'Replay mode: recorded runs, no models called.'}</p>
      </div>
    </footer>
  );
}
