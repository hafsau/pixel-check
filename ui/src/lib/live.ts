// Live mode client logic (orchestrator/api.py). Pure functions — the components only wire them to fetch and timers.

export type LiveBp = 'mobile' | 'tablet' | 'desktop';
export const LIVE_BPS: LiveBp[] = ['mobile', 'tablet', 'desktop'];
export const FRAME_SIZES: Record<LiveBp, [number, number]> = { mobile: [390, 844], tablet: [768, 1024], desktop: [1280, 800] };
export const MAX_FRAME_BYTES = 8 * 1024 * 1024; // api.MAX_BYTES
export const POLL_MS = 1500;
const MAX_NETWORK_ERRORS = 3;

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

// ------------------------------------------------------------------------------------------------ frames

export interface FrameFacts {
  type: string;
  name: string;
  size: number;
  /** Decoded pixel size; 0 when the browser could not decode the file. */
  width: number;
  height: number;
}

/** Client-side check mirroring the server's (api._check_png + MAX_BYTES). → message, or null when the frame is fine. */
export function validateFrame(bp: LiveBp, f: FrameFacts): string | null {
  const name = cap(bp);
  const isPng = f.type ? f.type === 'image/png' : /\.png$/i.test(f.name);
  if (!isPng) return `${name}: the frame must be a PNG image.`;
  if (f.size > MAX_FRAME_BYTES) return `${name}: the frame is larger than ${MAX_FRAME_BYTES / (1024 * 1024)} MB.`;
  if (!f.width || !f.height) return `${name}: the frame is not a readable PNG image.`;
  const [w, h] = FRAME_SIZES[bp];
  if (f.width !== w || f.height !== h) return `${name}: the frame must be exactly ${w}×${h} px (got ${f.width}×${f.height}).`;
  return null;
}

export function framesReady(frames: Partial<Record<LiveBp, 'ok' | 'error' | 'empty'>>, passcode: string): boolean {
  return LIVE_BPS.every((bp) => frames[bp] === 'ok') && passcode.trim().length > 0;
}

/** Decode a picked file to learn its pixel size (0×0 when it is not a decodable image). Browser only. */
export async function frameFacts(file: File): Promise<FrameFacts> {
  const base = { type: file.type, name: file.name, size: file.size };
  try {
    const bmp = await createImageBitmap(file);
    const out = { ...base, width: bmp.width, height: bmp.height };
    bmp.close();
    return out;
  } catch {
    return { ...base, width: 0, height: 0 };
  }
}

// ------------------------------------------------------------------------------------------------ API errors

/** FastAPI error body → the sentence shown to the user. status 0 = the request never got a response. */
export function apiErrorMessage(status: number, body: unknown): string {
  const raw = body && typeof body === 'object' ? (body as { detail?: unknown }).detail : undefined;
  const detail = Array.isArray(raw)
    ? raw
        .map((d) => {
          const loc = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== 'body').join('.') : '';
          return loc ? `${loc}: ${d?.msg ?? ''}` : String(d?.msg ?? '');
        })
        .join('; ')
    : typeof raw === 'string'
      ? raw
      : '';
  switch (status) {
    case 0:
      return 'Could not reach the PixelCheck server. Check your connection and try again.';
    case 403:
      return 'That passcode is not right. It is in the Devpost testing notes.';
    case 413:
    case 422:
      return detail ? cap(detail) : status === 413 ? 'A frame is larger than 8 MB.' : 'The frames were not accepted.';
    case 429:
      return 'The live-run limit is reached for now. Replays still work.';
    case 503:
      return 'Live mode is switched off right now. Replays still work.';
    case 404:
      return 'This run was not found. The server may have been restarted.';
    default:
      return `The server returned an error (${status}). Try again in a minute.`;
  }
}

// ------------------------------------------------------------------------------------------------ polling

export type LiveState = 'queued' | 'running' | 'done' | 'failed';
export type StageId = 'capture' | 'perceive' | 'compile' | 'bundle';

export interface LiveStatus {
  state: LiveState;
  stages: { stage: StageId | (string & {}); t: number }[];
  result?: { match: number | null; per_bp: Partial<Record<LiveBp, number>> | null; usd: number | null } | null;
  bundle?: string | null;
  error?: string;
  created?: number;
  source?: { url?: string } | null;
}

export interface PollState {
  phase: 'polling' | 'done' | 'failed' | 'offline';
  status: LiveStatus | null;
  networkErrors: number;
  error?: string;
}

export type PollEvent = { type: 'status'; status: LiveStatus } | { type: 'network-error' } | { type: 'not-found' } | { type: 'retry' };

export function initialPoll(): PollState {
  return { phase: 'polling', status: null, networkErrors: 0 };
}

export function pollReducer(s: PollState, e: PollEvent): PollState {
  if (e.type === 'retry') return s.phase === 'offline' ? { ...s, phase: 'polling', networkErrors: 0 } : s;
  if (s.phase === 'done' || s.phase === 'failed') return s;
  switch (e.type) {
    case 'status': {
      const st = e.status;
      if (st.state === 'done')
        return st.bundle
          ? { phase: 'done', status: st, networkErrors: 0 }
          : { phase: 'failed', status: st, networkErrors: 0, error: 'The run finished but produced no result bundle.' };
      if (st.state === 'failed') return { phase: 'failed', status: st, networkErrors: 0, error: st.error || 'The run failed.' };
      return { phase: 'polling', status: st, networkErrors: 0 };
    }
    case 'not-found':
      return { ...s, phase: 'failed', error: apiErrorMessage(404, null) };
    case 'network-error': {
      const n = s.networkErrors + 1;
      return { ...s, networkErrors: n, phase: n >= MAX_NETWORK_ERRORS ? 'offline' : 'polling' };
    }
  }
}

const CAPTURE = { id: 'capture' as const, label: 'Capturing the page' };
const STAGES: { id: StageId; label: string }[] = [
  { id: 'perceive', label: 'Reading the frames' },
  { id: 'compile', label: 'Compiling, rendering and scoring in the sandbox' },
  { id: 'bundle', label: 'Preparing the result' },
];

export type StageState = 'pending' | 'active' | 'done' | 'failed';

export function stageProgress(st: Pick<LiveStatus, 'state' | 'stages' | 'source'>): { id: StageId; label: string; state: StageState; t?: number }[] {
  const list = st.source?.url ? [CAPTURE, ...STAGES] : STAGES;
  const seen = list.map((s) => st.stages.find((x) => x.stage === s.id));
  const last = seen.reduce((acc, x, i) => (x ? i : acc), -1);
  return list.map((s, i) => {
    let state: StageState = 'pending';
    if (st.state === 'done') state = 'done';
    else if (st.state === 'running') state = i < Math.max(last, 0) ? 'done' : i === Math.max(last, 0) ? 'active' : 'pending';
    else if (st.state === 'failed') state = last < 0 ? (i === 0 ? 'failed' : 'pending') : i < last ? 'done' : i === last ? 'failed' : 'pending';
    return { ...s, state, t: seen[i]?.t };
  });
}

// ------------------------------------------------------------------------------------------------ URLs

export function apiBase(): string {
  return (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');
}

export function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
}

export function liveFilesBase(base: string, id: string): string {
  return joinUrl(base, `/api/runs/${encodeURIComponent(id)}/files/`);
}

/** A bundle-relative path (as stored in run.json) → URL under the run's files base; null for anything that leaves it. */
export function resolveAsset(filesBase: string, rel: string): string | null {
  if (!rel || /^[a-z][a-z0-9+.-]*:/i.test(rel) || rel.startsWith('/') || rel.startsWith('\\')) return null;
  const parts = rel.replace(/^\.\//, '').split('/');
  if (parts.some((p) => p === '..' || p === '')) return null;
  return filesBase + parts.map(encodeURIComponent).join('/');
}

// ------------------------------------------------------------------------------------------------ URL runs

const LOCAL_HOST = /^(localhost|.*\.localhost|.*\.local|.*\.internal|0\.0\.0\.0|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|169\.254\.\d+\.\d+|\[?::1\]?)$/i;

/** Friendly client-side check mirroring api._check_url (the server also resolves the host). → message or null. */
export function validatePageUrl(raw: string): string | null {
  const v = raw.trim();
  if (!v) return 'Enter the address of a public web page.';
  if (v.length > 2000) return 'The address is too long.';
  if (!/^[a-z][a-z0-9+.-]*:/i.test(v)) return 'Start the address with https:// — e.g. https://example.com/pricing.';
  if (!/^https?:/i.test(v)) return 'Only http:// and https:// pages can be captured.';
  let u: URL;
  try {
    u = new URL(v);
  } catch {
    return 'Enter a full address with a host name, e.g. https://example.com/pricing.';
  }
  if (!u.hostname) return 'Enter a full address with a host name, e.g. https://example.com/pricing.';
  if (u.username || u.password) return 'Remove the user name or password from the address.';
  if (u.port && u.port !== '80' && u.port !== '443') return 'Only standard ports (80 / 443) are supported.';
  if (LOCAL_HOST.test(u.hostname)) return 'Only public web pages can be captured — not local or private addresses.';
  return null;
}

export function urlReady(url: string, owns: boolean, passcode: string): boolean {
  return validatePageUrl(url) === null && owns && passcode.trim().length > 0;
}

const REFUSAL = /password or payment fields/i;

/** A failed run's error → what the progress page says. The login / checkout refusal is a decision, not a crash. */
export function failureNotice(error: string | undefined): { kind: 'refused' | 'error'; title: string; message: string } {
  if (error && REFUSAL.test(error)) return { kind: 'refused', title: 'This page was not rebuilt', message: cap(error) };
  return { kind: 'error', title: 'The run failed', message: error || 'The run failed.' };
}

export function runDuration(st: Pick<LiveStatus, 'source'> & Partial<LiveStatus>): string {
  return st.source?.url ? '2–7 minutes' : '45–90 seconds';
}

export function sourceHost(source: { url?: string } | null | undefined): string | null {
  if (!source?.url) return null;
  try {
    return new URL(source.url).hostname || null;
  } catch {
    return null;
  }
}
