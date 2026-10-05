"""Dev capture tool (tools/capture/capture.mjs --state): media that appears or is re-rendered after the click must be
replaced exactly like media in the base frame (netflix "Get help": the base showed the chevron as a grey block, the
state frame the real chevron → an inconsistent target). Written before the fix (TDD, Oct 2)."""
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CAP = ROOT / "tools" / "capture"
pytestmark = pytest.mark.skipif(not (CAP / "node_modules").exists(), reason="capture deps not installed")


def test_media_revealed_by_the_click_is_replaced_like_the_base(tmp_path):
    url = (ROOT / "tests" / "fixtures" / "capture" / "disclosure.html").as_uri()
    for extra in ([], ["--state", "help", "--click", "#t"]):          # base frame, then the state frame
        r = subprocess.run(["node", "capture.mjs", "fx", url, "--bps", "mobile", "--out", str(tmp_path), "--wait", "0"]
                           + extra, cwd=CAP, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr[-500:]
    d = tmp_path / "fx"
    for f in ("mobile.png", "mobile.help.png"):
        im = np.asarray(Image.open(d / f).convert("RGB")).astype(int)
        red = (im[..., 0] > 200) & (im[..., 1] < 60) & (im[..., 2] < 60)
        assert red.sum() == 0, (f, int(red.sum()))                    # no original media pixels left
    st = np.asarray(Image.open(d / "mobile.help.png").convert("RGB")).astype(int)
    grey = (np.abs(st - [212, 212, 216]).sum(axis=2) < 6)
    assert grey.sum() >= 16 * 16 + 32 * 32 - 40                       # the chevron and the new icon, as blocks


def test_capture_reports_password_and_payment_fields(tmp_path):
    """Live mode from a URL refuses login / checkout pages: the capture reports them in meta.json."""
    import json
    url = (ROOT / "tests" / "fixtures" / "capture" / "login.html").as_uri()
    r = subprocess.run(["node", "capture.mjs", "fx", url, "--bps", "mobile", "--out", str(tmp_path), "--wait", "0"],
                       cwd=CAP, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-500:]
    meta = json.loads((tmp_path / "fx" / "meta.json").read_text())
    assert meta["sensitive"]["password"] == 1 and meta["sensitive"]["payment"] >= 1
    plain = (ROOT / "tests" / "fixtures" / "capture" / "disclosure.html").as_uri()
    subprocess.run(["node", "capture.mjs", "fx2", plain, "--bps", "mobile", "--out", str(tmp_path), "--wait", "0"],
                   cwd=CAP, capture_output=True, text=True, timeout=120)
    m2 = json.loads((tmp_path / "fx2" / "meta.json").read_text())
    assert m2["sensitive"] == {"password": 0, "payment": 0}
