import { mkdtempSync, mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { devIndex, publishedFile, shipRuns } from './publishedRuns';

function setup() {
  const root = mkdtempSync(join(tmpdir(), 'pc-ship-'));
  mkdirSync(join(root, 'dist/runs/dev-capture'), { recursive: true });
  writeFileSync(join(root, 'dist/runs/index.json'), '[{"id":"dev-capture"}]');
  writeFileSync(join(root, 'dist/runs/dev-capture/run.json'), '{}');
  mkdirSync(join(root, 'published/hafsausmani-home/c'), { recursive: true });
  writeFileSync(join(root, 'published/index.json'), '[{"id":"hafsausmani-home","source":"owned:hafsausmani.com"}]');
  writeFileSync(join(root, 'published/hafsausmani-home/run.json'), '{"id":"hafsausmani-home"}');
  return root;
}

describe('shipRuns', () => {
  it('drops the dev replays and ships the published ones as /runs', () => {
    const root = setup();
    shipRuns(join(root, 'dist'), join(root, 'published'), false);
    expect(existsSync(join(root, 'dist/runs/dev-capture'))).toBe(false);
    expect(JSON.parse(readFileSync(join(root, 'dist/runs/index.json'), 'utf8'))).toEqual([
      { id: 'hafsausmani-home', source: 'owned:hafsausmani.com' },
    ]);
    expect(existsSync(join(root, 'dist/runs/hafsausmani-home/run.json'))).toBe(true);
  });

  it('with no published folder ships no runs at all', () => {
    const root = setup();
    shipRuns(join(root, 'dist'), join(root, 'missing'), false);
    expect(existsSync(join(root, 'dist/runs'))).toBe(false);
  });

  it('PC_INCLUDE_RUNS keeps the dev replays (local previews only)', () => {
    const root = setup();
    shipRuns(join(root, 'dist'), join(root, 'published'), true);
    expect(existsSync(join(root, 'dist/runs/dev-capture/run.json'))).toBe(true);
  });
});

// Oct 12 (Hafsa): localhost should show what production shows; the dev replays stay one toggle away
describe('devIndex (npm run dev)', () => {
  it('lists the published runs first and marks every dev replay', () => {
    const idx = devIndex(
      [{ id: 'hafsausmani-home', source: 'owned:hafsausmani.com' }],
      [{ id: 'abl-plan-lambda' }, { id: 'hafsausmani-home', title: 'an older dev copy' }],
    );
    expect(idx).toEqual([
      { id: 'hafsausmani-home', source: 'owned:hafsausmani.com' },
      { id: 'abl-plan-lambda', dev: true },
    ]);
  });

  it('serves a published bundle\'s files from ui/published, everything else falls through', () => {
    const root = setup();
    expect(publishedFile(join(root, 'published'), '/runs/hafsausmani-home/run.json')).toBe(
      join(root, 'published/hafsausmani-home/run.json'),
    );
    expect(publishedFile(join(root, 'published'), '/runs/dev-capture/run.json')).toBeNull();
    expect(publishedFile(join(root, 'published'), '/runs/../../secret.env')).toBeNull();
    expect(publishedFile(join(root, 'published'), '/runs/hafsausmani-home/%2e%2e/%2e%2e/x')).toBeNull();
  });
});
