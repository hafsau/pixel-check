import { usePath } from '../lib/router';
import { Mark } from './Logo';

export function SiteFooter() {
  const live = usePath().startsWith('/live/');
  return (
    <footer className="mt-section border-t border-line">
      <div className="page flex flex-col gap-3 py-8 text-xs text-ink-muted sm:flex-row sm:items-center sm:justify-between">
        <p className="flex items-start gap-2">
          <Mark size={16} className="mt-px text-accent" />
          <span>
            <span className="pixel text-[13px] text-ink">PixelCheck</span> · built on <strong className="font-semibold text-ink">Nebius Token Factory</strong> with{' '}
            <strong className="font-semibold text-ink">NVIDIA Nemotron</strong> models and Token Factory Sandboxes.
          </span>
        </p>
        <p>{live ? 'Live mode: this run called real models and sandboxes.' : 'Replay mode: recorded runs, no models called.'}</p>
      </div>
    </footer>
  );
}
