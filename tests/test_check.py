"""Check mode orchestration (orchestrator/check.py, Phase 3): capture the build in the sandbox (network on, guarded,
check_page.mjs), verify where it went (live mode's checks), read the design frames into target texts, score in a
disposable run forked from the capture (network off; the design frames enter only that run). Fake sandbox — no
network, no models. Written before the module (TDD, Oct 6)."""
import json
import shlex
from dataclasses import dataclass

import pytest

from orchestrator import check as C


@dataclass
class R:
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    result_image: str | None = "img-capture"
    status: str = "SUCCESS"

    @property
    def ok(self):
        return self.exit_code == 0


class FakeSB:
    def __init__(self, score=None, capture_ok=True):
        self.runs = []
        self.score = score or {"mode": "check", "match": 71.5, "breakpoints": {"mobile": {"score": 71.5}}, "fluidity": {"pass": False}}
        self.capture_ok = capture_ok

    def run(self, cmd, **kw):
        self.runs.append((cmd, kw))
        if "evaluate.py --check" in cmd:
            return R(stdout=json.dumps(self.score), result_image=None)
        return R(exit_code=0 if self.capture_ok else 1, result_image="img-capture" if self.capture_ok else None)

    def download_dir(self, image, path):
        meta = {"sensitive": {"password": 0}, "navigation": {"final_url": "https://build.example/", "final_urls": ["https://build.example/"]}}
        return {"meta.json": json.dumps(meta).encode(), "mobile.png": b"m", "tablet.png": b"t", "desktop.png": b"d",
                "checks.json": b"{}"}


FRAMES = {"mobile": b"PNGm", "tablet": b"PNGt", "desktop": b"PNGd"}
SPEC = {"breakpoints": {bp: {"texts": [{"text": "Plan your week", "box": [10, 10, 200, 30], "measured": True},
                                       {"text": "guess", "box": [0, 0, 200, 16], "measured": False}]} for bp in FRAMES}}


def test_capture_then_verify_then_score_in_a_fork():
    sb, seen = FakeSB(), []
    out = C.check_url("https://build.example/?x=1&y=2", FRAMES, sb=sb, read_design=lambda f: SPEC,
                      verify=lambda meta: seen.append(meta), emit=lambda *a, **k: None)
    (cap_cmd, cap), (score_cmd, sc) = sb.runs
    assert cap["networking"] is True and "check_page.mjs" in cap_cmd and "--block-private" in cap_cmd
    assert shlex.quote("https://build.example/?x=1&y=2") in cap_cmd
    assert {"/opt/pc/check_page.mjs", "/opt/pc/guard.mjs"} <= set(cap["files"])
    assert not any(k.startswith("/work/targets") for k in cap["files"])            # designs never in the capture run
    assert sc["disposable"] is True and not sc.get("networking") and sc["image"] == "img-capture"
    assert sc["files"]["/work/targets/mobile.png"] == b"PNGm"
    texts = json.loads(sc["files"]["/work/targets/mobile.text.json"])
    assert texts == [{"text": "Plan your week", "box": [10, 10, 200, 30]}]           # measured texts only
    assert seen and seen[0]["navigation"]["final_url"] == "https://build.example/"
    assert out["report"]["match"] == 71.5 and out["build"]["mobile"] == b"m"


def test_a_refusal_stops_before_reading_or_scoring():
    sb, read = FakeSB(), []

    def verify(meta):
        raise C.CheckRefused("the build redirected somewhere private")
    with pytest.raises(C.CheckRefused):
        C.check_url("https://build.example/", FRAMES, sb=sb, read_design=lambda f: read.append(1) or SPEC,
                    verify=verify, emit=lambda *a, **k: None)
    assert len(sb.runs) == 1 and not read


def test_a_failed_capture_is_reported_plainly():
    with pytest.raises(C.CheckError, match="could not be captured"):
        C.check_url("https://build.example/", FRAMES, sb=FakeSB(capture_ok=False), read_design=lambda f: SPEC,
                    verify=lambda m: None, emit=lambda *a, **k: None)


def test_check_code_renders_without_network_and_scores_in_check_mode():
    sb = FakeSB()
    out = C.check_code("export default function App(){return <main>Hi</main>}", FRAMES, sb=sb,
                       read_design=lambda f: SPEC, emit=lambda *a, **k: None)
    (render_cmd, rk), (score_cmd, sk) = sb.runs
    assert not rk.get("networking") and "/work/App.jsx" in rk["files"] and "render.mjs" in render_cmd
    assert "evaluate.py --check" in score_cmd and sk["disposable"] is True
    assert out["report"]["mode"] == "check"


def test_stages_are_emitted_in_order():
    stages = []
    C.check_url("https://build.example/", FRAMES, sb=FakeSB(), read_design=lambda f: SPEC, verify=lambda m: None,
                emit=lambda s, **k: stages.append(s))
    assert stages == ["capture", "read design", "score"]
