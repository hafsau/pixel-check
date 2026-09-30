"""Token Factory Sandboxes client (raw HTTPS; the SDK is not used — see docs/PLATFORM.md).

Rules enforced here, not by callers:
- every spawn sets networking off, shell on, an explicit timeout and the max output cap;
- POST /instances is never retried (a retry can launch a duplicate VM);
- reads (polls, uploads) retry on transient errors.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from . import config

_TERMINAL = {"SUCCESS", "FAILED", "CANCELLED", "ERROR", "TIMEOUT"}


@dataclass
class RunResult:
    op_id: str
    status: str
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    stdout_truncated: bool
    cost: float | None
    elapsed_s: float | None
    wall_s: float
    result_image: str | None  # checkpoint UUID (None when disposable)
    error: str | None
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "SUCCESS" and self.exit_code == 0 and not self.timed_out


class Sandbox:
    def __init__(self, client: httpx.Client | None = None):
        self._h = {"Authorization": f"Bearer {config.api_key()}", "Project": config.project_id()}
        self._c = client or httpx.Client(timeout=60)

    def _get(self, path: str) -> dict:
        for attempt in range(5):
            try:
                r = self._c.get(f"{config.SANDBOX_BASE}{path}", headers=self._h)
                if r.status_code == 429 or r.status_code >= 500:
                    raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
                r.raise_for_status()
                return r.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                time.sleep(min(2 ** attempt, 10))
        raise RuntimeError(f"GET {path} failed after retries")

    def upload(self, data: bytes) -> str:
        """Upload bytes; returns file UUID. Content-addressed, so retrying is safe."""
        for attempt in range(4):
            try:
                r = self._c.post(f"{config.SANDBOX_BASE}/files", headers={**self._h, "Content-Type": "application/octet-stream"}, content=data)
                r.raise_for_status()
                return r.json()["uuid"]
            except httpx.TransportError:
                time.sleep(2 ** attempt)
        raise RuntimeError("file upload failed after retries")

    def run(self, command: str, *, image: str = config.RUNTIME_IMAGE, files: dict[str, bytes] | None = None,
            disposable: bool = False, timeout_s: int = config.SANDBOX_TIMEOUT_S) -> RunResult:
        mapped = {path: {"uuid": self.upload(data), "mode": "0644"} for path, data in (files or {}).items()}
        body = {
            "image": image, "command": command, "shell": True,
            "networking": {"enabled": False},
            "timeout": timeout_s, "disposable": disposable,
            "truncate_output_at": config.SANDBOX_OUTPUT_CAP, "files": mapped,
        }
        t0 = time.time()
        r = self._c.post(f"{config.SANDBOX_BASE}/instances", headers=self._h, json=body)  # never retried
        r.raise_for_status()
        op_id = r.json()["uuid"]
        deadline = t0 + timeout_s + 60
        while True:
            op = self._get(f"/operations/{op_id}")
            if op.get("status") in _TERMINAL:
                break
            if time.time() > deadline:
                self._c.delete(f"{config.SANDBOX_BASE}/operations/{op_id}", headers=self._h)
                raise TimeoutError(f"sandbox op {op_id} exceeded local deadline")
            time.sleep(config.SANDBOX_POLL_S)
        res = (op.get("metadata") or {}).get("result") or {}
        out, err, state = res.get("stdout") or {}, res.get("stderr") or {}, res.get("state") or {}
        resources = res.get("resources") or {}
        return RunResult(
            op_id=op_id, status=op.get("status"), exit_code=state.get("exit_code"),
            timed_out=bool(state.get("timed_out")), stdout=_decode(out), stderr=_decode(err),
            stdout_truncated=bool(out.get("truncated")), cost=resources.get("cost"),
            elapsed_s=resources.get("elapsed_time"), wall_s=time.time() - t0,
            result_image=op.get("result_image_uuid"), error=op.get("error"), raw=op,
        )


    def download_dir(self, image: str, path: str) -> dict[str, bytes]:
        """Fetch a directory from a checkpoint image as {relative_name: bytes}.

        Used for render outputs: stdout is silently capped at 64 KiB by the API regardless of
        `truncate_output_at` (and reports truncated=false), so PNGs never go through stdout.
        """
        import io, tarfile
        for attempt in range(4):
            try:
                r = self._c.get(f"{config.SANDBOX_BASE}/inspect/{image}/archive", headers=self._h, params={"path": path})
                if r.status_code in (425, 429) or r.status_code >= 500:
                    raise httpx.TransportError(f"retryable {r.status_code}")
                r.raise_for_status()
                break
            except httpx.TransportError:
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"archive {path} from {image} failed after retries")
        out = {}
        with tarfile.open(fileobj=io.BytesIO(r.content)) as tar:
            for m in tar.getmembers():
                if m.isfile():
                    out[m.name.lstrip("./")] = tar.extractfile(m).read()
        return out


def _decode(stream: dict) -> str:
    v = stream.get("value") or ""
    if stream.get("encoding") == "base64":
        import base64
        return base64.b64decode(v).decode("utf-8", "replace")
    return v
