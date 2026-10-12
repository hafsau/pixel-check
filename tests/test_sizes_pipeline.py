"""A run's own frame sizes reach the sandbox (council plan, Oct 12): inside frames.use(sizes), renders and URL captures
get /work/sizes.json + --sizes; standard runs send exactly the commands and files they always did. The pipelines
wrap themselves in frames.use(sizes read from their frames). Fake sandboxes — no network, no models. Written
before the code (TDD)."""
import json

from orchestrator import check as C
from orchestrator import evaluate as E
from orchestrator import frames as F
from test_check import FRAMES, SPEC, FakeSB

RUN = {"mobile": (402, 870), "tablet": (768, 1024), "desktop": (1071, 1177)}


class EvalSB:
    def __init__(self):
        self.runs = []

    def run(self, cmd, **kw):
        self.runs.append((cmd, kw))

        class R:
            ok, result_image, stdout, stderr, status, exit_code = True, "img", json.dumps({"match": 50}), "", "SUCCESS", 0
        return R()

    def download_dir(self, image, path):
        return {}


def test_standard_renders_are_unchanged():
    sb = EvalSB()
    E.evaluate(sb, "export default function App(){return null}", {"mobile": b"m"})
    cmd, kw = sb.runs[0]
    assert cmd == E.RENDER_CMD and set(kw["files"]) == {"/work/App.jsx"}


def test_renders_inside_a_run_get_its_sizes():
    sb = EvalSB()
    with F.use(RUN):
        E.evaluate(sb, "export default function App(){return null}", {"mobile": b"m"})
    cmd, kw = sb.runs[0]
    assert "render.mjs --sizes /work/sizes.json" in cmd and cmd.count("timeout ") >= 2
    assert json.loads(kw["files"]["/work/sizes.json"]) == {bp: list(v) for bp, v in RUN.items()}


def test_check_mode_capture_and_code_render_get_the_sizes():
    sb = FakeSB()
    with F.use(RUN):
        C.check_url("https://build.example/", FRAMES, sb=sb, read_design=lambda f: SPEC, verify=lambda m: None,
                    emit=lambda *a, **k: None)
    cap_cmd, cap = sb.runs[0]
    assert "check_page.mjs" in cap_cmd and "--sizes /work/sizes.json" in cap_cmd
    assert json.loads(cap["files"]["/work/sizes.json"])["desktop"] == [1071, 1177]
    sb = FakeSB()
    C.check_url("https://build.example/", FRAMES, sb=sb, read_design=lambda f: SPEC, verify=lambda m: None,
                emit=lambda *a, **k: None)
    assert "--sizes" not in sb.runs[0][0] and "/work/sizes.json" not in sb.runs[0][1]["files"]
