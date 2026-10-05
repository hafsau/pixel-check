/** Phone-shaped thumbnail (390×844) of a design frame or render. Decorative: the card's title names it. */
export function Thumb({ src, className = '' }: { src: string | null; className?: string }) {
  return (
    <div className={`relative hidden aspect-[390/844] w-14 shrink-0 self-start overflow-hidden rounded-md border border-line bg-surface-2 min-[420px]:block ${className}`} aria-hidden="true">
      {src && <img src={src} alt="" loading="lazy" decoding="async" className="absolute inset-0 h-full w-full object-cover object-top" />}
    </div>
  );
}
