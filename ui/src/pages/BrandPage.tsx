import { MARK_VARIANTS, Mark, type MarkVariant } from '../components/Logo';
import { BpBullets } from '../components/viz/BpBullets';
import { ScoreRing } from '../components/viz/ScoreRing';
import { WidthStrip } from '../components/viz/WidthStrip';

/** Hidden review page (/brand): the three mark variants, lock-ups, favicon, palette and type. Not linked in the nav. */
export function BrandPage() {
  return (
    <div className="page pt-10">
      <p className="eyebrow">Brand review · not linked</p>
      <h1 className="h1 mt-2">PixelCheck mark</h1>
      <p className="mt-3 max-w-2xl text-ink-muted">
        Three frames — phone, tablet, desktop — share one bottom-left corner; their top-right corners trace a check. Hover a card to see the expand animation
        (off with reduced motion). The header, footer and favicon use <strong className="text-ink">Pixel</strong> (default); at 16 px it switches to a bolder 8-bit check.
      </p>

      <ul className="mt-8 grid gap-4 lg:grid-cols-3">
        {MARK_VARIANTS.map((v) => (
          <li key={v.key} className="card pc-hover overflow-hidden">
            <VariantCard variant={v.key} name={v.name} note={v.note} />
          </li>
        ))}
      </ul>

      <section className="section" aria-labelledby="fav-title">
        <h2 id="fav-title" className="h2">
          Favicon
        </h2>
        <div className="mt-3 flex flex-wrap items-end gap-6">
          {[16, 32, 64].map((s) => (
            <figure key={s} className="flex flex-col items-center gap-1.5">
              <img src="/favicon.svg" width={s} height={s} alt={`Favicon at ${s} px`} />
              <figcaption className="font-mono text-[11px] text-ink-faint">{s}px</figcaption>
            </figure>
          ))}
          <div className="flex items-center gap-2 rounded-t-md border border-b-0 border-line bg-surface px-3 py-2 text-xs">
            <img src="/favicon.svg" width={16} height={16} alt="" /> PixelCheck — designed once…
          </div>
          <div className="flex items-center gap-2 rounded-t-md bg-[#202124] px-3 py-2 text-xs text-[#e8eaed]">
            <img src="/favicon.svg" width={16} height={16} alt="" /> PixelCheck — designed once…
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="pal-title">
        <h2 id="pal-title" className="h2">
          Signal palette
        </h2>
        <p className="mt-1 text-sm text-ink-muted">Toggle the theme to see dark. Every text pair is contrast-tested (src/lib/contrast.test.ts).</p>
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {['bg', 'surface', 'surface-2', 'line', 'ink', 'ink-muted', 'accent', 'accent-strong', 'accent-2', 'good', 'ok', 'warn', 'bad', 'bp-mobile', 'bp-tablet', 'bp-desktop'].map((t) => (
            <li key={t} className="overflow-hidden rounded-md border border-line bg-surface">
              <div className="h-12" style={{ background: `rgb(var(--c-${t}))` }} />
              <p className="px-2 py-1.5 font-mono text-[11px]">{t}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="section grid gap-6 lg:grid-cols-2" aria-labelledby="type-title">
        <div>
          <h2 id="type-title" className="h2">
            Type
          </h2>
          <p className="display mt-3 text-5xl">Designed once.</p>
          <p className="mt-2 text-base">Geist Sans 400 · <span className="font-medium">500</span> · <span className="font-semibold">600</span> — display 600, −0.03em.</p>
          <p className="mt-1 font-mono text-sm">Geist Mono 400 · <span className="font-medium">500</span> — 360 / 768 / 1280 / 1600 px</p>
          <p className="pixel mt-3 text-4xl">PixelCheck 92.2</p>
          <p className="mt-1 text-xs text-ink-muted">Geist Pixel: wordmark and large score numerals only.</p>
        </div>
        <div className="card card-pad flex flex-col gap-4">
          <div className="flex items-center gap-4">
            <ScoreRing score={92.15} size={88} />
            <ScoreRing score={69.79} size={56} />
            <ScoreRing score={41} size={40} />
          </div>
          <BpBullets perBp={{ mobile: 94.03, tablet: 92.15, desktop: 71.4 }} legend />
          <WidthStrip
            cells={[
              { width: 360, state: 'pass' },
              { width: 375, state: 'pass' },
              { width: 500, state: 'pass' },
              { width: 1024, state: 'overflow', detail: 'overflow 12 px' },
              { width: 1600, state: 'pass' },
            ]}
            height="h-4"
          />
        </div>
      </section>
    </div>
  );
}

function VariantCard({ variant, name, note }: { variant: MarkVariant; name: string; note: string }) {
  return (
    <div>
      <div className="grid grid-cols-2">
        {(['light', 'dark'] as const).map((t) => (
          <div key={t} data-theme={t} className={`flex flex-col items-center gap-4 px-3 py-6 ${t === 'dark' ? 'bg-[#0E0D0B] text-[#F2F0EA]' : 'bg-[#F4F2EE] text-[#16150F]'}`}>
            <Mark size={88} variant={variant} />
            <div className="flex items-end gap-3">
              {[16, 24, 32].map((s) => (
                <Mark key={s} size={s} variant={variant} />
              ))}
              <Mark size={32} variant={variant} className={t === 'dark' ? 'text-[#FF6A2B]' : 'text-[#E5480F]'} />
            </div>
            <span className="inline-flex items-center gap-2">
              <Mark size={28} variant={variant} className={t === 'dark' ? 'text-[#FF6A2B]' : 'text-[#E5480F]'} />
              <span className="pixel text-[24px] leading-none">PixelCheck</span>
            </span>
          </div>
        ))}
      </div>
      <div className="border-t border-line p-4">
        <p className="flex items-center gap-2 font-semibold">
          {name}
          {variant === 'pixel' && <span className="chip border-accent/40 bg-accent/10 text-accent-strong">Default</span>}
        </p>
        <p className="mt-0.5 text-sm text-ink-muted">{note}</p>
      </div>
    </div>
  );
}
