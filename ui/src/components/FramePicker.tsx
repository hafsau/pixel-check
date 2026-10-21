import { useEffect, useId, useRef, useState } from 'react';
import { cap } from '../lib/format';
import { frameFacts, validateFrame, type FrameFacts, type LiveBp } from '../lib/live';
import { IconAlert, IconCheck } from './Icons';

export type FrameState =
  | { status: 'empty' }
  | { status: 'checking'; url: string }
  | { status: 'ok'; file: File; url: string; facts: FrameFacts }
  | { status: 'error'; message: string; url?: string };

/** One frame input, checked in the browser like the server checks it (PNG / JPEG / WebP, ≤ 8 MB, 320–1600 px wide,
 *  any height), with a preview. width / height: the typical export, for the empty slot's shape only. */
export function FramePicker({ bp, width, height, onChange, preset }: { bp: LiveBp; width: number; height: number; onChange?: (s: FrameState) => void; preset?: File | null }) {
  const id = useId();
  const [state, setState] = useState<FrameState>({ status: 'empty' });
  const urlRef = useRef<string | null>(null);
  const seq = useRef(0);

  useEffect(() => () => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
  }, []);

  const set = (s: FrameState) => {
    setState(s);
    onChange?.(s);
  };

  const pick = async (file: File | undefined) => {
    const n = ++seq.current;
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
    if (!file) return set({ status: 'empty' });
    const url = URL.createObjectURL(file);
    urlRef.current = url;
    set({ status: 'checking', url });
    const facts = await frameFacts(file);
    if (n !== seq.current) return; // a newer pick replaced this one
    const msg = validateFrame(bp, facts);
    set(msg ? { status: 'error', message: msg, url: facts.width ? url : undefined } : { status: 'ok', file, url, facts });
  };

  // a file handed in by the page ("Try the example") is checked exactly like a picked one
  useEffect(() => {
    if (preset) void pick(preset);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset]);

  const msgId = `${id}-msg`;
  const url = state.status !== 'empty' ? state.url : undefined;
  // the slot takes the picked frame's own shape (a full-page export is tall), capped so a page stays a thumbnail
  const [sw, sh] = state.status === 'ok' ? [state.facts.width, Math.min(state.facts.height, state.facts.width * 2.4)] : [width, height];
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="flex items-baseline justify-between text-sm font-medium">
        <span>{cap(bp)}</span>
        <span className="font-mono text-[11px] text-ink-faint">
          PNG · JPG · WebP, any size
        </span>
      </label>
      <div
        className={`inset relative mx-auto flex items-center justify-center overflow-hidden border ${state.status === 'error' ? 'border-bad/50' : state.status === 'ok' ? 'border-good/40' : 'border-dashed border-line'}`}
        style={{ aspectRatio: `${sw} / ${sh}`, width: `min(100%, calc(9rem * ${sw / sh}))` }}
      >
        {url ? <img src={url} alt={`${cap(bp)} frame preview`} className="h-full w-full object-cover object-top" /> : <span className="text-[11px] text-ink-faint">No frame yet</span>}
      </div>
      <input
        id={id}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        aria-describedby={msgId}
        aria-invalid={state.status === 'error'}
        onChange={(e) => void pick(e.target.files?.[0])}
        className="block w-full text-xs text-ink-muted file:mr-2 file:rounded-sm file:border file:border-line file:bg-surface file:px-2 file:py-1 file:text-xs file:font-medium file:text-ink hover:file:bg-surface-2"
      />
      <p id={msgId} className="min-h-[1rem] text-xs" aria-live="polite">
        {state.status === 'checking' && <span className="text-ink-muted">Checking…</span>}
        {state.status === 'ok' && (
          <span className="inline-flex items-center gap-1 text-good">
            <IconCheck /> {state.facts.width}×{state.facts.height}
          </span>
        )}
        {state.status === 'error' && (
          <span className="inline-flex items-start gap-1 text-bad">
            <IconAlert /> {state.message}
          </span>
        )}
      </p>
    </div>
  );
}
