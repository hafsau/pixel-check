import { describe, expect, it } from 'vitest';
import {
  FRAME_SIZES,
  MAX_FRAME_BYTES,
  apiErrorMessage,
  framesReady,
  initialPoll,
  joinUrl,
  liveFilesBase,
  pollReducer,
  resolveAsset,
  stageProgress,
  validateFrame,
  validatePageUrl,
  urlReady,
  failureNotice,
  runDuration,
  sourceHost,
  type LiveStatus,
} from './live';

const png = (w: number, h: number, extra: Partial<{ type: string; name: string; size: number }> = {}) => ({
  type: 'image/png',
  name: 'frame.png',
  size: 120_000,
  width: w,
  height: h,
  ...extra,
});

describe('validateFrame', () => {
  it('accepts a PNG of exactly the breakpoint size', () => {
    expect(validateFrame('mobile', png(390, 844))).toBeNull();
    expect(validateFrame('tablet', png(768, 1024))).toBeNull();
    expect(validateFrame('desktop', png(1280, 800))).toBeNull();
  });

  it('names the frame and both sizes when the size is wrong', () => {
    expect(validateFrame('tablet', png(800, 1024))).toBe('Tablet: the frame must be exactly 768×1024 px (got 800×1024).');
  });

  it('rejects non-PNG files by type, and accepts a .png name when the browser gives no type', () => {
    expect(validateFrame('mobile', png(390, 844, { type: 'image/jpeg', name: 'a.jpg' }))).toBe('Mobile: the frame must be a PNG image.');
    expect(validateFrame('mobile', png(390, 844, { type: '', name: 'A.PNG' }))).toBeNull();
    expect(validateFrame('mobile', png(390, 844, { type: '', name: 'a.webp' }))).toBe('Mobile: the frame must be a PNG image.');
  });

  it('rejects files over the server limit (8 MB) before decoding matters', () => {
    expect(validateFrame('desktop', png(1280, 800, { size: MAX_FRAME_BYTES + 1 }))).toBe('Desktop: the frame is larger than 8 MB.');
    expect(validateFrame('desktop', png(1280, 800, { size: MAX_FRAME_BYTES }))).toBeNull();
  });

  it('reports an image the browser could not decode', () => {
    expect(validateFrame('mobile', png(0, 0))).toBe('Mobile: the frame is not a readable PNG image.');
  });

  it('uses the same sizes as the server', () => {
    expect(FRAME_SIZES).toEqual({ mobile: [390, 844], tablet: [768, 1024], desktop: [1280, 800] });
  });
});

describe('framesReady', () => {
  it('needs all three frames valid and a non-empty passcode', () => {
    const ok = { mobile: 'ok', tablet: 'ok', desktop: 'ok' } as const;
    expect(framesReady(ok, 'abc')).toBe(true);
    expect(framesReady(ok, '   ')).toBe(false);
    expect(framesReady({ ...ok, tablet: 'error' }, 'abc')).toBe(false);
    expect(framesReady({ mobile: 'ok', tablet: 'ok' }, 'abc')).toBe(false);
  });
});

describe('apiErrorMessage', () => {
  it('passes the server detail through for frame problems (422) and size (413), capitalised', () => {
    expect(apiErrorMessage(422, { detail: 'tablet: the frame must be exactly 768×1024 px (got 800×1024)' })).toBe(
      'Tablet: the frame must be exactly 768×1024 px (got 800×1024)',
    );
    expect(apiErrorMessage(413, { detail: 'desktop: the frame is larger than 8 MB' })).toBe('Desktop: the frame is larger than 8 MB');
  });

  it('joins FastAPI validation lists (missing fields)', () => {
    expect(apiErrorMessage(422, { detail: [{ loc: ['body', 'tablet'], msg: 'Field required' }] })).toBe('Tablet: Field required');
  });

  it('gives a clear message for passcode, limits and kill switch', () => {
    expect(apiErrorMessage(403, { detail: 'wrong passcode' })).toMatch(/passcode is not right/i);
    expect(apiErrorMessage(429, { detail: 'the live-run limit is reached; replays still work' })).toMatch(/limit is reached.*replays still work/i);
    expect(apiErrorMessage(503, { detail: 'live mode is switched off; replays still work' })).toMatch(/switched off.*replays still work/i);
  });

  it('handles a network failure and unknown statuses without a body', () => {
    expect(apiErrorMessage(0, null)).toMatch(/could not reach/i);
    expect(apiErrorMessage(500, null)).toBe('The server returned an error (500). Try again in a minute.');
    expect(apiErrorMessage(502, 'Bad gateway')).toBe('The server returned an error (502). Try again in a minute.');
  });

  it('never echoes a passcode-like value from a body', () => {
    expect(apiErrorMessage(403, { detail: 'wrong passcode', passcode: 'hunter2' })).not.toContain('hunter2');
  });
});

describe('pollReducer', () => {
  const st = (state: LiveStatus['state'], extra: Partial<LiveStatus> = {}): LiveStatus => ({ state, stages: [], ...extra });

  it('starts polling with no status', () => {
    expect(initialPoll()).toEqual({ phase: 'polling', status: null, networkErrors: 0 });
  });

  it('keeps polling through queued and running, storing the latest status', () => {
    let s = pollReducer(initialPoll(), { type: 'status', status: st('queued') });
    expect(s.phase).toBe('polling');
    s = pollReducer(s, { type: 'status', status: st('running', { stages: [{ stage: 'perceive', t: 1 }] }) });
    expect(s).toMatchObject({ phase: 'polling', status: { state: 'running' } });
  });

  it('stops on done and on failed (with the error)', () => {
    const done = pollReducer(initialPoll(), { type: 'status', status: st('done', { bundle: '/api/runs/x/files/run.json' }) });
    expect(done.phase).toBe('done');
    const failed = pollReducer(initialPoll(), { type: 'status', status: st('failed', { error: 'RuntimeError: budget' }) });
    expect(failed).toMatchObject({ phase: 'failed', error: 'RuntimeError: budget' });
  });

  it('treats done without a bundle as a failure', () => {
    expect(pollReducer(initialPoll(), { type: 'status', status: st('done', { bundle: null }) })).toMatchObject({ phase: 'failed' });
  });

  it('tolerates a few network errors, then goes offline until retried; a status resets the count', () => {
    let s = initialPoll();
    s = pollReducer(s, { type: 'network-error' });
    s = pollReducer(s, { type: 'network-error' });
    expect(s).toMatchObject({ phase: 'polling', networkErrors: 2 });
    s = pollReducer(s, { type: 'status', status: st('running') });
    expect(s.networkErrors).toBe(0);
    for (let i = 0; i < 3; i++) s = pollReducer(s, { type: 'network-error' });
    expect(s.phase).toBe('offline');
    expect(s.status?.state).toBe('running'); // the last known status is kept for the progress view
    s = pollReducer(s, { type: 'retry' });
    expect(s).toMatchObject({ phase: 'polling', networkErrors: 0 });
  });

  it('a missing run (404) is a failure, not a network error', () => {
    expect(pollReducer(initialPoll(), { type: 'not-found' })).toMatchObject({ phase: 'failed' });
  });

  it('ignores events once finished', () => {
    const done = pollReducer(initialPoll(), { type: 'status', status: st('done', { bundle: 'b' }) });
    expect(pollReducer(done, { type: 'network-error' })).toBe(done);
  });
});

describe('stageProgress', () => {
  const ids = (s: ReturnType<typeof stageProgress>) => s.map((x) => x.state);
  it('all pending while queued', () => {
    expect(ids(stageProgress({ state: 'queued', stages: [] }))).toEqual(['pending', 'pending', 'pending']);
  });
  it('first stage active as soon as the run is running', () => {
    expect(ids(stageProgress({ state: 'running', stages: [] }))).toEqual(['active', 'pending', 'pending']);
  });
  it('the last emitted stage is active, earlier ones done', () => {
    expect(ids(stageProgress({ state: 'running', stages: [{ stage: 'perceive', t: 1 }, { stage: 'compile', t: 9 }] }))).toEqual(['done', 'active', 'pending']);
  });
  it('all done when the run is done', () => {
    expect(ids(stageProgress({ state: 'done', stages: [{ stage: 'perceive', t: 1 }] }))).toEqual(['done', 'done', 'done']);
  });
  it('marks the stage that was running as failed', () => {
    expect(ids(stageProgress({ state: 'failed', stages: [{ stage: 'perceive', t: 1 }, { stage: 'compile', t: 3 }] }))).toEqual(['done', 'failed', 'pending']);
  });
  it('labels the stages in plain words', () => {
    expect(stageProgress({ state: 'queued', stages: [] }).map((s) => s.label)).toEqual([
      'Reading the frames',
      'Compiling, rendering and scoring in the sandbox',
      'Preparing the result',
    ]);
  });
});

describe('asset URLs', () => {
  it('joins the API base and a path without doubling slashes', () => {
    expect(joinUrl('', '/api/health')).toBe('/api/health');
    expect(joinUrl('https://api.example.dev/', '/api/health')).toBe('https://api.example.dev/api/health');
  });

  it('builds the files base of a live run, encoding the id', () => {
    expect(liveFilesBase('', '20261005-101010-abc123')).toBe('/api/runs/20261005-101010-abc123/files/');
    expect(liveFilesBase('https://x.dev', 'a b')).toBe('https://x.dev/api/runs/a%20b/files/');
  });

  it('resolves bundle-relative asset paths against the files base', () => {
    const base = '/api/runs/r1/files/';
    expect(resolveAsset(base, 'design/mobile.webp')).toBe('/api/runs/r1/files/design/mobile.webp');
    expect(resolveAsset(base, './c/ab12/App.jsx')).toBe('/api/runs/r1/files/c/ab12/App.jsx');
  });

  it('refuses paths that would escape the bundle or point elsewhere', () => {
    const base = '/api/runs/r1/files/';
    expect(resolveAsset(base, '../../secrets')).toBeNull();
    expect(resolveAsset(base, 'https://evil.example/x.png')).toBeNull();
    expect(resolveAsset(base, '/etc/passwd')).toBeNull();
    expect(resolveAsset(base, '')).toBeNull();
  });
});

describe('validatePageUrl', () => {
  it('accepts full http(s) URLs', () => {
    expect(validatePageUrl('https://example.com/pricing')).toBeNull();
    expect(validatePageUrl('  http://example.com  ')).toBeNull();
  });
  it('asks for a URL when empty', () => {
    expect(validatePageUrl('   ')).toBe('Enter the address of a public web page.');
  });
  it('explains a missing scheme with the likely fix', () => {
    expect(validatePageUrl('example.com/pricing')).toBe('Start the address with https:// — e.g. https://example.com/pricing.');
  });
  it('rejects other schemes and URLs without a host', () => {
    expect(validatePageUrl('ftp://example.com')).toBe('Only http:// and https:// pages can be captured.');
    expect(validatePageUrl('javascript:alert(1)')).toBe('Only http:// and https:// pages can be captured.');
    expect(validatePageUrl('https://')).toBe('Enter a full address with a host name, e.g. https://example.com/pricing.');
  });
  it('mirrors the server on credentials, ports and length', () => {
    expect(validatePageUrl('https://user:pw@example.com')).toBe('Remove the user name or password from the address.');
    expect(validatePageUrl('https://example.com:8080/')).toBe('Only standard ports (80 / 443) are supported.');
    expect(validatePageUrl('https://example.com:443/')).toBeNull();
    expect(validatePageUrl('https://example.com/' + 'a'.repeat(2000))).toBe('The address is too long.');
  });
  it('flags obvious local addresses early (the server checks DNS too)', () => {
    expect(validatePageUrl('http://localhost:80/')).toBe('Only public web pages can be captured — not local or private addresses.');
    expect(validatePageUrl('http://192.168.1.10/')).toBe('Only public web pages can be captured — not local or private addresses.');
    expect(validatePageUrl('http://127.0.0.1/')).toBe('Only public web pages can be captured — not local or private addresses.');
  });
});

describe('urlReady', () => {
  it('needs a valid URL, the ownership box and a passcode', () => {
    expect(urlReady('https://example.com', true, 'pc')).toBe(true);
    expect(urlReady('https://example.com', false, 'pc')).toBe(false);
    expect(urlReady('example.com', true, 'pc')).toBe(false);
    expect(urlReady('https://example.com', true, ' ')).toBe(false);
  });
});

describe('apiErrorMessage — URL runs', () => {
  it('passes URL problems and the ownership requirement through, capitalised', () => {
    expect(apiErrorMessage(422, { detail: 'confirm that you own this page or have permission to rebuild it' })).toBe(
      'Confirm that you own this page or have permission to rebuild it',
    );
    expect(apiErrorMessage(422, { detail: 'only public web pages can be captured' })).toBe('Only public web pages can be captured');
    expect(apiErrorMessage(422, { detail: 'cannot find the host nope.invalid' })).toBe('Cannot find the host nope.invalid');
  });
});

describe('failureNotice', () => {
  it('presents the login / checkout refusal as a decision, not a crash', () => {
    const r = failureNotice('this page has password or payment fields — PixelCheck does not rebuild login or checkout pages from a URL; upload your own design frames instead');
    expect(r.kind).toBe('refused');
    expect(r.title).toBe('This page was not rebuilt');
    expect(r.message.startsWith('This page has password or payment fields')).toBe(true);
  });
  it('treats anything else as a failure', () => {
    expect(failureNotice('RuntimeError: the page could not be captured (FAILED)')).toMatchObject({ kind: 'error', title: 'The run failed' });
    expect(failureNotice(undefined)).toMatchObject({ kind: 'error', message: 'The run failed.' });
  });
});

describe('stageProgress — URL runs', () => {
  const ids = (s: ReturnType<typeof stageProgress>) => s.map((x) => `${x.id}:${x.state}`);
  it('adds "Capturing the page" first when the run has a source URL', () => {
    const st = { state: 'running' as const, stages: [{ stage: 'capture', t: 1 }], source: { url: 'https://example.com' } };
    expect(stageProgress(st).map((s) => s.label)[0]).toBe('Capturing the page');
    expect(ids(stageProgress(st))).toEqual(['capture:active', 'perceive:pending', 'compile:pending', 'bundle:pending']);
  });
  it('moves on after capture', () => {
    const st = { state: 'running' as const, stages: [{ stage: 'capture', t: 1 }, { stage: 'perceive', t: 90 }], source: { url: 'https://example.com' } };
    expect(ids(stageProgress(st))).toEqual(['capture:done', 'perceive:active', 'compile:pending', 'bundle:pending']);
  });
  it('a refusal during capture marks capture failed', () => {
    const st = { state: 'failed' as const, stages: [{ stage: 'capture', t: 1 }], source: { url: 'https://example.com' } };
    expect(ids(stageProgress(st))[0]).toBe('capture:failed');
  });
  it('has no capture step for uploaded frames', () => {
    expect(stageProgress({ state: 'queued', stages: [] }).map((s) => s.id)).toEqual(['perceive', 'compile', 'bundle']);
  });
});

describe('runDuration / sourceHost', () => {
  it('gives the honest duration hint per source', () => {
    expect(runDuration({ state: 'queued', stages: [] })).toBe('45–90 seconds');
    expect(runDuration({ state: 'queued', stages: [], source: { url: 'https://example.com' } })).toBe('2–7 minutes');
  });
  it('extracts the host for the header', () => {
    expect(sourceHost({ url: 'https://www.example.com/pricing?x=1' })).toBe('www.example.com');
    expect(sourceHost(undefined)).toBeNull();
    expect(sourceHost({ url: 'not a url' })).toBeNull();
  });
});

describe('brand name in live messages', () => {
  it('says PixelCheck (no hyphen) when the server is unreachable', () => {
    expect(apiErrorMessage(0, null)).toBe('Could not reach the PixelCheck server. Check your connection and try again.');
  });
});
