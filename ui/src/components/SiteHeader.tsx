import { Link } from '../lib/router';
import { ThemeToggle } from './ThemeToggle';
import { Logo } from './Logo';

export function SiteHeader() {
  return (
    <header className="border-b border-line/70 bg-bg/85 backdrop-blur supports-[backdrop-filter]:bg-bg/70">
      <div className="page flex h-14 items-center justify-between gap-4">
        <Link to="/" className="flex items-center rounded-sm" aria-label="PixelCheck — home">
          <Logo />
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1">
          <Link to="/#how" className="btn-ghost hidden md:inline-flex">
            How it works
          </Link>
          <Link to="/#runs" className="btn-ghost hidden sm:inline-flex">
            Runs
          </Link>
          <Link to="/#live" className="btn-ghost hidden sm:inline-flex">
            Live run
          </Link>
          <Link to="/check" className="btn-ghost">
            <span className="sm:hidden">Check</span>
            <span className="hidden sm:inline">Check a build</span>
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
