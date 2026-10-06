import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { prefersReducedMotion } from '../../lib/theme';
import { Link, navigate } from '../../lib/router';
import { useRunIndex } from '../../lib/data';
import { bestReplayHref, type CellState, type StripCell } from '../../lib/viz';
import {
  RULER_MARKS,
  SWEEP_CELLS,
  SWEEP_MAX,
  SWEEP_MIN,
  SWEEP_MS,
  cellIndex,
  crossedCells,
  initialSweep,
  measureLayout,
  nextPhase,
  sliderKey,
  sweepCaption,
  sweepWidth,
  valueText,
  type Measure,
  type Phase,
  type Variant,
} from '../../lib/sweep';
import { cellState } from '../../lib/viz';
import { WidthStrip } from '../viz/WidthStrip';
import { IconArrowRight, IconPause, IconPlay } from '../Icons';
import { DemoPage } from './DemoPage';

const pending = (): StripCell[] => SWEEP_CELLS.map((width) => ({ width, state: 'pending' as CellState }));

/** Measure the demo inside `frame` right now: every [data-m] box in the frame's own (unscaled) CSS px. */
function measureFrame(frame: HTMLElement): Measure {
  const fr = frame.getBoundingClientRect();
  const k = fr.width / (frame.offsetWidth || 1);
  const boxes = Array.from(frame.querySelectorAll<HTMLElement>('[data-m]')).map((el) => {
    const r = el.getBoundingClientRect();
    return { id: el.dataset.m!, group: el.dataset.g ?? null, left: (r.left - fr.left) / k, right: (r.right - fr.left) / k, top: (r.top - fr.top) / k, bottom: (r.bottom - fr.top) / k };
  });
  return measureLayout({ left: 0, right: frame.offsetWidth }, boxes);
}

function markOffenders(frame: HTMLElement, ids: string[]) {
  frame.querySelectorAll<HTMLElement>('[data-m]').forEach((el) => el.toggleAttribute('data-offender', ids.includes(el.dataset.m!)));
}

const detail = (m: Measure) => (m.overflow > 0 ? `overflow ${m.overflow} px` : m.overlaps.length ? `${m.overlaps.length} overlap${m.overlaps.length > 1 ? 's' : ''}` : undefined);

/**
 * "The Sweep": a frame whose width runs 360 → 1600 → 360 px over an original demo page, measuring it live at each
 * cell width (overflow / overlap of its boxes) and filling the heat strip. Pass 1 = the "before" demo with a real
 * overflow at 1104 px; pass 2 = the fixed demo. Then (or on any interaction) the handle is the user's: drag it, or
 * focus it and use the arrow keys. Reduced motion: no autoplay, a static frame at 768 px, the strip measured at once.
 */
export function HeroSweep() {
  const idx = useRunIndex();
  const seeRun = idx.status === 'ready' ? bestReplayHref(idx.data) : '/#runs';
  return (
    <section aria-labelledby="hero-title" className="pt-10 sm:pt-16">
      <h1 id="hero-title" className="display text-[40px] sm:text-6xl lg:text-[84px]">
        <span className="block">Designed once.</span> <span className="block text-ink-muted">Verified everywhere.</span>
      </h1>
      <div className="mt-5 flex flex-col gap-5 sm:mt-6 md:flex-row md:items-end md:justify-between">
        <p className="max-w-lg text-base text-ink-muted sm:text-lg">Three frames in, one responsive React + Tailwind codebase out — rendered, measured and scored at every width.</p>
        <div className="flex shrink-0 flex-wrap gap-2.5">
          <a href="/#live" className="btn-primary btn-lg" onClick={(e) => (e.preventDefault(), navigate('/#live'))}>
            Try it live <IconArrowRight />
          </a>
          <Link to={seeRun} className="btn btn-lg">
            See a run
          </Link>
        </div>
      </div>
      <SweepStage />
    </section>
  );
}

function SweepStage() {
  const reduced = useMemo(() => prefersReducedMotion(), []);
  const init = useMemo(() => initialSweep(reduced), [reduced]);
  const [phase, setPhase] = useState<Phase>(init.phase);
  const [variant, setVariant] = useState<Variant>(init.variant);
  const [width, setWidth] = useState(init.width);
  const [playing, setPlaying] = useState(init.autoplay);
  const [cells, setCells] = useState<StripCell[]>(pending);
  const [stageW, setStageW] = useState(0);
  const [settling, setSettling] = useState(false);

  const stageRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const clock = useRef({ t: 0, last: 0, prevW: SWEEP_MIN - 1 });
  const visible = useRef(true);
  const goingUp = useRef(true);
  const [live, setLive] = useState<CellState>('pending');
  const renderedW = useRef(width);
  renderedW.current = width;

  // stage width → scale (the whole 0–1600 px ruler fits the stage)
  useLayoutEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setStageW(e.contentRect.width));
    ro.observe(el);
    setStageW(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  const k = stageW ? stageW / SWEEP_MAX : 0;
  const displayH = stageW < 640 ? 240 : 440;
  const frameH = k ? Math.round(displayH / k) : 600;

  /** Measure at an exact width (imperatively), then put the rendered width back. */
  const measureAt = useCallback((w: number): Measure | null => {
    const f = frameRef.current;
    if (!f) return null;
    f.style.width = `${w}px`;
    const m = measureFrame(f);
    f.style.width = `${renderedW.current}px`;
    return m;
  }, []);

  const record = useCallback((updates: { i: number; m: Measure }[]) => {
    if (!updates.length) return;
    setCells((cs) => {
      const next = cs.slice();
      for (const { i, m } of updates) next[i] = { width: SWEEP_CELLS[i], state: cellState(m), detail: detail(m) };
      return next;
    });
  }, []);

  const cellsRef = useRef(cells);
  cellsRef.current = cells;

  // pause autoplay while the stage is off screen
  useEffect(() => {
    const el = stageRef.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([e]) => (visible.current = e.isIntersecting), { threshold: 0.2 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // autoplay: advance the clock, measure every cell the frame grows past
  useEffect(() => {
    if (!playing || phase === 'interactive' || !k) return;
    let raf = 0;
    clock.current.last = performance.now();
    const tick = (now: number) => {
      const c = clock.current;
      const dt = Math.min(64, now - c.last);
      c.last = now;
      if (visible.current) c.t += dt;
      if (c.t >= SWEEP_MS) {
        const np = nextPhase(phase);
        c.t = 0;
        c.prevW = SWEEP_MIN - 1;
        if (np === 'after') {
          setVariant('after');
          setCells(pending());
          setPhase('after');
        } else {
          // settle on 1280 px and hand the handle over
          setPhase('interactive');
          setPlaying(false);
          setSettling(true);
          setWidth(1280);
          window.setTimeout(() => setSettling(false), 1200); // in case transitionend never fires (hidden tab)
        }
        return;
      }
      const w = sweepWidth(c.t);
      const f = frameRef.current;
      const crossed = crossedCells(c.prevW, w);
      if (f && crossed.length) {
        const ups = crossed.map((i) => ({ i, m: measureAt(SWEEP_CELLS[i])! }));
        record(ups);
        const last = ups[ups.length - 1].m;
        markOffenders(f, last.offenders);
      } else if (f && w < c.prevW) markOffenders(f, []); // shrinking: nothing new is measured this pass
      goingUp.current = w >= c.prevW;
      c.prevW = Math.max(c.prevW, w);
      setWidth(w);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, phase, k, measureAt, record]);

  // interactive: measure the width under the handle, its cell, and any cell still pending (reduced motion, a new
  // variant, or a sweep interrupted half-way) — all real measurements of the demo as rendered now
  useLayoutEffect(() => {
    if (phase !== 'interactive' || settling || !frameRef.current || !k) return;
    const m = measureFrame(frameRef.current);
    markOffenders(frameRef.current, m.offenders);
    setLive(cellState(m));
    const here = cellIndex(width);
    const todo = SWEEP_CELLS.map((_, i) => i).filter((i) => i === here || cellsRef.current[i].state === 'pending');
    record(todo.map((i) => ({ i, m: measureAt(SWEEP_CELLS[i])! })).filter((u) => u.m));
  }, [phase, width, variant, k, settling, record, measureAt]);

  const takeOver = () => {
    if (phase !== 'interactive') {
      setPhase('interactive');
      setPlaying(false);
    }
    setSettling(false);
  };

  const setVariantInteractive = (v: Variant) => {
    takeOver();
    setVariant(v);
    setCells(pending()); // re-measured by the effect above, for the new variant
  };

  const replay = () => {
    clock.current = { t: 0, last: performance.now(), prevW: SWEEP_MIN - 1 };
    if (frameRef.current) markOffenders(frameRef.current, []);
    setSettling(false);
    setVariant('before');
    setCells(pending());
    setWidth(SWEEP_MIN);
    setPhase('before');
    setPlaying(true);
  };

  const fromPointer = (clientX: number) => {
    const r = stageRef.current!.getBoundingClientRect();
    return Math.round(Math.max(SWEEP_MIN, Math.min(SWEEP_MAX, (clientX - r.left) / k)));
  };
  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (!k || e.button !== 0) return;
    takeOver();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    setWidth(fromPointer(e.clientX));
    document.getElementById('sweep-handle')?.focus({ preventScroll: true });
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!(e.currentTarget as HTMLElement).hasPointerCapture(e.pointerId)) return;
    setWidth(fromPointer(e.clientX));
  };
  const onKey = (e: KeyboardEvent) => {
    const v = sliderKey(width, e.key);
    if (v == null) return;
    e.preventDefault();
    takeOver();
    setWidth(v);
  };

  const hereState: CellState = phase === 'interactive' ? (settling ? 'pending' : live) : goingUp.current ? (cells[cellIndex(width)]?.state ?? 'pending') : 'pending';
  const caption = sweepCaption(phase === 'interactive' ? (variant === 'before' ? 'before' : 'after') : phase, cells);
  const failing = hereState !== 'pass' && hereState !== 'pending';
  const x = width * k;

  return (
    <div className="card mt-10 overflow-hidden p-0 shadow-lift sm:mt-14">
      {/* top bar: what this is + controls */}
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-line px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="mono-chip border-accent/40 bg-accent/10 text-accent-strong">demo</span>
          <p className="truncate text-sm font-medium" aria-live={playing ? 'off' : 'polite'}>
            {caption}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="seg" role="group" aria-label="Demo page version">
            <button type="button" className="seg-item" aria-pressed={variant === 'before'} onClick={() => setVariantInteractive('before')}>
              Before
            </button>
            <button type="button" className="seg-item" aria-pressed={variant === 'after'} onClick={() => setVariantInteractive('after')}>
              After fix
            </button>
          </div>
          {phase === 'interactive' ? (
            !reduced && (
              <button type="button" className="btn h-[34px] min-h-0 px-2.5 text-xs" onClick={replay}>
                <IconPlay /> Replay
              </button>
            )
          ) : (
            <button type="button" className="btn h-[34px] min-h-0 px-2.5 text-xs" onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause the sweep' : 'Play the sweep'}>
              {playing ? <IconPause /> : <IconPlay />} {playing ? 'Pause' : 'Play'}
            </button>
          )}
        </div>
      </div>

      <div className="bg-bg/60 px-4 pb-5 pt-4 sm:px-6 sm:pb-6">
        <div ref={stageRef} className="relative select-none touch-pan-y" onPointerDown={onPointerDown} onPointerMove={onPointerMove}>
          {/* ruler */}
          <div className="relative h-9 cursor-ew-resize" aria-hidden="true">
            <div className="absolute inset-x-0 bottom-0 h-px bg-line" />
            {k > 0 &&
              Array.from({ length: SWEEP_MAX / 100 + 1 }, (_, i) => i * 100).map((t) => (
                <span key={t} className={`absolute bottom-0 w-px ${t % 400 === 0 ? 'h-2 bg-ink-faint/60' : 'h-1 bg-ink-faint/40'}`} style={{ left: t * k }} />
              ))}
            {k > 0 &&
              RULER_MARKS.map((m) => (
                <span key={m} className="absolute bottom-2.5 -translate-x-1/2 font-mono text-[10px] text-ink-faint num last:-translate-x-full" style={{ left: m * k }}>
                  {m}
                </span>
              ))}
          </div>

          {/* handle: a slider on the frame's right edge */}
          {k > 0 && (
            <div
              id="sweep-handle"
              role="slider"
              tabIndex={0}
              aria-label="Demo frame width"
              aria-valuemin={SWEEP_MIN}
              aria-valuemax={SWEEP_MAX}
              aria-valuenow={Math.round(width)}
              aria-valuetext={valueText(width, hereState)}
              aria-describedby="sweep-help"
              onKeyDown={onKey}
              className={`group absolute top-0 z-10 -ml-px flex h-[calc(100%+4px)] w-0 cursor-ew-resize justify-center rounded-sm outline-none focus-visible:ring-0 focus-visible:ring-offset-0 ${settling ? 'transition-[left] duration-1000 ease-out' : ''}`}
              style={{ left: x }}
            >
              <span className={`absolute top-1 whitespace-nowrap rounded-pill px-2 py-0.5 font-mono text-[11px] font-medium num shadow-card group-focus-visible:ring-2 group-focus-visible:ring-accent group-focus-visible:ring-offset-2 group-focus-visible:ring-offset-bg ${failing ? 'bg-accent text-accent-ink' : 'bg-ink text-bg'} ${x < 40 ? 'translate-x-[45%]' : x > stageW - 40 ? '-translate-x-[45%]' : ''}`}>
                {Math.round(width)} px{failing ? ` · ${hereState}` : ''}
              </span>
              <span className={`absolute bottom-0 top-8 w-0.5 ${failing ? 'bg-accent' : 'bg-ink'}`} />
              <span className="absolute top-8 h-3 w-3 -translate-y-1/2 rotate-45 rounded-[2px] bg-ink group-focus-visible:ring-2 group-focus-visible:ring-accent group-focus-visible:ring-offset-2 group-focus-visible:ring-offset-bg" />
            </div>
          )}

          {/* the frame */}
          <div className="relative mt-1.5" style={{ height: k ? displayH : undefined }}>
            {k > 0 && (
              <div
                className={`absolute left-0 top-0 overflow-hidden rounded-md border bg-surface ${failing ? 'border-accent' : 'border-line'} ${settling ? 'transition-[width] duration-1000 ease-out' : ''}`}
                style={{ width: x, height: displayH }}
                onTransitionEnd={() => setSettling(false)}
              >
                <div
                  ref={frameRef}
                  className={`dm-frame origin-top-left ${settling ? 'transition-[width] duration-1000 ease-out' : ''}`}
                  style={{ width, height: frameH, transform: `scale(${k})` }}
                >
                  <DemoPage variant={variant} />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* heat strip, under the swept range */}
        <div className="mt-4" style={{ marginLeft: `${(SWEEP_MIN / SWEEP_MAX) * 100}%` }}>
          <WidthStrip cells={cells} labels={stageW < 640 ? [360, 1104, 1600] : [360, 794, 1104, 1290, 1600]} active={phase === 'interactive' ? cellIndex(width) : null} summary={caption} showSummary={false} height="h-3 sm:h-4" />
        </div>
        <p id="sweep-help" className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-muted">
          <span>Drag the handle or use ← → to change the width.</span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-[2px] bg-good" /> fits
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="pc-hatch h-2.5 w-2.5 rounded-[2px] bg-accent" /> overflow / overlap
          </span>
          <span>Measured live in your browser on a made-up page.</span>
        </p>
      </div>
    </div>
  );
}
