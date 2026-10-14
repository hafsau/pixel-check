"""Live mode API: upload the three frames of one screen, PixelCheck runs the pipeline in the background (perceive →
compile → render + score in Token Factory Sandboxes), the web app polls progress and replays the result bundle.

    uvicorn orchestrator.api:app --port 8000          (LIVE_ENABLED=1 LIVE_PASSCODE=… in the environment)

POST /api/runs            multipart mobile / tablet / desktop (PNG, exactly 390×844 / 768×1024 / 1280×800) + passcode
                          → 202 {"id"}; 403 passcode · 422 frames · 413 too large · 429 caps · 503 live off
GET  /api/runs/{id}       {"state": queued|running|done|failed, "stages": [...], "events": [...], "result", "bundle"}
GET  /api/runs/{id}/files/<path>   the result bundle (run.json, screenshots, App.jsx) — never outside it
GET  /api/health          {"live", "runs_left_today", "runs_left_total"}

Guards (CLAUDE.md §6–7): kill switch, passcode (constant-time compare, never logged or echoed), daily + total run
caps persisted next to the runs, per-run spend budget in the pipeline (TFClient), upload size limit, path-safe file
serving, error messages scrubbed of anything credential-like.
"""
from __future__ import annotations

import hmac
import io
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

SIZES = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}
MAX_BYTES = 8 * 1024 * 1024
_ID = re.compile(r"^[a-z0-9-]{8,40}$")
_SECRET = re.compile(r"(?i)(bearer\s+\S+|sk-[\w-]+|api[_-]?key\s*[=:]?\s*\S+|authorization\s*:?\s*\S+(\s+\S+)?|"
                     r"\btoken\s*[=:]\s*\S+|\b(access|auth|secret)[_-]?token\S*)")
MAX_REQUEST = 26 * 1024 * 1024   # 3 frames × 8 MB + an App.jsx: refuse bigger bodies before parsing them


class _Refused(Exception):
    """A deliberate refusal (shown to the user as is)."""


def _scrub(msg: str) -> str:
    return _SECRET.sub("[redacted]", msg)[:300]


class _Caps:
    """Daily + total run counts, persisted (a restart must not reset the total)."""

    def __init__(self, path: Path, daily: int, total: int, per_ip: int | None = None):
        self.path, self.daily, self.total, self.per_ip = path, daily, total, per_ip
        self.lock = threading.Lock()

    def _read(self) -> list:
        """A missing file is no runs yet; a garbled one raises (fail closed: never 'all runs left')."""
        try:
            text = self.path.read_text()
        except FileNotFoundError:
            return []
        return [r if isinstance(r, list) else [r, None] for r in json.loads(text)]

    def _write(self, runs: list) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(runs))
        os.replace(tmp, self.path)

    def untake(self) -> None:
        with self.lock:
            self._write(self._read()[:-1])

    def left(self, ip: str | None = None) -> tuple[int, int]:
        try:
            runs = self._read()
        except (json.JSONDecodeError, ValueError):
            return 0, 0
        today = time.strftime("%Y-%m-%d")
        todays = [r for r in runs if time.strftime("%Y-%m-%d", time.localtime(r[0])) == today]
        d = self.daily - len(todays)
        if ip is not None and self.per_ip:          # one visitor cannot use up the whole day
            d = min(d, self.per_ip - sum(1 for r in todays if r[1] == ip))
        return max(0, d), max(0, self.total - len(runs))

    def take(self, ip: str | None = None) -> bool:
        with self.lock:
            d, t = self.left(ip)
            if d <= 0 or t <= 0:
                return False
            self._write(self._read() + [[time.time(), ip]])
            return True


def _check_png(bp: str, data: bytes):
    from PIL import Image, UnidentifiedImageError
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(422, f"{bp}: the frame must be a PNG image")
    try:
        with Image.open(io.BytesIO(data)) as im:
            size = im.size
    except (UnidentifiedImageError, OSError):
        raise HTTPException(422, f"{bp}: the frame is not a readable PNG image") from None
    if tuple(size) != SIZES[bp]:
        w, h = SIZES[bp]
        raise HTTPException(422, f"{bp}: the frame must be exactly {w}×{h} px (got {size[0]}×{size[1]})")


async def _read_frames(uploads) -> tuple[dict[str, bytes], dict, dict[str, bytes]]:
    """Three uploads (field, UploadFile) → frames labelled by width and cropped to the first screen
    (orchestrator/frames.py), what was inferred for the user, and the full originals of cropped frames."""
    from . import frames as F
    raw = {}
    for field, up in uploads:
        data = await up.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, f"{field}: the frame is larger than {MAX_BYTES // (1024 * 1024)} MB")
        raw[field] = data
    try:
        assigned, notes = F.assign(raw)
    except F.FrameError as e:
        raise HTTPException(422, str(e)) from None
    sizes = F.sizes(assigned)
    info = {"sizes": {bp: list(v) for bp, v in sizes.items()},
            "original": {bp: list(f.original) for bp, f in assigned.items()},
            "sources": {bp: f.source for bp, f in assigned.items()},
            "prefixes": F.prefixes(sizes), "notes": notes}
    full = {bp: raw[f.source] for bp, f in assigned.items() if f.original != f.size}
    return {bp: f.png for bp, f in assigned.items()}, info, full


def _save_frames(run_dir: Path, frames: dict[str, bytes], full: dict[str, bytes]) -> None:
    """frames/{bp}.png = what is perceived and scored; frames/full/{bp}.png = a cropped frame's whole page (display)."""
    (run_dir / "frames").mkdir(parents=True)
    for bp, data in frames.items():
        (run_dir / "frames" / f"{bp}.png").write_bytes(data)
    if full:
        (run_dir / "frames" / "full").mkdir()
        for bp, data in full.items():
            (run_dir / "frames" / "full" / f"{bp}.png").write_bytes(data)


def _resolve(host: str) -> list[str]:
    import socket
    return sorted({ai[4][0] for ai in socket.getaddrinfo(host, None)})


def _check_url(url: str, resolver) -> str:
    """Public http(s) pages only: no private / loopback / link-local (cloud metadata) / reserved addresses — every
    address the host resolves to must be public —, no credentials in the URL, standard ports, sane length."""
    import ipaddress
    from urllib.parse import urlsplit
    url = (url or "").strip()
    if len(url) > 2000:
        raise HTTPException(422, "the URL is too long")
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise HTTPException(422, "enter a full http(s) URL, e.g. https://example.com/pricing")
    if u.username or u.password:
        raise HTTPException(422, "the URL must not contain a user name or password")
    try:
        port = u.port
    except ValueError:
        raise HTTPException(422, "the URL has an invalid port") from None
    if port not in (None, 80, 443):
        raise HTTPException(422, "only standard ports (80 / 443) are supported")
    host = u.hostname
    try:
        addrs = [host] if _is_ip(host) else resolver(host)
    except OSError:
        raise HTTPException(422, f"cannot find the host {host}") from None
    if not addrs:
        raise HTTPException(422, f"cannot find the host {host}")
    for a in addrs:
        ip = ipaddress.ip_address(a)
        if not ip.is_global or ip.is_multicast:
            raise HTTPException(422, "only public web pages can be captured")
    return url


def _is_ip(host: str) -> bool:
    import ipaddress
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _bare(url: str) -> str:
    """Stored / shown without query or fragment (they can carry private data)."""
    from urllib.parse import urlsplit, urlunsplit
    u = urlsplit(url)
    return urlunsplit((u.scheme, u.netloc, u.path, "", ""))


def _policy(url: str) -> dict | None:
    from urllib.parse import urlsplit
    from . import policy
    u = urlsplit(url)
    return policy.check_host(u.hostname or "") or policy.check_query(u.query)


def _policy_or_422(url: str):
    from . import policy
    r = _policy(url)
    if r:
        raise HTTPException(422, policy.refusal(r))


def _verify_capture(meta: dict, resolver):
    """Where the capture really went: every redirect hop and the final URL must be public and allowed, the server IP
    public, and the page must not present itself as a high-risk service (title / og:site_name)."""
    import ipaddress
    from . import policy
    nav = meta.get("navigation")
    if not nav or not nav.get("final_url"):
        raise _Refused("PixelCheck could not verify where the page led, so nothing was rebuilt")
    for u in list(nav.get("hops") or []) + [nav["final_url"]] + list(nav.get("final_urls") or []):
        try:
            _check_url(u, resolver)
        except HTTPException:
            raise _Refused("the page redirected to an address that is not a public web page — only public web pages "
                           "can be captured") from None
        r = _policy(u)
        if r:
            raise _Refused(policy.refusal(r))
    for ip in [nav.get("server_ip")] + list(nav.get("server_ips") or []):     # every size's server
        if not ip:
            continue
        try:
            ok = ipaddress.ip_address(ip).is_global
        except ValueError:
            ok = False
        if not ok:
            raise _Refused("the page was served from an address that is not public — only public web pages can be captured")
    for page in [meta.get("page") or {}] + list(meta.get("pages") or []):
        r = policy.check_page(page.get("title", ""), page.get("site_name", ""))
        if r:
            raise _Refused(policy.refusal(r))


MAX_CODE = 300_000       # an App.jsx for check mode, characters


def _refuse_sensitive(meta: dict):
    sens = (meta or {}).get("sensitive") or {}
    if any(sens.get(k) for k in ("password", "payment", "signin", "crypto")):
        raise _Refused("this page has sign-in, password, payment or wallet fields — PixelCheck does not "
                       "rebuild login, checkout or wallet pages from a URL; upload your own design frames instead")


def _ledger_entries(path: Path) -> list[dict]:
    try:
        return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def create_app(pipeline=None, live_dir: Path | None = None, settings: dict | None = None, capture=None,
               resolver=None, checker=None, repairer=None, store=None) -> FastAPI:
    from . import config
    from . import frames as _frames
    from . import state as _state
    from .tf_client import Ledger
    s = {"enabled": config.LIVE_ENABLED, "passcode": config.LIVE_PASSCODE, "daily": config.LIVE_DAILY_RUNS,
         "total": config.LIVE_TOTAL_RUNS, "origins": config.LIVE_ORIGINS, "per_ip": config.LIVE_PER_IP_DAILY,
         "trust_proxy": config.LIVE_TRUST_PROXY, "url_allow": config.LIVE_URL_ALLOW, "owned_hosts": config.OWNED_HOSTS,
         "daily_spend": config.LIVE_DAILY_SPEND_USD, "ledger": config.LEDGER_PATH}
    s.update(settings or {})
    root = Path(live_dir or config.LIVE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    caps = _Caps(root / "caps.json", s["daily"], s["total"], s.get("per_ip"))
    ledger_path = Path(s["ledger"])
    ledger = Ledger(ledger_path)
    store = store or _state.from_env(dict(os.environ), root)
    take_lock = threading.Lock()
    jobs = threading.Semaphore(max(1, int(s.get("job_slots") or config.JOB_SLOTS)))   # heavy work, one at a time

    def today() -> str:
        return time.strftime("%Y-%m-%d")

    def daily_spend() -> float:
        """Today's spend: today's ledger entries; a restored entry carries the stored day's share."""
        tot = 0.0
        for e in _ledger_entries(ledger_path):
            if time.strftime("%Y-%m-%d", time.localtime(e.get("ts", 0))) != today():
                continue
            tot += e.get("today_usd", 0.0) if e.get("kind") == "restored" else e.get("usd", 0.0)
        return tot

    def snapshot() -> dict:
        return {"caps": caps._read(), "spend_usd": round(ledger.total(), 6), "spend_day": [today(), round(daily_spend(), 6)]}

    # the host may have wiped the disk (Render free): restore caps and spend from the store — or keep live mode off
    state_error = None
    try:
        st = store.load()
        merged = sorted({tuple(r) for r in caps._read() + [list(x) for x in st["caps"]]}, key=lambda r: r[0])
        caps._write([list(r) for r in merged])
        missing = st["spend_usd"] - ledger.total()
        if missing > 1e-9:
            day, day_usd = (st["spend_day"] + [None, 0.0])[:2]
            ledger.add({"ts": time.time(), "kind": "restored", "usd": missing,
                        "today_usd": float(day_usd or 0.0) if day == today() else 0.0})
    except (_state.StateError, json.JSONDecodeError, ValueError) as e:
        state_error = str(e)

    def live_ok() -> bool:
        return bool(s["enabled"]) and state_error is None

    def require_live():
        if not s["enabled"]:
            raise HTTPException(503, "live mode is switched off; replays still work")
        if state_error is not None:
            raise HTTPException(503, "live mode is unavailable: the run counter could not be read; replays still work")

    def persist():
        store.save(snapshot())

    def take_run(request: Request, weight: int = 1):
        """A run slot (a repair weighs 3): daily spend under its cap, caps not reached, and the store has recorded
        it — or no run."""
        if daily_spend() >= float(s["daily_spend"]):
            raise HTTPException(429, "today's live-run budget is used up; replays still work")
        with take_lock:
            taken = 0
            for _ in range(weight):
                if not caps.take(visitor(request)):
                    for _ in range(taken):
                        caps.untake()
                    raise HTTPException(429, "the live-run limit is reached; replays still work")
                taken += 1
            try:
                persist()
            except _state.StateError:
                for _ in range(taken):
                    caps.untake()
                raise HTTPException(503, "PixelCheck could not record the run in its run counter; please try again later") from None

    def visitor(request: Request) -> str:
        """The client address; X-Forwarded-For only behind a trusted proxy (else anyone could pick an address).
        Kept only as a keyed hash: the caps live in a gist that anyone with its URL can read."""
        addr = request.client.host if request.client else "unknown"
        if s.get("trust_proxy"):
            fwd = request.headers.get("x-forwarded-for", "")
            if fwd.strip():           # Render appends the address it saw: the LAST entry (earlier ones are client-made)
                addr = fwd.split(",")[-1].strip()
        key = (s.get("passcode") or "pixelcheck").encode()
        return hmac.new(key, addr.encode(), "sha256").hexdigest()[:16]
    for st_p in root.glob("*/status.json"):     # runs live in threads: a restart orphans unfinished ones
        try:
            st = json.loads(st_p.read_text())
        except json.JSONDecodeError:
            continue
        if st.get("state") in ("queued", "running"):
            st.update(state="failed", error="the server restarted during this run; please start it again")
            st_p.write_text(json.dumps(st))
    run_pipeline = pipeline or default_pipeline
    run_capture = capture or default_capture
    run_check = checker or default_checker
    run_repair = repairer or default_repairer
    resolve = resolver or _resolve
    app = FastAPI(title="PixelCheck live", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def limit_body(request: Request, call_next):
        from fastapi.responses import JSONResponse
        try:
            size = int(request.headers.get("content-length") or 0)
        except ValueError:
            size = 0
        if size > MAX_REQUEST:
            return JSONResponse({"detail": "the request is too large"}, status_code=413)
        return await call_next(request)
    app.add_middleware(CORSMiddleware, allow_origins=list(s["origins"] or []), allow_methods=["GET", "POST"],
                       allow_headers=["*"])

    def status_path(rid: str) -> Path:
        return root / rid / "status.json"

    def write_status(rid: str, **upd):
        p = status_path(rid)
        st = json.loads(p.read_text()) if p.exists() else {}
        st.update(upd)
        p.write_text(json.dumps(st))

    def worker(rid: str, frames: dict[str, bytes] | None, url: str | None = None):
        run_dir = root / rid
        stages = []

        def emit(stage: str, **info):
            stages.append({"stage": stage, "t": round(time.time(), 1), **info})
            write_status(rid, state="running", stages=stages)
        owned = False
        jobs.acquire()                     # waits as "queued" while another run uses the slot
        try:
            write_status(rid, state="running")
            if url is not None:          # capture the page at the three breakpoints first (sandbox, network on)
                from urllib.parse import urlsplit
                host = (urlsplit(url).hostname or "").lower()
                owned = any(host == h or host.endswith("." + h) for h in (s.get("owned_hosts") or []))
                frames, meta = run_capture(url, run_dir, emit, **({"owned": True} if owned else {}))
                _verify_capture(meta or {}, resolve)
                _refuse_sensitive(meta)
                (run_dir / "frames").mkdir(parents=True, exist_ok=True)
                for bp, data in frames.items():
                    (run_dir / "frames" / f"{bp}.png").write_bytes(data)
            with _frames.use(_frames.sizes_of(frames)):        # the run's own frame sizes; defaults restored
                result = run_pipeline(rid, frames, run_dir, emit)
            if url is not None:          # rebuilt from a page: say where it came from, in the code itself
                from urllib.parse import urlsplit
                if owned:
                    note = (f"// Generated by PixelCheck from {urlsplit(url).hostname} (an owned site) on "
                            f"{time.strftime('%Y-%m-%d')}.\n")
                else:
                    note = (f"// Generated by PixelCheck from a capture of {urlsplit(url).hostname} on "
                            f"{time.strftime('%Y-%m-%d')}. Replace third-party text and branding before use.\n")
                for jsx in (run_dir / "bundle").rglob("App.jsx"):
                    jsx.write_text(note + jsx.read_text())
            write_status(rid, state="done", stages=stages, result=result,
                         bundle=f"/api/runs/{rid}/files/run.json" if (run_dir / "bundle" / "run.json").exists() else None)
        except _Refused as e:
            write_status(rid, state="failed", stages=stages, error=str(e))
        except Exception as e:     # the API must report, never leak credentials from upstream errors
            write_status(rid, state="failed", stages=stages, error=_scrub(f"{type(e).__name__}: {e}"))
        finally:
            jobs.release()
            try:
                persist()                  # the spend of this run survives a wiped disk
            except Exception:
                pass

    @app.get("/api/health")
    def health():
        d, t = caps.left()
        return {"live": live_ok(), "runs_left_today": d, "runs_left_total": t}

    @app.post("/api/runs", status_code=202)
    async def start(request: Request, mobile: UploadFile = File(...), tablet: UploadFile = File(...),
                    desktop: UploadFile = File(...), passcode: str = Form("")):
        require_live()
        if not s["passcode"] or not hmac.compare_digest(passcode.encode(), str(s["passcode"]).encode()):
            raise HTTPException(403, "wrong passcode")
        frames, info, full = await _read_frames((("mobile", mobile), ("tablet", tablet), ("desktop", desktop)))
        take_run(request)
        rid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        run_dir = root / rid
        _save_frames(run_dir, frames, full)
        write_status(rid, state="queued", stages=[], created=time.time(), frames=info)
        threading.Thread(target=worker, args=(rid, frames), daemon=True).start()
        return {"id": rid}

    @app.post("/api/runs/url", status_code=202)
    def start_url(request: Request, url: str = Form(""), owns: str = Form(""), passcode: str = Form("")):
        require_live()
        if not s["passcode"] or not hmac.compare_digest(passcode.encode(), str(s["passcode"]).encode()):
            raise HTTPException(403, "wrong passcode")
        if owns.strip().lower() not in ("true", "1", "yes", "on"):
            raise HTTPException(422, "confirm that you own this page or have permission to rebuild it")
        url = _check_url(url, resolve)
        _policy_or_422(url)
        allow = [h.lower() for h in (s.get("url_allow") or [])]
        if allow:
            from urllib.parse import urlsplit
            host = (urlsplit(url).hostname or "").lower()
            if not any(host == h or host.endswith("." + h) for h in allow):
                raise HTTPException(422, f"this demo only rebuilds pages from: {', '.join(allow)}")
        take_run(request)
        rid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        (root / rid).mkdir(parents=True)
        write_status(rid, id=rid, state="queued", stages=[], created=time.time(), source={"url": _bare(url)})
        threading.Thread(target=worker, args=(rid, None, url), daemon=True).start()
        return {"id": rid}

    def check_worker(rid: str, kind: str, build: str, frames: dict[str, bytes], repair: bool = False):
        """Check mode: the build (URL or App.jsx) measured against the design frames → bundle/check.json + frames."""
        from .check import CheckError, CheckRefused
        run_dir = root / rid
        stages = []

        def emit(stage: str, **info):
            stages.append({"stage": stage, "t": round(time.time(), 1), **info})
            write_status(rid, state="running", stages=stages)

        def verify(meta):
            _verify_capture(meta or {}, resolve)
            _refuse_sensitive(meta)
        jobs.acquire()
        try:
            write_status(rid, state="running")
            from contextlib import nullcontext
            with _frames.use(_frames.sizes_of(frames)) if frames else nullcontext():   # the run's own frame sizes
                out = run_check(kind, build, frames, run_dir, emit, verify)
            rep = out.get("report") or {}
            bundle = run_dir / "bundle"
            paths = {}
            for side, imgs in (("design", frames), ("build", out.get("build") or {})):
                paths[side] = {}
                for bp, data in imgs.items():
                    (bundle / side).mkdir(parents=True, exist_ok=True)
                    _webp(data, bundle / side / f"{bp}.webp")
                    paths[side][bp] = f"{side}/{bp}.webp"
            per_bp = rep.get("per_bp") or {bp: v.get("score") for bp, v in (rep.get("breakpoints") or {}).items()
                                           if isinstance(v, dict)}
            repaired, summary = None, None
            if repair and kind == "code":   # Nemotron repair loop on the same frames (orchestrator/repair.py)
                try:
                    fix = run_repair(build, frames, run_dir, emit)
                except Exception as e:      # the check result stands; the repair reports what stopped it
                    fix = {"error": _scrub(f"the repair could not finish: {type(e).__name__}: {e}")}
                if "error" in fix:
                    repaired, summary = {"error": fix["error"]}, {"error": fix["error"]}
                else:
                    (bundle / "repair").mkdir(parents=True, exist_ok=True)
                    (bundle / "original").mkdir(parents=True, exist_ok=True)
                    (bundle / "repair" / "App.jsx").write_text(fix["code"])
                    (bundle / "original" / "App.jsx").write_text(build)
                    repaired = {"code": "repair/App.jsx", "original": "original/App.jsx", "start": fix.get("start"),
                                "best": fix.get("best"), "history": fix.get("history"),
                                "lines_kept": fix.get("lines_kept"), "usd": fix.get("usd")}
                    summary = {"before": (fix.get("start") or {}).get("worst"),
                               "after": (fix.get("best") or {}).get("worst"), "lines_kept": fix.get("lines_kept")}
            diagnostics = {}
            if frames:                       # explain the score beside it (orchestrator/diagnose.py); never changes it
                from .diagnose import diagnose
                diagnostics = diagnose(rep, frames=frames, build=out.get("build") or {},
                                       design_texts=out.get("design_texts") or {}, dom=out.get("dom") or {},
                                       fonts=out.get("fonts"))
            (bundle / "check.json").write_text(json.dumps({
                "type": "check", "id": rid, "source": json.loads(status_path(rid).read_text()).get("source"),
                "report": rep, "design": paths["design"], "build": paths["build"],
                "design_texts": out.get("design_texts") or {}, "usd": out.get("usd"), "repair": repaired,
                "fonts": out.get("fonts"), "diagnostics": diagnostics,
                "sizes": {bp: list(wh) for bp, wh in _frames.sizes_of(frames).items()} if frames else None}))
            write_status(rid, state="done", stages=stages,
                         result={"match": rep.get("match"), "per_bp": per_bp,
                                 "fluid_pass": (rep.get("fluidity") or {}).get("pass"), "usd": out.get("usd"),
                                 **({"repair": summary} if summary else {})},
                         bundle=f"/api/runs/{rid}/files/check.json")
        except (_Refused, CheckRefused) as e:
            write_status(rid, state="failed", stages=stages, error=str(e))
        except CheckError as e:
            write_status(rid, state="failed", stages=stages, error=_scrub(str(e)))
        except Exception as e:
            write_status(rid, state="failed", stages=stages, error=_scrub(f"{type(e).__name__}: {e}"))
        finally:
            jobs.release()
            try:
                persist()
            except Exception:
                pass

    @app.post("/api/checks", status_code=202)
    async def start_check(request: Request, mobile: UploadFile | None = File(None), tablet: UploadFile | None = File(None),
                          desktop: UploadFile | None = File(None), url: str = Form(""), code: str = Form(""),
                          owns: str = Form(""), passcode: str = Form(""), repair: str = Form("")):
        require_live()
        if not s["passcode"] or not hmac.compare_digest(passcode.encode(), str(s["passcode"]).encode()):
            raise HTTPException(403, "wrong passcode")
        if owns.strip().lower() not in ("true", "1", "yes", "on"):
            raise HTTPException(422, "confirm that you own this build or have permission to check it")
        url, has_code = url.strip(), bool(code.strip())
        if bool(url) == has_code:
            raise HTTPException(422, "give either the build's address or its App.jsx, not both")
        if len(code) > MAX_CODE:
            raise HTTPException(413, f"the App.jsx is larger than {MAX_CODE // 1000} k characters")
        want_repair = repair.strip().lower() in ("true", "1", "yes", "on")
        if want_repair and not has_code:
            raise HTTPException(422, "repair works on code: give the build's App.jsx")
        given = [up for up in (mobile, tablet, desktop) if up is not None]
        audit = not given                 # no design frames (Oct 13): the build measured on its own, no match score
        if given and len(given) != 3:
            raise HTTPException(422, "give all three frames (phone, tablet, desktop), or none for an audit without designs")
        if audit and not url:
            raise HTTPException(422, "an audit without design frames needs the build's address (a public URL)")
        if audit and want_repair:
            raise HTTPException(422, "repair needs design frames to aim at")
        if audit:
            frames, info, full = {}, None, {}
        else:
            frames, info, full = await _read_frames((("mobile", mobile), ("tablet", tablet), ("desktop", desktop)))
        if want_repair and any(info["sizes"][bp] != list(v) for bp, v in SIZES.items()):
            raise HTTPException(422, "repair works on the standard frame sizes (390 × 844, 768 × 1024, 1280 × 800) "
                                     "for now — check mode itself accepts these frames")
        if url:
            url = _check_url(url, resolve)
            _policy_or_422(url)
            allow = [h.lower() for h in (s.get("url_allow") or [])]
            if allow:
                from urllib.parse import urlsplit
                host = (urlsplit(url).hostname or "").lower()
                if not any(host == h or host.endswith("." + h) for h in allow):
                    raise HTTPException(422, f"this demo only checks pages from: {', '.join(allow)}")
        take_run(request, weight=3 if want_repair else 1)
        rid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        _save_frames(root / rid, frames, full)
        write_status(rid, id=rid, kind="check", state="queued", stages=[], created=time.time(),
                     source={"url": _bare(url)} if url else {"code": True}, repair=want_repair, frames=info, audit=audit)
        threading.Thread(target=check_worker, args=(rid, "audit" if audit else "url" if url else "code", url or code,
                                                    frames, want_repair),
                         daemon=True).start()
        return {"id": rid}

    @app.get("/api/runs/{rid}")
    def status(rid: str):
        if not _ID.match(rid) or not status_path(rid).exists():
            raise HTTPException(404, "no such run")
        return json.loads(status_path(rid).read_text())

    @app.get("/api/runs/{rid}/files/{path:path}")
    def files(rid: str, path: str):
        if not _ID.match(rid):
            raise HTTPException(404, "no such file")
        base = (root / rid / "bundle").resolve()
        target = (base / path).resolve()
        if base not in target.parents or not target.is_file():
            raise HTTPException(404, "no such file")
        # captured images (SVG included) are inert here: no scripts, no sniffing, no embedding of anything else
        return FileResponse(target, headers={"X-Content-Type-Options": "nosniff",
                                             "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"})

    return app


def spec_fonts(spec: dict) -> dict | None:
    """The fonts perception detected for the page ({"body", "kept"}), for the run's result."""
    return next((f["fonts"] for f in (spec.get("breakpoints") or {}).values() if (f or {}).get("fonts")), None)


def default_pipeline(run_id: str, frames: dict[str, bytes], run_dir: Path, emit) -> dict:
    """The real pipeline for one live run: perceive (vision + measurement) → loop (fluid compiler, Nemotron names
    the regions, render + score in Token Factory Sandboxes) → replay bundle for the web app."""
    import sys
    from . import config
    from .loop import LoopConfig, run_loop
    from .perceive import perceive
    from .tf_client import TFClient
    emit("perceive")
    client = TFClient(run_id=run_id, run_budget_usd=config.LIVE_RUN_BUDGET_USD)
    spec = perceive(client, frames)
    (run_dir / "spec.json").write_text(json.dumps(spec))
    emit("compile")
    res = run_loop(frames, spec, None, run_id=run_id, cfg=LoopConfig(run_budget_usd=config.LIVE_RUN_BUDGET_USD),
                   out_root=run_dir)
    emit("bundle")
    owned = (run_dir / "real").exists() or (run_dir / "assets.json").exists()
    if (run_dir / "assets.json").exists():     # owned site: the delivered code shows its own images
        from .assets import build_display
        build_display(run_dir / run_id, run_dir / "assets.json")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from export_run import export
    export(run_dir / run_id, run_dir / "frames", title="Live run", label="live", index=False, out_root=run_dir / "bundle",
           owned=run_dir if owned else None)
    return {"match": res.get("match"), "per_bp": res.get("per_bp"), "usd": res.get("spend_usd"), "fonts": spec_fonts(spec)}


def _save_owned(got: dict[str, bytes], run_dir: Path) -> None:
    """Owned site: keep the real screenshots (valid PNGs at the exact frame sizes) and the page's own images (re-checked
    here: hash, type signature, safe SVG — orchestrator/assets.verify) in the run folder. Nothing else is written."""
    import io
    from PIL import Image
    from . import config
    from .assets import verify
    for bp, wh in config.BREAKPOINTS.items():
        data = got.get(f"{bp}.real.png")
        if not data or data[:8] != b"\x89PNG\r\n\x1a\n":
            continue
        try:
            with Image.open(io.BytesIO(data)) as im:
                ok = im.size == tuple(wh)
        except Exception:
            ok = False
        if ok:
            (run_dir / "real").mkdir(parents=True, exist_ok=True)
            (run_dir / "real" / f"{bp}.png").write_bytes(data)
    try:
        manifest = json.loads(got.get("assets.json") or b"{}")
    except ValueError:
        manifest = {}
    clean, keep = verify(got, manifest)
    if keep:
        (run_dir / "assets").mkdir(parents=True, exist_ok=True)
        for name, data in keep.items():
            (run_dir / "assets" / name.split("/", 1)[1]).write_bytes(data)
        (run_dir / "assets.json").write_text(json.dumps(clean))


def _webp(png: bytes, dest: Path) -> None:
    from PIL import Image
    with Image.open(io.BytesIO(png)) as im:
        im.convert("RGB").save(dest, "WEBP", lossless=True, method=4)


def default_checker(kind: str, build: str, frames: dict[str, bytes], run_dir: Path, emit, verify) -> dict:
    """Check mode with real models and sandboxes: perception reads the design frames (vision + OCR); the build is
    captured (URL) or rendered (App.jsx) and scored in a disposable fork (orchestrator/check.py)."""
    from . import config
    from .check import check_code, check_url
    from .perceive import perceive
    from .sandbox import Sandbox
    from .tf_client import TFClient
    client = TFClient(run_id=run_dir.name, run_budget_usd=config.LIVE_RUN_BUDGET_USD)
    sb = Sandbox(meter=client)                    # sandbox time counts in the run's budget and its reported cost
    read = lambda fr: perceive(client, fr)          # noqa: E731
    if kind == "audit":                    # no design frames: measured on its own (orchestrator/check.audit_url)
        from .check import audit_url
        out = audit_url(build, sb=sb, verify=verify, emit=emit)
        out["usd"] = round(client.run_spend, 4)
        return out
    out = (check_url(build, frames, sb=sb, read_design=read, verify=verify, emit=emit) if kind == "url"
           else check_code(build, frames, sb=sb, read_design=read, emit=emit))
    out["usd"] = round(client.run_spend, 4)
    return out


def default_repairer(code: str, frames: dict[str, bytes], run_dir: Path, emit) -> dict:
    """The Nemotron repair loop (orchestrator/repair.py) with real sandboxes: ≤ 3 rounds, 3 candidates each."""
    from concurrent.futures import ThreadPoolExecutor
    from . import config
    from .check import check_code
    from .perceive import perceive
    from .repair import _propose_default, repair
    from .sandbox import Sandbox
    from .tf_client import TFClient
    # a repair weighs 3 runs against the caps, so it gets 3 runs' budget (mostly sandbox time, ~$0.55)
    client = TFClient(run_id=run_dir.name + "-repair", run_budget_usd=3 * config.LIVE_RUN_BUDGET_USD)
    sb = Sandbox(meter=client)
    spec = perceive(client, frames)               # cached vision reads: the check already read these frames
    emit("repair")
    check = lambda c: check_code(c, frames, sb=sb, read_design=None, emit=lambda *a, **k: None, spec=spec)  # noqa: E731
    with ThreadPoolExecutor(3) as ex:
        out = repair(code, spec=spec, check=check, propose=_propose_default(client), rounds=3, pmap=ex.map)
    out["usd"] = round(client.run_spend, 4)
    return out


def capture_files(*scripts: str) -> dict[str, bytes]:
    """The capture scripts uploaded into the sandbox at /opt/pc/ (capture.mjs and the modules it imports)."""
    here = Path(__file__).resolve().parents[1] / "tools" / "capture"
    return {f"/opt/pc/{n}": (here / n).read_bytes() for n in ("capture.mjs", "guard.mjs", *scripts)}


def default_capture(url: str, run_dir: Path, emit, owned: bool = False) -> tuple[dict[str, bytes], dict]:
    """Capture a public page at 390×844 / 768×1024 / 1280×800 in a Token Factory sandbox (networking on for the
    capture only, media replaced by blocks, fonts normalised — tools/capture/capture.mjs). The URL is shell-quoted
    and was validated by _check_url. → ({bp: png}, meta with "sensitive" counts)."""
    import shlex
    from .sandbox import Sandbox
    emit("capture")
    cmd = (f"cd /opt/pc && timeout 150 node /opt/pc/capture.mjs page {shlex.quote(url)} --out /work/cap --fonts /opt/pc/fonts "
           f"--wait 2000 --block-private" + (" --real --assets --own-fonts" if owned else ""))
    sb = Sandbox()
    r = sb.run(cmd, files=capture_files(), timeout_s=300, networking=True)
    if r.exit_code != 0 or not r.result_image:
        raise RuntimeError(f"the page could not be captured ({r.status})")
    got = sb.download_dir(r.result_image, "/work/cap/page")
    frames = {bp: got[f"{bp}.png"] for bp in ("mobile", "tablet", "desktop") if f"{bp}.png" in got}
    if len(frames) != 3:
        raise RuntimeError("the page could not be captured at all three sizes")
    meta = json.loads(got.get("meta.json", b"{}") or b"{}")
    if owned:
        _save_owned(got, run_dir)
    return frames, meta


app = create_app()
