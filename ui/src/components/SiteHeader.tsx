import { Link } from '../lib/router';
import { ThemeToggle } from './ThemeToggle';

export function SiteHeader() {
  return (
    <header className="border-b border-line bg-surface/80 backdrop-blur supports-[backdrop-filter]:bg-surface/70">
      <div className="page flex h-14 items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2 rounded-sm font-semibold tracking-tight">
          <Logo />
          <span>Pixel-Check</span>
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1">
          <Link to="/#runs" className="btn-ghost hidden sm:inline-flex">
            Runs
          </Link>
          <Link to="/#live" className="btn-ghost hidden sm:inline-flex">
            Live run
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}

function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" className="fill-ink" />
      <rect x="7" y="9" width="5" height="14" rx="1.5" className="fill-bg" />
      <rect x="14" y="9" width="11" height="9" rx="1.5" className="fill-bg" />
      <rect x="14" y="20" width="11" height="3" rx="1.5" className="fill-good" />
    </svg>
  );
}
