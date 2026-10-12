// The live server runs on Render's free plan: it sleeps after 15 idle minutes, and the first request then waits
// ~30–60 s or fails (no answer, 502/503) while it starts. Retry the health check and say "waking", not "unreachable".
import type { Health } from './liveApi';

export type HealthTry = { ok: true; health: Health } | { ok: false; status: number; message: string };

const WAKING = new Set([0, 502, 503, 504]);

export interface WakeOptions {
  fetchHealth: () => Promise<HealthTry>;
  onWaking?: () => void;
  deadlineMs?: number;
  retryMs?: number;
  slowMs?: number;
  sleep?: (ms: number) => Promise<void>;
  clock?: () => number;
  after?: (ms: number, fn: () => void) => () => void;
}

export async function wakeHealth({
  fetchHealth,
  onWaking = () => {},
  deadlineMs = 90_000,
  retryMs = 4_000,
  slowMs = 3_000,
  sleep = (ms) => new Promise((r) => setTimeout(r, ms)),
  clock = () => Date.now(),
  after = (ms, fn) => {
    const t = setTimeout(fn, ms);
    return () => clearTimeout(t);
  },
}: WakeOptions): Promise<HealthTry> {
  const start = clock();
  let waking = false;
  const wake = () => {
    if (!waking) {
      waking = true;
      onWaking();
    }
  };
  for (;;) {
    const cancel = after(slowMs, wake); // a held request: Render answers once the server is up
    const r = await fetchHealth();
    cancel();
    if (r.ok || !WAKING.has(r.status) || clock() - start >= deadlineMs) return r;
    wake();
    await sleep(retryMs);
  }
}
