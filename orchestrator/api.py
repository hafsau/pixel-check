"""Live mode API: upload the three frames of one screen, Pixel-Check runs the pipeline in the background (perceive →
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

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
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

    def __init__(self, path: Path, daily: int, total: int):
        self.path, self.daily, self.total = path, daily, total
        self.lock = threading.Lock()

    def _read(self) -> list[float]:
        try:
            return json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def left(self) -> tuple[int, int]:
        runs = self._read()
        today = time.strftime("%Y-%m-%d")
        n_today = sum(1 for t in runs if time.strftime("%Y-%m-%d", time.localtime(t)) == today)
        return max(0, self.daily - n_today), max(0, self.total - len(runs))

    def take(self) -> bool:
        with self.lock:
            d, t = self.left()
            if d <= 0 or t <= 0:
                return False
            runs = self._read() + [time.time()]
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


def create_app(pipeline=None, live_dir: Path | None = None, settings: dict | None = None, capture=None,
               resolver=None) -> FastAPI:
    from . import config
    s = {"enabled": config.LIVE_ENABLED, "passcode": config.LIVE_PASSCODE, "daily": config.LIVE_DAILY_RUNS,
         "total": config.LIVE_TOTAL_RUNS, "origins": config.LIVE_ORIGINS}
    s.update(settings or {})
    root = Path(live_dir or config.LIVE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    caps = _Caps(root / "caps.json", s["daily"], s["total"])
    run_pipeline = pipeline or default_pipeline
    run_capture = capture or default_capture
    resolve = resolver or _resolve
    app = FastAPI(title="Pixel-Check live", docs_url=None, redoc_url=None)
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
        try:
            write_status(rid, state="running")
            if url is not None:          # capture the page at the three breakpoints first (sandbox, network on)
                frames, meta = run_capture(url, run_dir, emit)
                sens = (meta or {}).get("sensitive") or {}
                if sens.get("password") or sens.get("payment"):
                    raise _Refused("this page has password or payment fields — Pixel-Check does not rebuild login or "
                                   "checkout pages from a URL; upload your own design frames instead")
                (run_dir / "frames").mkdir(parents=True, exist_ok=True)
                for bp, data in frames.items():
                    (run_dir / "frames" / f"{bp}.png").write_bytes(data)
            result = run_pipeline(rid, frames, run_dir, emit)
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
    async def start(mobile: UploadFile = File(...), tablet: UploadFile = File(...), desktop: UploadFile = File(...),
                    passcode: str = Form("")):
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
        if not caps.take():
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
    def start_url(url: str = Form(""), owns: str = Form(""), passcode: str = Form("")):
        if not s["enabled"]:
            raise HTTPException(503, "live mode is switched off; replays still work")
        if not s["passcode"] or not hmac.compare_digest(passcode.encode(), str(s["passcode"]).encode()):
            raise HTTPException(403, "wrong passcode")
        if owns.strip().lower() not in ("true", "1", "yes", "on"):
            raise HTTPException(422, "confirm that you own this page or have permission to rebuild it")
        url = _check_url(url, resolve)
        if not caps.take():
            raise HTTPException(429, "the live-run limit is reached; replays still work")
        rid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        (root / rid).mkdir(parents=True)
        write_status(rid, id=rid, state="queued", stages=[], created=time.time(), source={"url": url})
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
        return FileResponse(target)

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
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from export_run import export
    export(run_dir / run_id, run_dir / "frames", title="Live run", label="live", index=False, out_root=run_dir / "bundle")
    return {"match": res.get("match"), "per_bp": res.get("per_bp"), "usd": res.get("spend_usd")}


def default_capture(url: str, run_dir: Path, emit) -> tuple[dict[str, bytes], dict]:
    """Capture a public page at 390×844 / 768×1024 / 1280×800 in a Token Factory sandbox (networking on for the
    capture only, media replaced by blocks, fonts normalised — tools/capture/capture.mjs). The URL is shell-quoted
    and was validated by _check_url. → ({bp: png}, meta with "sensitive" counts)."""
    import shlex
    from .sandbox import Sandbox
    emit("capture")
    script = (Path(__file__).resolve().parents[1] / "tools" / "capture" / "capture.mjs").read_bytes()
    cmd = (f"cd /opt/pc && node /opt/pc/capture.mjs page {shlex.quote(url)} --out /work/cap --fonts /opt/pc/fonts "
           f"--wait 2000")
    sb = Sandbox()
    r = sb.run(cmd, files={"/opt/pc/capture.mjs": script}, timeout_s=300, networking=True)
    if r.exit_code != 0 or not r.result_image:
        raise RuntimeError(f"the page could not be captured ({r.status})")
    got = sb.download_dir(r.result_image, "/work/cap/page")
    frames = {bp: got[f"{bp}.png"] for bp in ("mobile", "tablet", "desktop") if f"{bp}.png" in got}
    if len(frames) != 3:
        raise RuntimeError("the page could not be captured at all three sizes")
    meta = json.loads(got.get("meta.json", b"{}") or b"{}")
    return frames, meta


app = create_app()
