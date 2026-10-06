import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { buildPreviewDoc } from '../lib/previewDoc';

const MIN_W = 320;
const MAX_W = 1440;
const PRESETS = [
  { label: 'Mobile', w: 390 },
  { label: 'Tablet', w: 768 },
  { label: 'Desktop', w: 1280 },
];
/** Height of the preview viewport in CSS px (before scaling to fit). */
const VIEW_H = 800;

/**
 * Renders App.jsx in a sandboxed iframe whose width you can drag from 320 to 1440 px.
 * When the chosen width is wider than the page, the iframe is scaled down visually —
 * its layout width (and so Tailwind's breakpoints) stays the chosen width.
 */
export function LivePreview({ code, assetUrl }: { code: string; assetUrl?: (rel: string) => string }) {
  const [width, setWidth] = useState(390);
  const [avail, setAvail] = useState(1200);
  const [dragging, setDragging] = useState(false);
  const stage = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; w: number; scale: number } | null>(null);
  const doc = useMemo(() => buildPreviewDoc(code, { assetUrl }), [code, assetUrl]);

  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setAvail(Math.max(200, e.contentRect.width - 20)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const clamp = (w: number) => Math.round(Math.max(MIN_W, Math.min(MAX_W, w)));
  const scale = Math.min(1, avail / width);

  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, w: width, scale };
    setDragging(true);
  };
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (d) setWidth(clamp(d.w + (e.clientX - d.x) / d.scale));
  };
  const onUp = () => {
    drag.current = null;
    setDragging(false);
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 100 : 10;
    const map: Record<string, number> = { ArrowLeft: width - step, ArrowDown: width - step, ArrowRight: width + step, ArrowUp: width + step, Home: MIN_W, End: MAX_W };
    if (e.key in map) {
      e.preventDefault();
      setWidth(clamp(map[e.key]));
    }
  };

  return (
    <section aria-labelledby="preview-title" className="card card-pad">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="preview-title" className="h2">
            Live preview
          </h2>
          <p className="mt-1 text-xs text-ink-muted">The best candidate, rendered in your browser. Drag the handle to resize.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="seg" role="group" aria-label="Preset widths">
            {PRESETS.map((p) => (
              <button key={p.w} type="button" className="seg-item num" aria-pressed={width === p.w} onClick={() => setWidth(p.w)}>
                {p.label} {p.w}
              </button>
            ))}
          </div>
          <output className="mono-chip min-w-[5.5rem] justify-center" aria-live="polite">
            {width} px{scale < 1 ? ` · ${Math.round(scale * 100)}%` : ''}
          </output>
        </div>
      </div>

      <div ref={stage} className="inset mt-4 overflow-hidden p-2.5">
        <div className="relative" style={{ width: width * scale + 16, height: VIEW_H * scale }}>
          <div
            className="overflow-hidden rounded-sm border border-line bg-white"
            style={{ width, height: VIEW_H, transform: `scale(${scale})`, transformOrigin: 'top left' }}
          >
            <iframe
              title="Live preview of the generated App.jsx"
              srcDoc={doc}
              sandbox="allow-scripts"
              className="block h-full w-full border-0"
              style={{ pointerEvents: dragging ? 'none' : 'auto' }}
            />
          </div>
          <div
            role="slider"
            tabIndex={0}
            aria-label="Preview width"
            aria-valuemin={MIN_W}
            aria-valuemax={MAX_W}
            aria-valuenow={width}
            aria-valuetext={`${width} pixels`}
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
            onKeyDown={onKey}
            className="absolute top-0 flex h-full w-4 cursor-ew-resize touch-none items-center justify-center rounded-sm hover:bg-accent/10"
            style={{ left: width * scale }}
          >
            <span className={`h-14 w-1.5 rounded-pill ${dragging ? 'bg-accent' : 'bg-ink-muted'}`} aria-hidden="true" />
          </div>
        </div>
      </div>
    </section>
  );
}
