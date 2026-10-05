import { useEffect, useState, type FormEvent } from 'react';
import { navigate } from '../lib/router';
import { FRAME_SIZES, LIVE_BPS, framesReady, type LiveBp } from '../lib/live';
import { getHealth, startRun, type Health } from '../lib/liveApi';
import { FramePicker, type FrameState } from './FramePicker';
import { IconAlert } from './Icons';

type HealthState = { status: 'loading' } | { status: 'ok'; health: Health } | { status: 'unreachable'; message: string };

/** Live mode: three frames + passcode → POST /api/runs → /live/<id>. The passcode lives only in this component's state. */
export function LiveRunPanel() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' });
  const [frames, setFrames] = useState<Partial<Record<LiveBp, FrameState>>>({});
  const [passcode, setPasscode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getHealth().then((r) => alive && setHealth(r.ok ? { status: 'ok', health: r.health } : { status: 'unreachable', message: r.message }));
    return () => {
      alive = false;
    };
  }, []);

  const statuses = Object.fromEntries(LIVE_BPS.map((bp) => [bp, frames[bp]?.status === 'ok' ? 'ok' : frames[bp]?.status === 'error' ? 'error' : 'empty'])) as Record<LiveBp, 'ok' | 'error' | 'empty'>;
  const h = health.status === 'ok' ? health.health : null;
  const open = !!h?.live && h.runs_left_today > 0 && h.runs_left_total > 0;
  const ready = framesReady(statuses, passcode);
  const missing = [
    ...LIVE_BPS.filter((bp) => statuses[bp] !== 'ok').map((bp) => `a valid ${bp} frame`),
    ...(passcode.trim() ? [] : ['the passcode']),
  ];

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!ready || !open || submitting) return;
    setSubmitting(true);
    setError(null);
    const files = Object.fromEntries(LIVE_BPS.map((bp) => [bp, (frames[bp] as Extract<FrameState, { status: 'ok' }>).file])) as Record<LiveBp, File>;
    const r = await startRun(files, passcode);
    setSubmitting(false);
    if (r.ok) {
      setPasscode('');
      navigate(`/live/${encodeURIComponent(r.id)}`);
    } else {
      setError(r.message);
      if (r.status === 503 || r.status === 429) getHealth().then((x) => x.ok && setHealth({ status: 'ok', health: x.health }));
    }
  };

  return (
    <section id="live" aria-labelledby="live-title" className="section scroll-mt-6" tabIndex={-1}>
      <div className="card card-pad">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <h2 id="live-title" className="h2">
              Live run
            </h2>
            <p className="mt-1 text-sm text-ink-muted">
              Upload the three frames of one screen. Pixel-Check reads them, compiles one React + Tailwind codebase, renders and scores it in a Token Factory
              Sandbox — about a minute, with real models.
            </p>
          </div>
          <Availability health={health} />
        </div>

        <form className="mt-5" onSubmit={submit} aria-describedby="live-note" noValidate>
          <fieldset disabled={submitting}>
            <legend className="sr-only">Design frames</legend>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {LIVE_BPS.map((bp) => (
                <FramePicker key={bp} bp={bp} width={FRAME_SIZES[bp][0]} height={FRAME_SIZES[bp][1]} onChange={(s) => setFrames((f) => ({ ...f, [bp]: s }))} />
              ))}
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,18rem)_auto] sm:items-end">
              <div>
                <label htmlFor="passcode" className="text-sm font-medium">
                  Passcode
                </label>
                <input
                  id="passcode"
                  name="passcode"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  className="input mt-1"
                  placeholder="From the Devpost testing notes"
                  value={passcode}
                  onChange={(e) => setPasscode(e.target.value)}
                />
              </div>
              <button type="submit" className="btn-primary justify-self-start" disabled={!ready || !open || submitting} aria-describedby="live-note">
                {submitting ? 'Starting…' : 'Start live run'}
              </button>
            </div>
          </fieldset>

          {error && (
            <p role="alert" className="mt-4 flex items-start gap-1.5 rounded-md border border-bad/30 bg-bad/5 px-3 py-2 text-sm text-bad">
              <IconAlert /> <span>{error}</span>
            </p>
          )}
          <p id="live-note" className="mt-3 text-xs text-ink-muted">
            {!open
              ? 'Live runs are not available right now — every replay above still works.'
              : ready
                ? 'Ready. Frames are sent to the Pixel-Check server only when you press Start.'
                : `Still needed: ${missing.join(', ')}.`}{' '}
            Frames must be PNG, exactly 390×844, 768×1024 and 1280×800, up to 8 MB each.
          </p>
        </form>
      </div>
    </section>
  );
}

function Availability({ health }: { health: HealthState }) {
  if (health.status === 'loading')
    return (
      <span className="chip" role="status">
        Checking live mode…
      </span>
    );
  if (health.status === 'unreachable')
    return (
      <p className="max-w-xs text-right text-xs text-ink-muted" role="status">
        <span className="chip mb-1">Live server unreachable</span>
        <br />
        Replays still work.
      </p>
    );
  const h = health.health;
  if (!h.live)
    return (
      <p className="max-w-xs text-xs text-ink-muted sm:text-right" role="status">
        <span className="chip mb-1">Live mode off</span>
        <br />
        Switched off to protect the credits. The replays were recorded from real runs and still work.
      </p>
    );
  const none = h.runs_left_today <= 0 || h.runs_left_total <= 0;
  return (
    <p className="text-xs text-ink-muted sm:text-right" role="status">
      <span className={`chip mb-1 ${none ? 'border-warn/40 text-warn' : 'border-good/30 bg-good/10 text-good'}`}>{none ? 'Run limit reached' : 'Live mode on'}</span>
      <br />
      <span className="num">
        {h.runs_left_today} runs left today · {h.runs_left_total} left in total
      </span>
    </p>
  );
}
