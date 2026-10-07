import { cpSync, existsSync, rmSync } from 'node:fs';
import { join } from 'node:path';

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
