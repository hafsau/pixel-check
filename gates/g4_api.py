"""G4 (API path): spawn a sandbox via raw HTTPS with networking OFF, poll, report.

Usage: .venv/bin/python gates/g4_api.py
Reads NEBIUS_API_KEY + NEBIUS_AI_PROJECT from .env. Never prints the key.
Never retries POST /instances (duplicate launches).
"""
import json, os, sys, time
import httpx
from dotenv import load_dotenv

load_dotenv()
KEY, PROJECT = os.environ.get("NEBIUS_API_KEY"), os.environ.get("NEBIUS_AI_PROJECT")
if not (KEY and PROJECT):
    sys.exit("NEBIUS_API_KEY / NEBIUS_AI_PROJECT missing from .env")
BASE = "https://api.tokenfactory.nebius.com/sandboxes/v1"
H = {"Authorization": f"Bearer {KEY}", "Project": PROJECT}

CMD = ("python3 -c \"import urllib.request as u\n"
       "try: print('NET', u.urlopen('https://example.com', timeout=5).status)\n"
       "except Exception as e: print('NET_BLOCKED', type(e).__name__)\n"
       "print(2+2)\"")


def spawn(body):
    t0 = time.time()
    r = httpx.post(f"{BASE}/instances", headers=H, json=body, timeout=30)
    print("POST", r.status_code, r.text[:500])
    r.raise_for_status()
    op = r.json()
    op_id = op.get("uuid") or op.get("id") or op.get("operation_id")
    while True:
        g = httpx.get(f"{BASE}/operations/{op_id}", headers=H, timeout=30)
        g.raise_for_status()
        j = g.json()
        if j.get("status") not in ("PENDING", "RUNNING", "EXECUTING", "QUEUED", None):
            break
        time.sleep(1)
    print(f"spawn->result {time.time() - t0:.1f}s")
    print(json.dumps(j, indent=1)[:3000])


if __name__ == "__main__":
    spawn({"image": "tag:python:3.12-slim", "command": CMD, "shell": True,
           "networking": {"enabled": False}, "timeout": 60, "disposable": True})
