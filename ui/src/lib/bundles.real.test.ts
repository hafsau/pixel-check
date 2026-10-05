// Smoke test against the locally exported replay bundles (ui/public/runs/ is git-ignored dev data: skipped when absent).
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Interaction } from './types';
import { buildChecklist, buildTimeline } from './interactions';
import { normalizeIndex } from './bundle';

const RUNS = resolve(__dirname, '../../public/runs');
const ix = existsSync(RUNS) ? readdirSync(RUNS).filter((d) => existsSync(resolve(RUNS, d, 'interaction.json'))) : [];

describe.skipIf(!existsSync(resolve(RUNS, 'index.json')))('exported index', () => {
  it('parses and lists every interaction bundle on disk', () => {
    const idx = normalizeIndex(JSON.parse(readFileSync(resolve(RUNS, 'index.json'), 'utf8')));
    for (const d of ix) expect(idx.some((e) => e.id === d && e.type === 'interaction')).toBe(true);
  });
});

describe.skipIf(ix.length === 0)('exported interaction bundles', () => {
  it.each(ix)('%s: every per-breakpoint failure lands in a checklist row', (d) => {
    const b = JSON.parse(readFileSync(resolve(RUNS, d, 'interaction.json'), 'utf8')) as Interaction;
    const bps = b.breakpoints.map((x) => x.name);
    for (const v of b.variants) {
      expect(buildTimeline(v).filter((s) => s.kind === 'attempt')).toHaveLength(v.attempts.length);
      for (const a of v.attempts) {
        const { rows, general } = buildChecklist(a, bps);
        for (const g of general) expect(bps.some((bp) => g.startsWith(`${bp}: `))).toBe(false);
        if (a.pass) expect(rows.every((r) => bps.every((bp) => r.cells[bp]?.status !== 'fail'))).toBe(true);
        for (const bp of bps) for (const slot of ['base', 'open'] as const) expect(existsSync(resolve(RUNS, d, a.captures[bp]?.[slot] ?? 'missing'))).toBe(true);
      }
    }
  });
});
