// A tiny History-API router (no dependency). Routes are matched in App.tsx.
import { createContext, useContext, useEffect, useState, type AnchorHTMLAttributes, type MouseEvent } from 'react';

const PathCtx = createContext<string>('/');

export function RouterProvider({ children }: { children: React.ReactNode }) {
  const [path, setPath] = useState(() => window.location.pathname);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  return <PathCtx.Provider value={path}>{children}</PathCtx.Provider>;
}

export function usePath(): string {
  return useContext(PathCtx);
}

export function navigate(to: string) {
  const [pathPart, hash] = to.split('#');
  if (to !== window.location.pathname + window.location.search + window.location.hash) {
    window.history.pushState({}, '', to);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
  // Wait a frame so the new route has rendered before scrolling.
  requestAnimationFrame(() => {
    const el = hash ? document.getElementById(hash) : null;
    if (el) {
      el.scrollIntoView({ block: 'start' });
      (el as HTMLElement).focus?.({ preventScroll: true });
    } else if (pathPart) window.scrollTo({ top: 0 });
  });
}

/** Match "/run/:id/result" style patterns. Returns params or null. */
export function matchPath(pattern: string, path: string): Record<string, string> | null {
  const p = pattern.split('/').filter(Boolean);
  const a = path.split('/').filter(Boolean);
  if (p.length !== a.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(':')) params[p[i].slice(1)] = decodeURIComponent(a[i]);
    else if (p[i] !== a[i]) return null;
  }
  return params;
}

export function Link({ to, onClick, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) {
  const handle = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    navigate(to);
  };
  return <a href={to} onClick={handle} {...rest} />;
}
