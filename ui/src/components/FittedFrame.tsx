import type { ReactNode } from 'react';

/**
 * A box with the breakpoint's aspect ratio that scales to fit both the column width
 * and var(--frame-max-h). Children are positioned inside it (absolute fill).
 */
export function FittedFrame({ width, height, children, className = '' }: { width: number; height: number; children: ReactNode; className?: string }) {
  return (
    <div
      className={`relative mx-auto overflow-hidden rounded-md border border-line bg-surface-2 ${className}`}
      style={{
        aspectRatio: `${width} / ${height}`,
        width: `min(100%, calc(var(--frame-max-h) * ${width / height}))`,
      }}
    >
      {children}
    </div>
  );
}

/** An image that fills a FittedFrame without distortion. */
export function FrameImage({ src, alt, style }: { src: string; alt: string; style?: React.CSSProperties }) {
  return <img src={src} alt={alt} draggable={false} decoding="async" className="absolute inset-0 h-full w-full object-contain" style={style} />;
}

export function FrameEmpty({ children }: { children: ReactNode }) {
  return <div className="absolute inset-0 flex items-center justify-center p-3 text-center text-xs text-ink-muted">{children}</div>;
}
