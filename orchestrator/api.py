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
_SECRET = re.compile(r"(?i)(bearer\s+\S+|sk-[\w-]+|api[_-]?key\S*|authorization\S*|token\S*)")


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
        try:
            return [r if isinstance(r, list) else [r, None] for r in json.loads(self.path.read_text())]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def left(self, ip: str | None = None) -> tuple[int, int]:
        runs = self._read()
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
            runs = self._read() + [[time.time(), ip]]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(runs))
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


def create_app(pipeline=None, live_dir: Path | None = None, settings: dict | None = None, capture=None,
               resolver=None) -> FastAPI:
    from . import config
    s = {"enabled": config.LIVE_ENABLED, "passcode": config.LIVE_PASSCODE, "daily": config.LIVE_DAILY_RUNS,
         "total": config.LIVE_TOTAL_RUNS, "origins": config.LIVE_ORIGINS, "per_ip": config.LIVE_PER_IP_DAILY,
         "trust_proxy": config.LIVE_TRUST_PROXY, "url_allow": config.LIVE_URL_ALLOW, "owned_hosts": config.OWNED_HOSTS}
    s.update(settings or {})
    root = Path(live_dir or config.LIVE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    caps = _Caps(root / "caps.json", s["daily"], s["total"], s.get("per_ip"))

    def visitor(request: Request) -> str:
        """The client address; X-Forwarded-For only behind a trusted proxy (else anyone could pick an address)."""
        if s.get("trust_proxy"):
            fwd = request.headers.get("x-forwarded-for", "")
            if fwd.strip():
                return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
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
    resolve = resolver or _resolve
    app = FastAPI(title="PixelCheck live", docs_url=None, redoc_url=None)
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
        try:
            write_status(rid, state="running")
            if url is not None:          # capture the page at the three breakpoints first (sandbox, network on)
                from urllib.parse import urlsplit
                host = (urlsplit(url).hostname or "").lower()
                owned = any(host == h or host.endswith("." + h) for h in (s.get("owned_hosts") or []))
                frames, meta = run_capture(url, run_dir, emit, **({"owned": True} if owned else {}))
                _verify_capture(meta or {}, resolve)
                sens = (meta or {}).get("sensitive") or {}
                if any(sens.get(k) for k in ("password", "payment", "signin", "crypto")):
                    raise _Refused("this page has sign-in, password, payment or wallet fields — PixelCheck does not "
                                   "rebuild login, checkout or wallet pages from a URL; upload your own design frames instead")
                (run_dir / "frames").mkdir(parents=True, exist_ok=True)
                for bp, data in frames.items():
                    (run_dir / "frames" / f"{bp}.png").write_bytes(data)
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

    @app.get("/api/health")
    def health():
        d, t = caps.left()
        return {"live": bool(s["enabled"]), "runs_left_today": d, "runs_left_total": t}

    @app.post("/api/runs", status_code=202)
    async def start(request: Request, mobile: UploadFile = File(...), tablet: UploadFile = File(...),
                    desktop: UploadFile = File(...), passcode: str = Form("")):
        if not s["enabled"]:
            raise HTTPException(503, "live mode is switched off; replays still work")
        if not s["passcode"] or not hmac.compare_digest(passcode.encode(), str(s["passcode"]).encode()):
            raise HTTPException(403, "wrong passcode")
        frames = {}
        for bp, up in (("mobile", mobile), ("tablet", tablet), ("desktop", desktop)):
            data = await up.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise HTTPException(413, f"{bp}: the frame is larger than {MAX_BYTES // (1024 * 1024)} MB")
            _check_png(bp, data)
            frames[bp] = data
        if not caps.take(visitor(request)):
            raise HTTPException(429, "the live-run limit is reached; replays still work")
        rid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        run_dir = root / rid
        (run_dir / "frames").mkdir(parents=True)
        for bp, data in frames.items():
            (run_dir / "frames" / f"{bp}.png").write_bytes(data)
        write_status(rid, state="queued", stages=[], created=time.time())
        threading.Thread(target=worker, args=(rid, frames), daemon=True).start()
        return {"id": rid}

    @app.post("/api/runs/url", status_code=202)
    def start_url(request: Request, url: str = Form(""), owns: str = Form(""), passcode: str = Form("")):
        if not s["enabled"]:
            raise HTTPException(503, "live mode is switched off; replays still work")
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
        if not caps.take(visitor(request)):
            raise HTTPException(429, "the live-run limit is reached; replays still work")
        rid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        (root / rid).mkdir(parents=True)
        write_status(rid, id=rid, state="queued", stages=[], created=time.time(), source={"url": _bare(url)})
        threading.Thread(target=worker, args=(rid, None, url), daemon=True).start()
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
    return {"match": res.get("match"), "per_bp": res.get("per_bp"), "usd": res.get("spend_usd")}


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


def default_capture(url: str, run_dir: Path, emit, owned: bool = False) -> tuple[dict[str, bytes], dict]:
    """Capture a public page at 390×844 / 768×1024 / 1280×800 in a Token Factory sandbox (networking on for the
    capture only, media replaced by blocks, fonts normalised — tools/capture/capture.mjs). The URL is shell-quoted
    and was validated by _check_url. → ({bp: png}, meta with "sensitive" counts)."""
    import shlex
    from .sandbox import Sandbox
    emit("capture")
    script = (Path(__file__).resolve().parents[1] / "tools" / "capture" / "capture.mjs").read_bytes()
    cmd = (f"cd /opt/pc && node /opt/pc/capture.mjs page {shlex.quote(url)} --out /work/cap --fonts /opt/pc/fonts "
           f"--wait 2000 --block-private" + (" --real --assets" if owned else ""))
    sb = Sandbox()
    r = sb.run(cmd, files={"/opt/pc/capture.mjs": script}, timeout_s=300, networking=True)
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
