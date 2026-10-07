"""Deploy preflight: what the live server needs before it takes runs. Never prints a secret's value.

    python -m orchestrator.preflight [--static] [--json]

--static: only what the image itself must contain (tesseract, node + the JSX tool, fonts, capture scripts) — run at
image build time. Without it, also the environment (secrets present, live-mode settings, writable storage, the
spend cap inside the credit). Exit code 1 when any check fails.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREDIT_USD = 50.0          # the hackathon credit (CLAUDE.md §3)


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail}


def _static() -> list[dict]:
    out = []
    tess = shutil.which("tesseract")
    ver = ""
    if tess:
        try:
            ver = subprocess.run([tess, "--version"], capture_output=True, text=True, timeout=20).stdout.splitlines()[0]
        except Exception:
            ver = "?"
    out.append(_check("tesseract", bool(tess), ver or "not installed (apt install tesseract-ocr)"))
    try:
        from .jsx_edit import tag
        code, els = tag('export default function App(){return <main className="p-4">x</main>}')
        out.append(_check("node + JSX tool", 'data-pc="0"' in code and els[0]["tag"] == "main", "jsx_tool tag works"))
    except Exception as e:
        out.append(_check("node + JSX tool", False, f"{type(e).__name__}: {str(e)[:160]}"))
    fonts = [ROOT / "sandbox" / "fonts" / f"inter-latin-{w}-normal.woff2" for w in (400, 500, 600, 700)]
    missing = [f.name for f in fonts if not f.exists()]
    out.append(_check("fonts", not missing, "missing: " + ", ".join(missing) if missing else "Inter 400–700"))
    try:
        from .api import capture_files
        files = capture_files("check_page.mjs")
        out.append(_check("capture scripts", len(files) == 3, ", ".join(Path(k).name for k in files)))
    except Exception as e:
        out.append(_check("capture scripts", False, f"{type(e).__name__}: {str(e)[:160]}"))
    return out


def _writable(name: str, path: Path) -> dict:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".preflight"
        probe.write_text("ok")
        probe.unlink()
        return _check(f"writable {name}", True, str(path))
    except OSError as e:
        return _check(f"writable {name}", False, f"{path}: {e.strerror or e}")


def _env(env: dict) -> list[dict]:
    out = []
    for k in ("NEBIUS_API_KEY", "NEBIUS_AI_PROJECT"):
        out.append(_check(f"env {k}", bool((env.get(k) or "").strip()), "set" if env.get(k) else "missing"))
    live = (env.get("LIVE_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")
    out.append(_check("env LIVE_PASSCODE", not live or bool((env.get("LIVE_PASSCODE") or "").strip()),
                      "set" if env.get("LIVE_PASSCODE") else ("missing (live mode is on)" if live else "not needed")))
    out.append(_check("env LIVE_ORIGINS", not live or bool((env.get("LIVE_ORIGINS") or "").strip()),
                      env.get("LIVE_ORIGINS", "") if env.get("LIVE_ORIGINS") else
                      ("missing — the web app's origin, e.g. https://<app>.vercel.app" if live else "not needed")))
    try:
        cap = float(env.get("SPEND_CAP_USD") or 40)
        out.append(_check("spend cap", 0 < cap <= CREDIT_USD, f"${cap:g} of ${CREDIT_USD:g} credit"))
    except ValueError:
        out.append(_check("spend cap", False, "SPEND_CAP_USD is not a number"))
    out.append(_writable("LIVE_DIR", Path(env.get("LIVE_DIR") or ROOT / "var" / "live")))
    out.append(_writable("LEDGER_PATH", Path(env.get("LEDGER_PATH") or ROOT / "var" / "spend.jsonl").parent))
    out.append(_writable("VISION_CACHE_DIR", Path(env.get("VISION_CACHE_DIR") or ROOT / "var" / "cache" / "vision")))
    return out


def run(env: dict, static: bool = False) -> list[dict]:
    return _static() + ([] if static else _env(env))


def main(argv: list[str]) -> int:
    res = run(dict(os.environ), static="--static" in argv)
    if "--json" in argv:
        print(json.dumps(res, indent=1))
    else:
        for r in res:
            print(f"{'ok  ' if r['ok'] else 'FAIL'}  {r['check']:<22} {r['detail']}")
    return 0 if all(r["ok"] for r in res) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
