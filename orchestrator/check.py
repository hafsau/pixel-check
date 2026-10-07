"""Check mode (Phase 3): how close is ANY build to its design, at every size?

Input: the three design frames and a build — a deployed URL (captured as it really looks by
tools/capture/check_page.mjs, network on, behind live mode's URL guards) or an App.jsx (rendered with network off).
The design frames are read into target texts (vision + OCR, orchestrator/perceive.py) and enter only the scoring
run: a disposable fork of the capture/render checkpoint with networking off. The report is the scorer's (per size,
components, missing text, regions) plus the width sweep at 360/375/500/1024/1600. Someone else's code is measured,
not graded: no lint / integrity verdict (sandbox/evaluate.py --check).
"""
from __future__ import annotations

import json
import shlex

from .evaluate import RENDER_CMD

SCORE_CHECK = "cd /opt/pc && python3 evaluate.py --check"
BPS = ("mobile", "tablet", "desktop")


class CheckError(RuntimeError):
    pass


class CheckRefused(CheckError):
    """The build is a page PixelCheck does not capture (live mode's URL policy)."""


def design_texts(spec: dict) -> dict[str, list]:
    """Target strings per size from the design reading: measured texts only (an unplaced guess would demand text
    at the wrong spot)."""
    return {bp: [{"text": t["text"], "box": t["box"]} for t in (spec.get("breakpoints", {}).get(bp) or {}).get("texts", [])
                 if t.get("measured") and t.get("box") and (t.get("text") or "").strip()]
            for bp in BPS}


def _score(sb, image: str, frames: dict[str, bytes], spec: dict, emit) -> dict:
    emit("score")
    files = {f"/work/targets/{bp}.png": png for bp, png in frames.items()}
    for bp, texts in design_texts(spec).items():
        files[f"/work/targets/{bp}.text.json"] = json.dumps(texts).encode()
    r = sb.run(SCORE_CHECK, image=image, files=files, disposable=True, step="check score")
    try:
        return json.loads(r.stdout)
    except (json.JSONDecodeError, TypeError):
        raise CheckError(f"the scoring run failed ({r.status})") from None


def check_url(url: str, frames: dict[str, bytes], *, sb, read_design, verify, emit) -> dict:
    """read_design(frames) → perception spec; verify(meta) raises CheckRefused for pages not to capture."""
    from .api import capture_files
    emit("capture")
    cmd = f"cd /opt/pc && node /opt/pc/check_page.mjs {shlex.quote(url)} --out /work/out --wait 2000 --block-private"
    r = sb.run(cmd, files=capture_files("check_page.mjs"), timeout_s=300, networking=True, step="check capture")
    if r.exit_code != 0 or not r.result_image:
        raise CheckError("the build could not be captured — is the address public and reachable?")
    got = sb.download_dir(r.result_image, "/work/out")
    meta = json.loads(got.get("meta.json") or b"{}")
    verify(meta)
    emit("read design")
    spec = read_design(frames)
    report = _score(sb, r.result_image, frames, spec, emit)
    return {"report": report, "build": {bp: got[f"{bp}.png"] for bp in BPS if f"{bp}.png" in got}, "meta": meta,
            "design_texts": design_texts(spec), "dom": _doms(got), "nodes": _doms(got, "nodes")}


def _doms(got: dict, kind: str = "dom") -> dict[str, list]:
    out = {}
    for bp in BPS:
        try:
            out[bp] = json.loads(got.get(f"{bp}.{kind}.json") or b"[]")
        except (json.JSONDecodeError, TypeError):
            out[bp] = []
    return out


def check_code(code: str, frames: dict[str, bytes], *, sb, read_design, emit, spec: dict | None = None) -> dict:
    """An App.jsx (React + Tailwind, one file) rendered with network off, then scored in check mode. spec: a design
    reading already made (the repair loop checks several versions against the same frames)."""
    emit("render")
    r = sb.run(RENDER_CMD, files={"/work/App.jsx": code.encode()}, step="check render")
    if not r.ok or not r.result_image:
        raise CheckError("the code could not be rendered")
    got = sb.download_dir(r.result_image, "/work/out")
    if spec is None:
        emit("read design")
        spec = read_design(frames)
    report = _score(sb, r.result_image, frames, spec, emit)
    return {"report": report, "build": {bp: got[f"{bp}.png"] for bp in BPS if f"{bp}.png" in got}, "meta": {},
            "design_texts": design_texts(spec), "dom": _doms(got), "nodes": _doms(got, "nodes")}
