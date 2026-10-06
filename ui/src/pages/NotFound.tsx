import { Link } from '../lib/router';

export function NotFound() {
  return (
    <div className="page py-20">
      <h1 className="h2">Page not found</h1>
      <p className="mt-2 text-sm text-ink-muted">
        <Link to="/" className="text-accent-strong underline underline-offset-2">
          Back to runs
        </Link>
      </p>
    </div>
  );
}
