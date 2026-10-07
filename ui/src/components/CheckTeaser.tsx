import { Link } from '../lib/router';
import { CHECK_WIDTHS, DESIGN_AT } from '../lib/check';
import { IconArrowRight } from './Icons';

/** Home-page entry to check mode, next to the live panel. The strip is an illustration, not data. */
export function CheckTeaser() {
  return (
    <section aria-labelledby="check-teaser-title" className="mt-4">
      <Link
        to="/check"
        className="card card-pad group flex flex-col gap-4 transition-shadow hover:shadow-lift sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="min-w-0">
          <p className="eyebrow">Check mode</p>
          <h2 id="check-teaser-title" className="h2 mt-1">
            Already built it? Check a build
          </h2>
          <p className="mt-1 text-sm text-ink-muted">Your URL or App.jsx against your frames, 360–1600 px.</p>
        </div>
        <div className="flex items-end gap-4">
          <div className="flex w-48 items-end gap-[3px]" aria-hidden="true">
            {CHECK_WIDTHS.map((w, i) => (
              <span key={w} className={`flex-1 rounded-[3px] ${DESIGN_AT[w] ? 'h-7 bg-ink/80' : 'h-4'} ${i === 0 ? 'pc-hatch bg-bad' : DESIGN_AT[w] ? '' : 'bg-good'}`} />
            ))}
          </div>
          <span className="btn-primary shrink-0">
            Check <IconArrowRight />
          </span>
        </div>
      </Link>
    </section>
  );
}
