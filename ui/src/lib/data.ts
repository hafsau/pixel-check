import { useEffect, useState } from 'react';
import type { Group, IndexEntry, Interaction, Run } from './types';
import { normalizeIndex } from './bundle';

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

/** URL of a file inside a run bundle (paths in run.json are relative to the run folder). */
export function runAsset(runId: string, rel: string): string {
  return `${BASE}/runs/${encodeURIComponent(runId)}/${rel}`;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url}`);
  return (await res.json()) as T;
}

export async function getText(url: string): Promise<string> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url}`);
  return res.text();
}

export type Load<T> = { status: 'loading' } | { status: 'error'; error: string } | { status: 'ready'; data: T };

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]): Load<T> {
  const [state, setState] = useState<Load<T>>({ status: 'loading' });
  useEffect(() => {
    let alive = true;
    setState({ status: 'loading' });
    fn().then(
      (data) => alive && setState({ status: 'ready', data }),
      (e: unknown) => alive && setState({ status: 'error', error: e instanceof Error ? e.message : String(e) }),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export function useRunIndex(): Load<IndexEntry[]> {
  return useLoad(async () => normalizeIndex(await getJson<unknown>(`${BASE}/runs/index.json`)), []);
}

export function useInteraction(id: string): Load<Interaction> {
  return useLoad(() => getJson<Interaction>(runAsset(id, 'interaction.json')), [id]);
}

export function useGroup(id: string): Load<Group> {
  return useLoad(() => getJson<Group>(runAsset(id, 'group.json')), [id]);
}

export function useRun(id: string): Load<Run> {
  return useLoad(() => getJson<Run>(runAsset(id, 'run.json')), [id]);
}

export function useText(url: string | null): Load<string> {
  return useLoad(() => (url ? getText(url) : Promise.resolve('')), [url]);
}
