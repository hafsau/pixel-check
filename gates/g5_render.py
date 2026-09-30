"""G5: render an App.jsx at 3 breakpoints inside the sandbox via the API (network off).

Usage: .venv/bin/python -m gates.g5_render [path/to/App.jsx]
Pass: 3 PNGs at exact sizes, Inter loaded, network blocked, deterministic across 2 runs.
Outputs are fetched from the run's checkpoint image (stdout is capped at 64 KiB by the API).
"""
import hashlib, json, pathlib, sys

from orchestrator import config
from orchestrator.sandbox import Sandbox

app = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "sandbox/selftest/App.jsx").read_bytes()
out_dir = pathlib.Path("out/g5"); out_dir.mkdir(parents=True, exist_ok=True)
sb = Sandbox()
cmd = ("node -e \"require('http').get('http://example.com',()=>console.error('NET_OPEN')).on('error',()=>console.error('NET_BLOCKED'))\"; "
       "cd /opt/pc && node render.mjs --in /work/App.jsx --out /work/out > /work/out.log")
hashes, ok = [], True
for i in range(2):
    r = sb.run(cmd, files={"/work/App.jsx": app})
    print(f"run{i}: status={r.status} exit={r.exit_code} wall={r.wall_s:.1f}s vm={r.elapsed_s:.2f}s cost={r.cost} "
          f"checkpoint={r.result_image} stderr={r.stderr.strip()[:200]!r}")
    ok &= r.ok and "NET_BLOCKED" in r.stderr
    files = sb.download_dir(r.result_image, "/work/out")
    checks = json.loads(files["checks.json"])
    h = {}
    for bp, (w, hgt) in config.BREAKPOINTS.items():
        png = files[f"{bp}.png"]
        pw, ph = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
        ok &= (pw, ph) == (w, hgt) and checks["breakpoints"][bp]["fonts_ok"]
        (out_dir / f"{bp}.png").write_bytes(png)
        h[bp] = hashlib.sha256(png).hexdigest()[:16]
    hashes.append(h)
    print(f"  files={sorted(files)} sizes/fonts ok={ok} hashes={h}")
    print("  between:", {k: (v["overflow_px"], v["text_overlaps"]) for k, v in checks["between"].items()})
det = hashes[0] == hashes[1]
print("DETERMINISTIC" if det else "NON-DETERMINISTIC", "| G5", "PASS" if ok and det else "FAIL")
