import { useState } from 'react';
import { DEFAULT_BPS } from '../lib/format';
import { FramePicker, type FrameState } from './FramePicker';

/** Live mode placeholder: frame upload + validation + passcode. Never submits. */
export function LiveRunPanel() {
  const [frames, setFrames] = useState<Record<string, FrameState['status']>>({});
  const allOk = DEFAULT_BPS.every((b) => frames[b.name] === 'ok');

  return (
    <section id="live" aria-labelledby="live-title" className="section scroll-mt-6" tabIndex={-1}>
      <div className="card card-pad">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="live-title" className="h2">
              Live run
            </h2>
            <p className="mt-1 text-sm text-ink-muted">
              Upload the three frames of one screen. Pixel-Check writes one codebase and verifies it at all three sizes.
            </p>
          </div>
          <span className="chip">Live mode coming soon</span>
        </div>

        <form className="mt-5" onSubmit={(e) => e.preventDefault()} aria-describedby="live-note">
          <fieldset>
            <legend className="sr-only">Design frames</legend>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {DEFAULT_BPS.map((b) => (
                <FramePicker
                  key={b.name}
                  bp={b.name}
                  width={b.width}
                  height={b.height}
                  onChange={(s) => setFrames((f) => ({ ...f, [b.name]: s.status }))}
                />
              ))}
            </div>
          </fieldset>

          <div className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,18rem)_auto] sm:items-end">
            <div>
              <label htmlFor="passcode" className="text-sm font-medium">
                Passcode
              </label>
              <input id="passcode" type="password" autoComplete="off" className="input mt-1" placeholder="From the Devpost testing notes" />
            </div>
            <button type="submit" className="btn-primary justify-self-start" disabled aria-disabled="true">
              Start live run
            </button>
          </div>
          <p id="live-note" className="mt-3 text-xs text-ink-muted">
            Live mode coming soon — runs are capped and need a passcode. {allOk ? 'All three frames are the right size.' : 'Frames must be exactly 390×844, 768×1024 and 1280×800.'}
          </p>
        </form>
      </div>
    </section>
  );
}
