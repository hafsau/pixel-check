import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { FittedFrame, FrameImage } from './FittedFrame';

/** Draggable before/after slider: design on the left of the handle, render on the right. */
export function CompareSlider({
  design,
  render,
  width,
  height,
  label,
}: {
  design: string;
  render: string;
  width: number;
  height: number;
  label: string;
}) {
  const [pos, setPos] = useState(50);
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const fromX = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r || r.width === 0) return;
    setPos(Math.max(0, Math.min(100, ((clientX - r.left) / r.width) * 100)));
  };
  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    dragging.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    fromX(e.clientX);
  };
  const onMove = (e: PointerEvent<HTMLDivElement>) => dragging.current && fromX(e.clientX);
  const onUp = () => (dragging.current = false);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const big = e.shiftKey ? 10 : 2;
    const map: Record<string, number> = { ArrowLeft: pos - big, ArrowRight: pos + big, ArrowDown: pos - big, ArrowUp: pos + big, Home: 0, End: 100, PageDown: pos - 10, PageUp: pos + 10 };
    if (e.key in map) {
      e.preventDefault();
      setPos(Math.max(0, Math.min(100, map[e.key])));
    }
  };

  return (
    <FittedFrame width={width} height={height}>
      <div ref={ref} className="absolute inset-0 cursor-ew-resize touch-none select-none" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}>
        <FrameImage src={design} alt="" />
        <FrameImage src={render} alt="" style={{ clipPath: `inset(0 0 0 ${pos}%)` }} />
        <span className="pointer-events-none absolute left-1.5 top-1.5 rounded-sm bg-ink/70 px-1 text-[10px] font-medium text-bg">Design</span>
        <span className="pointer-events-none absolute right-1.5 top-1.5 rounded-sm bg-ink/70 px-1 text-[10px] font-medium text-bg">Render</span>
        <div className="pointer-events-none absolute inset-y-0 w-px bg-accent" style={{ left: `${pos}%` }} aria-hidden="true" />
        <div
          role="slider"
          tabIndex={0}
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(pos)}
          aria-valuetext={`${Math.round(pos)}% design, ${100 - Math.round(pos)}% render`}
          onKeyDown={onKey}
          className="absolute top-1/2 h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-pill border-2 border-accent bg-surface shadow-card"
          style={{ left: `${pos}%` }}
        />
      </div>
    </FittedFrame>
  );
}
