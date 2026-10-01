import { FittedFrame, FrameImage } from './FittedFrame';

/** Render blended over the design with mix-blend-mode: difference — black means identical. */
export function DiffOverlay({ design, render, width, height, label }: { design: string; render: string; width: number; height: number; label: string }) {
  return (
    <FittedFrame width={width} height={height} className="bg-black">
      <div className="absolute inset-0 isolate" role="img" aria-label={label}>
        <FrameImage src={design} alt="" />
        <FrameImage src={render} alt="" style={{ mixBlendMode: 'difference' }} />
      </div>
    </FittedFrame>
  );
}
