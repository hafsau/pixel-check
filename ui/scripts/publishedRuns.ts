import { cpSync, existsSync, rmSync, statSync } from 'node:fs';
import { join, resolve, sep } from 'node:path';

/**
 * What a production build serves under /runs: the dev replays in public/runs (third-party captures, git-ignored)
 * are dropped and the bundles published into ui/published/ (tools/publish_run.py — owned sites or original designs,
 * committed) take their place. includeDev keeps the dev replays (PC_INCLUDE_RUNS=1: local previews only).
 */
export function shipRuns(dist: string, published: string, includeDev: boolean): void {
  if (includeDev) return;
  const runs = join(dist, 'runs');
  rmSync(runs, { recursive: true, force: true });
  if (existsSync(join(published, 'index.json'))) cpSync(published, runs, { recursive: true });
}

type Entry = { id: string; [k: string]: unknown };

/**
 * npm run dev: /runs/index.json = the published runs (what production shows) followed by the dev replays, each
 * marked `dev: true` so the web app hides them until "Show dev runs" is on. A published id wins over a dev copy.
 */
export function devIndex(published: Entry[], dev: Entry[]): Entry[] {
  const ids = new Set(published.map((e) => e.id));
  return [...published, ...dev.filter((e) => !ids.has(e.id)).map((e) => ({ ...e, dev: true }))];
}

/** The file under ui/published/ for a /runs/<id>/... URL in dev, or null (then public/runs serves it). */
export function publishedFile(published: string, url: string): string | null {
  let path: string;
  try {
    path = decodeURIComponent(url.split('?')[0]);
  } catch {
    return null;
  }
  const m = path.match(/^\/runs\/([a-z0-9][a-z0-9-]{0,63})\/(.+)$/);
  if (!m || m[2].split('/').some((p) => p === '..' || p === '.' || p === '')) return null;
  const file = resolve(published, m[1], m[2]);
  if (!file.startsWith(resolve(published) + sep) || !existsSync(file) || !statSync(file).isFile()) return null;
  return file;
}
