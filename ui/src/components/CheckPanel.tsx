import { useEffect, useId, useState, type FormEvent } from 'react';
import { navigate } from '../lib/router';
import { FRAME_SIZES, LIVE_BPS, validatePageUrl, type LiveBp } from '../lib/live';
import { checkMissing, checkPath, checkReady, codeCounter, validateCode, wantsRepair, type CheckSource } from '../lib/check';
import { REPAIR_ROUNDS } from '../lib/repair';
import { getHealth, startCheck } from '../lib/liveApi';
import { Tabs } from './Tabs';
import { FramePicker, type FrameState } from './FramePicker';
import { Availability, type HealthState } from './LiveRunPanel';
import { IconAlert } from './Icons';

/** Check mode form: three frames + a build (URL or one App.jsx) → POST /api/checks → /check/<id>. */
export function CheckPanel() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' });
  const [frames, setFrames] = useState<Partial<Record<LiveBp, FrameState>>>({});
  const [source, setSource] = useState<CheckSource>('url');
  const [url, setUrl] = useState('');
  const [urlTouched, setUrlTouched] = useState(false);
  const [code, setCode] = useState('');
  const [codeTouched, setCodeTouched] = useState(false);
  const [repair, setRepair] = useState(false);
  const [owns, setOwns] = useState(false);
  const [passcode, setPasscode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ids = useId();

  useEffect(() => {
    let alive = true;
    getHealth().then((r) => alive && setHealth(r.ok ? { status: 'ok', health: r.health } : { status: 'unreachable', message: r.message }));
    return () => {
      alive = false;
    };
  }, []);

  const statuses = Object.fromEntries(LIVE_BPS.map((bp) => [bp, frames[bp]?.status === 'ok' ? 'ok' : frames[bp]?.status === 'error' ? 'error' : 'empty'])) as Record<LiveBp, 'ok' | 'error' | 'empty'>;
  const draft = { frames: statuses, source, url, code, owns, passcode, repair };
  const ready = checkReady(draft);
  const missing = checkMissing(draft);
  const h = health.status === 'ok' ? health.health : null;
  const open = !!h?.live && h.runs_left_today > 0 && h.runs_left_total > 0;
  const urlError = validatePageUrl(url);
  const codeError = validateCode(code);
  const counter = codeCounter(code.length);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!ready || !open || submitting) return;
    setSubmitting(true);
    setError(null);
    const files = Object.fromEntries(LIVE_BPS.map((bp) => [bp, (frames[bp] as Extract<FrameState, { status: 'ok' }>).file])) as Record<LiveBp, File>;
    const r = await startCheck(files, draft);
    setSubmitting(false);
    if (r.ok) {
      setPasscode('');
      navigate(checkPath(r.id, wantsRepair(source, repair)));
    } else {
      setError(r.message);
      if (r.status === 503 || r.status === 429) getHealth().then((x) => x.ok && setHealth({ status: 'ok', health: x.health }));
    }
  };

  return (
    <section aria-labelledby="check-title" className="card card-pad">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <h1 id="check-title" className="display text-2xl sm:text-3xl">
            Check a build
          </h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            Measures your build against your frames at <span className="num">390 / 768 / 1280</span> and across <span className="num">360–1600</span> px. Nothing is changed.
          </p>
        </div>
        <Availability health={health} />
      </div>

      <form className="mt-6 flex flex-col gap-6" onSubmit={submit} aria-describedby={`${ids}-note`} noValidate>
        <fieldset disabled={submitting} className="flex min-w-0 flex-col gap-6">
          <legend className="sr-only">Frames and build to check</legend>
          <div>
            <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <Step n={1} /> Your frames
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {LIVE_BPS.map((bp) => (
                <FramePicker key={bp} bp={bp} width={FRAME_SIZES[bp][0]} height={FRAME_SIZES[bp][1]} onChange={(st) => setFrames((f) => ({ ...f, [bp]: st }))} />
              ))}
            </div>
          </div>

          <div className="min-w-0">
            <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold">
              <Step n={2} /> Your build
            </h2>
            <Tabs
              label="What to check"
              size="md"
              value={source}
              onChange={(s) => {
                setSource(s);
                setError(null);
              }}
              tabs={[
                { key: 'url', label: 'Build URL' },
                { key: 'code', label: 'App.jsx' },
              ]}
            >
              {/* both stay mounted so a typed URL / pasted code survive switching; only the active one is sent */}
              <>
                <div hidden={source !== 'url'} className={source !== 'url' ? 'hidden' : 'grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:items-start'}>
                  <div>
                    <label htmlFor={`${ids}-url`} className="sr-only">
                      Build address
                    </label>
                    <input
                      id={`${ids}-url`}
                      name="url"
                      type="url"
                      inputMode="url"
                      autoComplete="url"
                      spellCheck={false}
                      className="input"
                      placeholder="https://your-build.example.com"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      onBlur={() => setUrlTouched(true)}
                      aria-invalid={urlTouched && !!urlError}
                      aria-describedby={`${ids}-url-msg`}
                    />
                    <p id={`${ids}-url-msg`} className="mt-1 min-h-[1rem] text-xs text-bad" aria-live="polite">
                      {urlTouched && urlError ? urlError : ''}
                    </p>
                  </div>
                  <p className="inset px-3 py-2.5 text-xs text-ink-muted" role="note">
                    <strong className="text-ink">Not for banks, payment, crypto, government, healthcare or sign-in pages.</strong> PixelCheck refuses them, and any page with
                    password, card or wallet fields. The check is automatic, not a security guarantee.
                  </p>
                </div>
                <div hidden={source !== 'code'} className={source !== 'code' ? 'hidden' : 'flex flex-col gap-1'}>
                  <label htmlFor={`${ids}-code`} className="sr-only">
                    App.jsx
                  </label>
                  <textarea
                    id={`${ids}-code`}
                    name="code"
                    rows={10}
                    spellCheck={false}
                    autoCapitalize="off"
                    autoCorrect="off"
                    wrap="off"
                    className="input min-h-[12rem] resize-y py-2 font-mono text-xs leading-relaxed"
                    placeholder={'export default function App() {\n  return <main className="p-6">…</main>;\n}'}
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    onBlur={() => setCodeTouched(true)}
                    aria-invalid={(codeTouched || counter.over) && !!codeError}
                    aria-describedby={`${ids}-code-msg`}
                  />
                  <div id={`${ids}-code-msg`} className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs" aria-live="polite">
                    <span className={codeError && (codeTouched || counter.over) ? 'text-bad' : 'text-ink-muted'}>
                      {codeError && (codeTouched || counter.over) ? codeError : 'React + Tailwind, one file. Rendered offline.'}
                    </span>
                    <span className={`font-mono num ${counter.over ? 'font-semibold text-bad' : counter.near ? 'font-medium text-warn' : 'text-ink-faint'}`}>{counter.label}</span>
                  </div>
                  <label className="inset mt-2 flex cursor-pointer items-start gap-2.5 px-3 py-2.5 text-sm">
                    <input
                      type="checkbox"
                      name="repair"
                      checked={repair}
                      onChange={(e) => setRepair(e.target.checked)}
                      className="mt-0.5 h-4 w-4 shrink-0 accent-[rgb(var(--c-accent))]"
                      aria-describedby={`${ids}-repair-hint`}
                    />
                    <span className="min-w-0">
                      <span className="font-medium text-ink">Also repair it</span>
                      <span id={`${ids}-repair-hint`} className="block text-xs text-ink-muted">
                        Nemotron edits classes, ≤ {REPAIR_ROUNDS} rounds; your structure stays.
                      </span>
                    </span>
                  </label>
                </div>
              </>
            </Tabs>
          </div>

          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" required checked={owns} onChange={(e) => setOwns(e.target.checked)} className="mt-0.5 h-4 w-4 shrink-0 accent-[rgb(var(--c-accent))]" />
            <span>I own this build or have permission to check it.</span>
          </label>

          <div className="grid gap-3 sm:grid-cols-[minmax(0,18rem)_auto] sm:items-end">
            <div>
              <label htmlFor={`${ids}-pass`} className="text-sm font-medium">
                Passcode
              </label>
              <input
                id={`${ids}-pass`}
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
            <button type="submit" className="btn-primary btn-lg justify-self-start" disabled={!ready || !open || submitting}>
              {submitting ? 'Starting…' : wantsRepair(source, repair) ? 'Check + repair' : 'Run check'}
            </button>
          </div>
        </fieldset>

        {error && (
          <p role="alert" className="flex items-start gap-1.5 rounded-md border border-bad/30 bg-bad/5 px-3 py-2 text-sm text-bad">
            <IconAlert /> <span>{error}</span>
          </p>
        )}
        <p id={`${ids}-note`} className="-mt-3 text-xs text-ink-muted">
          {!open ? 'Checks are not available right now.' : ready ? `Ready. Nothing is sent until you press ${wantsRepair(source, repair) ? 'Check + repair' : 'Run check'}.` : `Still needed: ${missing.join(', ')}.`}
        </p>
      </form>
    </section>
  );
}

function Step({ n }: { n: number }) {
  return (
    <span className="grid h-5 w-5 place-items-center rounded-pill bg-ink text-[11px] font-semibold text-bg num" aria-hidden="true">
      {n}
    </span>
  );
}
