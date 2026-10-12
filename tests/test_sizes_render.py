"""Renders at a run's own frame sizes (council plan, Oct 12): `render.mjs --sizes` renders each frame at its width and
first-screen height, moves the width sweep between the run's frames, and records the sizes in checks.json; the
width checks and the anti-cheat read them. Without --sizes everything stays byte-identical (selftest hashes).
Written before the code (TDD)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sandbox"))
import fluidity  # noqa: E402

RUN = {"mobile": [402, 870], "tablet": [768, 1024], "desktop": [1071, 1177]}
APP = """export default function App(){return <main className="p-4"><h1 className="text-[24px] md:text-[32px] lg:text-[40px]">
Welcome back</h1><p className="mt-2 lg:mt-6">Keep the momentum going.</p></main>}"""


def render(tmp, sizes=None):
    (tmp / "App.jsx").write_text(APP)
    cmd = ["node", "render.mjs", "--in", str(tmp / "App.jsx"), "--out", str(tmp / "out")]
    if sizes:
        (tmp / "sizes.json").write_text(json.dumps(sizes))
        cmd += ["--sizes", str(tmp / "sizes.json")]
    r = subprocess.run(cmd, cwd=ROOT / "sandbox", capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-500:] + r.stdout[-500:]
    return json.loads((tmp / "out" / "checks.json").read_text())


def png_size(p):
    b = p.read_bytes()
    return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")


def test_frames_render_at_the_runs_sizes_and_the_sweep_moves_between_them(tmp_path):
    checks = render(tmp_path, RUN)
    for bp, (w, h) in RUN.items():
        assert png_size(tmp_path / "out" / f"{bp}.png") == (w, h)
        assert checks["breakpoints"][bp]["width"] == w
    assert checks["sizes"] == RUN
    widths = sorted(int(w) for w in checks["between"])
    assert widths == [360, 375, 585, 920, 1600]          # phones, the midpoints between frames, wide
    assert all(abs(w - f[0]) > 8 for w in widths for f in RUN.values())


def test_without_sizes_nothing_changes(tmp_path):
    checks = render(tmp_path)
    assert png_size(tmp_path / "out" / "desktop.png") == (1280, 800)
    assert sorted(int(w) for w in checks["between"]) == [360, 375, 500, 1024, 1600]
    assert checks["sizes"] == {"mobile": [390, 844], "tablet": [768, 1024], "desktop": [1280, 800]}


def test_the_layout_in_effect_follows_the_runs_screens():
    # 1071 px desktop → lg: (1024) switches it on: 1030 px shows the desktop layout, 1000 px the tablet one
    assert fluidity.nearest(1030, RUN) == "desktop" and fluidity.nearest(1000, RUN) == "tablet"
    assert fluidity.nearest(700, RUN) == "mobile"
    assert [fluidity.nearest(w) for w in (500, 1024, 1600)] == ["mobile", "tablet", "desktop"]   # standard


def test_fluidity_report_uses_the_sizes_in_checks():
    bp = {k: {"text_overlaps": 0, "overflow_px": 0, "width": v[0], "height": v[1]} for k, v in RUN.items()}
    bp["desktop"]["text_overlaps"] = 2                     # the design itself has 2 overlaps at desktop
    checks = {"sizes": RUN, "breakpoints": bp,
              "between": {"1030": {"overflow_px": 0, "text_overlaps": 2}}}
    assert fluidity.report(checks)["pass"]                 # 1030 px is the desktop layout: its own 2 overlaps


def test_hidden_text_below_800_px_on_a_tall_desktop_frame_is_caught(tmp_path):
    """Red team (Oct 12): with a fixed size table, design text hidden below y=800 on a 1177 px desktop frame was
    never "on-screen", so stuffing there went unseen."""
    import integrity
    hidden = "".join(f'<p className="text-transparent">{t}</p>' for t in ("Welcome back", "Keep the momentum going",
                                                                         "Current Streak", "Time Logged"))
    (tmp_path / "App.jsx").write_text('export default function App(){return <main className="p-4">'
                                      '<div className="h-[900px] md:h-[1100px] lg:h-[850px]"></div>' + hidden + '</main>}')
    (tmp_path / "sizes.json").write_text(json.dumps(RUN))
    r = subprocess.run(["node", "render.mjs", "--in", str(tmp_path / "App.jsx"), "--out", str(tmp_path / "out"),
                        "--sizes", str(tmp_path / "sizes.json")], cwd=ROOT / "sandbox", capture_output=True, text=True,
                       timeout=180)
    assert r.returncode == 0, r.stderr[-400:]
    checks = json.loads((tmp_path / "out" / "checks.json").read_text())
    fails = integrity.failures(checks, tmp_path / "out", ["Welcome back", "Keep the momentum going", "Current Streak",
                                                          "Time Logged"])
    assert any("hidden copies" in f for f in fails), fails
