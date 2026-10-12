// Render free sleeps after 15 idle minutes; the first request then waits ~30–60 s or fails while the server starts.
// wakeHealth retries the health check and says "waking" instead of "unreachable" (Oct 8, written before the code).
import { describe, expect, it } from 'vitest';
import { wakeHealth, type HealthTry } from './wake';

const health = { live: true, runs_left_today: 9, runs_left_total: 30 };

function harness(tries: (HealthTry | 'slow')[]) {
  let now = 0;
  const events: string[] = [];
  const sleep = async (ms: number) => {
    now += ms;
  };
  const fetchHealth = async (): Promise<HealthTry> => {
    const t = tries.shift() ?? { ok: false, status: 0, message: 'down' };
    if (t === 'slow') {
      now += 4000;
      return { ok: true, health };
    }
    now += 100;
    return t;
  };
  return { events, opts: { fetchHealth, sleep, clock: () => now, onWaking: () => events.push('waking') } };
}

describe('wakeHealth', () => {
  it('returns at once when the server is awake', async () => {
    const h = harness([{ ok: true, health }]);
    expect(await wakeHealth(h.opts)).toEqual({ ok: true, health });
    expect(h.events).toEqual([]);
  });

  it('retries while the server wakes (network error, 502, 503) and reports waking once', async () => {
    const h = harness([
      { ok: false, status: 0, message: 'x' },
      { ok: false, status: 502, message: 'x' },
      { ok: false, status: 503, message: 'x' },
      { ok: true, health },
    ]);
    expect(await wakeHealth(h.opts)).toEqual({ ok: true, health });
    expect(h.events).toEqual(['waking']);
  });

  it('gives up after the deadline as unreachable', async () => {
    const h = harness([]);
    const r = await wakeHealth({ ...h.opts, deadlineMs: 20000 });
    expect(r.ok).toBe(false);
    expect(h.events).toEqual(['waking']);
  });

  it('does not retry a real answer such as 404 or 500', async () => {
    const h = harness([{ ok: false, status: 500, message: 'boom' }, { ok: true, health }]);
    expect(await wakeHealth(h.opts)).toEqual({ ok: false, status: 500, message: 'boom' });
    expect(h.events).toEqual([]);
  });
});
