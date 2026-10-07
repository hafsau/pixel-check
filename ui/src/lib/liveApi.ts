// fetch wrappers for the live API. The passcode only travels in the POST body; it is never stored or logged.
import { useEffect, useReducer, useRef } from 'react';
import { apiBase, apiErrorMessage, initialPoll, joinUrl, pollReducer, POLL_MS, type LiveBp, type LiveStatus, type PollState } from './live';
import { checkBundleUrl, checkFormData, parseCheck, type CheckBundle, type CheckDraft } from './check';

export interface Health {
  live: boolean;
  runs_left_today: number;
  runs_left_total: number;
}

async function body(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

export async function getHealth(): Promise<{ ok: true; health: Health } | { ok: false; message: string }> {
  try {
    const res = await fetch(joinUrl(apiBase(), '/api/health'), { cache: 'no-store' });
    if (!res.ok) return { ok: false, message: apiErrorMessage(res.status, await body(res)) };
    return { ok: true, health: (await res.json()) as Health };
  } catch {
    return { ok: false, message: apiErrorMessage(0, null) };
  }
}

export async function startRun(frames: Record<LiveBp, File>, passcode: string): Promise<{ ok: true; id: string } | { ok: false; status: number; message: string }> {
  const fd = new FormData();
  (Object.keys(frames) as LiveBp[]).forEach((bp) => fd.append(bp, frames[bp], `${bp}.png`));
  fd.append('passcode', passcode);
  try {
    const res = await fetch(joinUrl(apiBase(), '/api/runs'), { method: 'POST', body: fd });
    const b = await body(res);
    if (res.status !== 202 && !res.ok) return { ok: false, status: res.status, message: apiErrorMessage(res.status, b) };
    const id = (b as { id?: unknown } | null)?.id;
    if (typeof id !== 'string') return { ok: false, status: res.status, message: apiErrorMessage(res.status || 500, null) };
    return { ok: true, id };
  } catch {
    return { ok: false, status: 0, message: apiErrorMessage(0, null) };
  }
}

/** Polls GET /api/runs/{id} every POLL_MS until done / failed / offline. `retry()` resumes after going offline. */
export function useLivePoll(id: string): [PollState, () => void] {
  const [state, dispatch] = useReducer(pollReducer, undefined, initialPoll);
  const phase = useRef(state.phase);
  phase.current = state.phase;

  useEffect(() => {
    if (state.phase !== 'polling') return;
    let alive = true;
    const tick = async () => {
      try {
        const res = await fetch(joinUrl(apiBase(), `/api/runs/${encodeURIComponent(id)}`), { cache: 'no-store' });
        if (!alive) return;
        if (res.status === 404) dispatch({ type: 'not-found' });
        else if (!res.ok) dispatch({ type: 'network-error' });
        else dispatch({ type: 'status', status: (await res.json()) as LiveStatus });
      } catch {
        if (alive) dispatch({ type: 'network-error' });
      }
    };
    const delay = state.status == null && state.networkErrors === 0 ? 0 : POLL_MS;
    const t = window.setTimeout(tick, delay);
    return () => {
      alive = false;
      window.clearTimeout(t);
    };
  }, [id, state]);

  return [state, () => dispatch({ type: 'retry' })];
}

export async function startUrlRun(url: string, owns: boolean, passcode: string): Promise<{ ok: true; id: string } | { ok: false; status: number; message: string }> {
  const fd = new FormData();
  fd.append('url', url.trim());
  fd.append('owns', owns ? 'true' : 'false');
  fd.append('passcode', passcode);
  try {
    const res = await fetch(joinUrl(apiBase(), '/api/runs/url'), { method: 'POST', body: fd });
    const b = await body(res);
    if (!res.ok) return { ok: false, status: res.status, message: apiErrorMessage(res.status, b) };
    const id = (b as { id?: unknown } | null)?.id;
    if (typeof id !== 'string') return { ok: false, status: res.status, message: apiErrorMessage(500, null) };
    return { ok: true, id };
  } catch {
    return { ok: false, status: 0, message: apiErrorMessage(0, null) };
  }
}

/** Check mode: POST /api/checks (three frames + exactly one of url / code + owns + passcode). Same errors as live runs. */
export async function startCheck(frames: Record<LiveBp, File>, draft: Pick<CheckDraft, 'source' | 'url' | 'code' | 'owns' | 'passcode'>): Promise<{ ok: true; id: string } | { ok: false; status: number; message: string }> {
  try {
    const res = await fetch(joinUrl(apiBase(), '/api/checks'), { method: 'POST', body: checkFormData(frames, draft) });
    const b = await body(res);
    if (!res.ok) return { ok: false, status: res.status, message: apiErrorMessage(res.status, b) };
    const id = (b as { id?: unknown } | null)?.id;
    if (typeof id !== 'string') return { ok: false, status: res.status, message: apiErrorMessage(500, null) };
    return { ok: true, id };
  } catch {
    return { ok: false, status: 0, message: apiErrorMessage(0, null) };
  }
}

/** GET check.json for a finished check, parsed defensively. */
export async function getCheck(id: string, status: LiveStatus | null | undefined): Promise<CheckBundle> {
  const res = await fetch(checkBundleUrl(apiBase(), id, status?.bundle), { cache: 'no-store' });
  if (!res.ok) throw new Error(`The check result could not be loaded (${res.status}).`);
  return parseCheck(await res.json(), status?.result?.per_bp ?? null);
}
