import { useEffect, useId, useState } from 'react';
import { cap } from '../lib/format';
import { IconAlert, IconCheck } from './Icons';

export type FrameState =
  | { status: 'empty' }
  | { status: 'ok'; file: File; url: string }
  | { status: 'error'; message: string; url?: string };

/** One PNG input that checks the image is exactly width × height (client-side only). */
export function FramePicker({
  bp,
  width,
  height,
  onChange,
}: {
  bp: string;
  width: number;
  height: number;
  onChange?: (s: FrameState) => void;
}) {
  const id = useId();
  const [state, setState] = useState<FrameState>({ status: 'empty' });

  useEffect(() => () => {
    if (state.status !== 'empty' && state.url) URL.revokeObjectURL(state.url);
  }, [state]);

  const set = (s: FrameState) => {
    setState(s);
    onChange?.(s);
  };

  const pick = (file: File | undefined) => {
    if (!file) return set({ status: 'empty' });
    if (file.type !== 'image/png') return set({ status: 'error', message: 'Must be a PNG file.' });
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const w = img.naturalWidth;
      const h = img.naturalHeight;
      if (w === width && h === height) set({ status: 'ok', file, url });
      else set({ status: 'error', message: `Is ${w}×${h}; must be exactly ${width}×${height}.`, url });
    };
    img.onerror = () => set({ status: 'error', message: 'Could not read this image.' });
    img.src = url;
  };

  const msgId = `${id}-msg`;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="flex items-baseline justify-between text-sm font-medium">
        <span>{cap(bp)}</span>
        <span className="font-mono text-[11px] text-ink-faint">
          {width}×{height}
        </span>
      </label>
      <div
        className="inset relative mx-auto flex items-center justify-center overflow-hidden border border-dashed border-line"
        style={{ aspectRatio: `${width} / ${height}`, width: `min(100%, calc(9rem * ${width / height}))` }}
      >
        {state.status !== 'empty' && state.url ? (
          <img src={state.url} alt={`${cap(bp)} frame preview`} className="h-full w-full object-contain" />
        ) : (
          <span className="text-[11px] text-ink-faint">PNG</span>
        )}
      </div>
      <input
        id={id}
        type="file"
        accept="image/png"
        aria-describedby={msgId}
        aria-invalid={state.status === 'error'}
        onChange={(e) => pick(e.target.files?.[0])}
        className="block w-full text-xs text-ink-muted file:mr-2 file:rounded-sm file:border file:border-line file:bg-surface file:px-2 file:py-1 file:text-xs file:font-medium file:text-ink hover:file:bg-surface-2"
      />
      <p id={msgId} className="min-h-[1rem] text-xs" aria-live="polite">
        {state.status === 'ok' && (
          <span className="inline-flex items-center gap-1 text-good">
            <IconCheck /> Size OK
          </span>
        )}
        {state.status === 'error' && (
          <span className="inline-flex items-center gap-1 text-bad">
            <IconAlert /> {state.message}
          </span>
        )}
      </p>
    </div>
  );
}
