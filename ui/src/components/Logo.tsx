/**
 * The PixelCheck mark: three frames — phone, tablet, desktop — share one bottom-left corner, and their top-right
 * corners (10,14) → (16,20) → (28,8) trace a check. Single colour (currentColor); frames are drawn lighter so the
 * check carries the mark. Hover replays a short "expand" (frames grow out of the shared corner, the check draws) —
 * switched off under prefers-reduced-motion (styles in src/styles/index.css, `.pc-mark`).
 *
 * Variants (compare them on /brand): pixel = THE mark (Hafsa, Oct 5) · signal · outline.
 * At ≤ 18 px the pixel mark drops the frames and uses a bolder 8-bit check with fewer, larger steps (same as the favicon).
 */
export type MarkVariant = 'signal' | 'outline' | 'pixel';

export const DEFAULT_MARK: MarkVariant = 'pixel';

export const MARK_VARIANTS: { key: MarkVariant; name: string; note: string }[] = [
  { key: 'pixel', name: 'Pixel', note: 'The check is stepped in square pixels, like the Geist Pixel wordmark. Default; ≤ 18 px uses the bold 8-bit check.' },
  { key: 'signal', name: 'Signal', note: 'Light frames, bold round check.' },
  { key: 'outline', name: 'Outline', note: 'Equal-weight frames; the check ends on the desktop corner. More “diagram”.' },
];

/** Corners of the three frames' top-right edges: the check path. */
export const CHECK_POINTS: [number, number][] = [
  [10, 14],
  [16, 20],
  [28, 8],
];

/** The check path rasterised on a 3-unit grid (connected staircase), cells as [col, row]. */
export const PIXEL_CELLS: [number, number][] = [
  [3, 4], [3, 5], [4, 5], [4, 6], [5, 6], [6, 5], [6, 6], [7, 4], [7, 5], [8, 3], [8, 4], [9, 2], [9, 3],
];
/** Small sizes (≤ 18 px, favicon): a bold 8-bit check, 4-unit cells from (4, 6). */
export const SMALL_CELLS: [number, number][] = [
  [5, 0], [4, 1], [5, 1], [0, 2], [3, 2], [4, 2], [0, 3], [1, 3], [2, 3], [3, 3], [1, 4], [2, 4],
];

export function Mark({ size = 24, variant = DEFAULT_MARK, className = '', title }: { size?: number; variant?: MarkVariant; className?: string; title?: string }) {
  const small = variant === 'pixel' && size <= 18;
  const frameOpacity = variant === 'outline' ? 1 : 0.42;
  const frameWidth = variant === 'outline' ? 1.75 : 1.5;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={`pc-mark shrink-0 ${className}`}
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      focusable="false"
      data-variant={variant}
    >
      {!small && (
        <g fill="none" stroke="currentColor" strokeWidth={frameWidth} opacity={frameOpacity}>
          <rect className="pc-f pc-f3" x="3" y="8" width="25" height="21" rx="1.8" />
          <rect className="pc-f pc-f2" x="3" y="20" width="13" height="9" rx="1.2" />
          <rect className="pc-f pc-f1" x="3" y="14" width="7" height="15" rx="1.2" />
        </g>
      )}
      {variant === 'pixel' ? (
        <g fill="currentColor" className="pc-px">
          {(small ? SMALL_CELLS : PIXEL_CELLS).map(([c, r], i) => (
            <rect key={i} x={small ? 4 + c * 4 : c * 3} y={small ? 6 + r * 4 : r * 3} width={small ? 4 : 3} height={small ? 4 : 3} style={{ animationDelay: `${120 + i * 30}ms` }} />
          ))}
        </g>
      ) : (
        <path
          className="pc-check"
          d={`M${CHECK_POINTS.map((p) => p.join(' ')).join(' L')}`}
          pathLength={1}
          fill="none"
          stroke="currentColor"
          strokeWidth={variant === 'outline' ? 2.6 : 3.2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
}

/** Mark + "PixelCheck" wordmark in Geist Pixel (24 px; 20 px on phones). The mark takes the signal orange. */
export function Logo({ variant = DEFAULT_MARK }: { variant?: MarkVariant }) {
  return (
    <span className="pc-logo inline-flex items-center gap-2 sm:gap-2.5">
      <Mark size={28} variant={variant} className="h-6 w-6 text-accent sm:h-7 sm:w-7" />
      <span className="pixel text-[20px] leading-none sm:text-[24px]">PixelCheck</span>
    </span>
  );
}
