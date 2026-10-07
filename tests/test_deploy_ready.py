"""Deploy readiness (council, Oct 5): a fresh server must install everything the code imports; sandbox spend is
counted against the spend cap. Written before the fixes (TDD)."""
import ast
import json
import re
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
# import name → package name in requirements.txt (others: same name)
PKG = {"PIL": "pillow", "skimage": "scikit-image", "dotenv": "python-dotenv", "fontTools": "fonttools",
       "multipart": "python-multipart", "yaml": "pyyaml"}


def third_party_imports() -> set[str]:
    import sys
    std = set(sys.stdlib_module_names)
    local = {p.stem for d in ("orchestrator", "tools", "sandbox") for p in (ROOT / d).glob("*.py")} | {"orchestrator", "tools", "sandbox"}
    mods = set()
    for d in ("orchestrator", "tools", "sandbox"):
        for p in (ROOT / d).glob("*.py"):
            for node in ast.walk(ast.parse(p.read_text())):
                if isinstance(node, ast.Import):
                    mods |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    mods.add(node.module.split(".")[0])
    return {m for m in mods if m not in std and m not in local and m != "__future__"}


def test_requirements_cover_every_third_party_import():
    req = {re.split(r"[=<>\[ ]", l.strip())[0].lower() for l in (ROOT / "requirements.txt").read_text().splitlines()
           if l.strip() and not l.startswith("#")}
    missing = sorted(m for m in third_party_imports() if PKG.get(m, m).lower() not in req)
    assert missing == [], missing
    assert "brotli" in req, "fontTools needs brotli to read the bundled woff2 fonts"


def _sandbox(tmp_path, monkeypatch, cost=0.012, cap=40.0, spent=0.0):
    from orchestrator import config, sandbox, tf_client
    ledger = tmp_path / "spend.jsonl"
    if spent:
        ledger.write_text(json.dumps({"usd": spent}) + "\n")
    monkeypatch.setattr(config, "LEDGER_PATH", ledger)
    monkeypatch.setattr(config, "SPEND_CAP_USD", cap)
    monkeypatch.setattr(config, "SANDBOX_POLL_S", 0)
    monkeypatch.setattr(config, "api_key", lambda: "test-key")
    monkeypatch.setattr(config, "project_id", lambda: "proj")

    def handler(req: httpx.Request):
        if req.method == "POST" and req.url.path.endswith("/instances"):
            return httpx.Response(200, json={"uuid": "op1"})
        if req.url.path.endswith("/files"):
            return httpx.Response(200, json={"uuid": "f1"})
        return httpx.Response(200, json={"status": "SUCCESS", "result_image_uuid": "img",
                                         "metadata": {"result": {"state": {"exit_code": 0},
                                                                 "resources": {"cost": cost, "elapsed_time": 1.0}}}})
    return sandbox.Sandbox(client=httpx.Client(transport=httpx.MockTransport(handler))), ledger


def test_sandbox_run_cost_is_recorded_in_the_spend_ledger(tmp_path, monkeypatch):
    sb, ledger = _sandbox(tmp_path, monkeypatch)
    sb.run("echo hi", step="render")
    rows = [json.loads(l) for l in ledger.read_text().splitlines()]
    assert rows[-1]["usd"] == pytest.approx(0.012) and rows[-1]["kind"] == "sandbox" and rows[-1]["step"] == "render"


def test_sandbox_run_refused_past_the_global_cap(tmp_path, monkeypatch):
    from orchestrator.tf_client import SpendCapExceeded
    sb, _ = _sandbox(tmp_path, monkeypatch, cap=1.0, spent=1.5)
    with pytest.raises(SpendCapExceeded):
        sb.run("echo hi")


# Phase 4 deploy files (Oct 7): the Render blueprint, the API Dockerfile, the web app's Vercel config
def _render_env() -> dict:
    """key → {"value"|"sync"} from render.yaml (tiny parser: no yaml dependency)."""
    env, cur = {}, None
    for line in (ROOT / "render.yaml").read_text().splitlines():
        m = re.match(r"\s*- key: (\w+)", line)
        if m:
            cur = m.group(1)
            env[cur] = {}
            continue
        m = re.match(r"\s*(value|sync): (.+?)\s*(#.*)?$", line)
        if m and cur:
            env[cur][m.group(1)] = m.group(2).strip('"')
    return env


def test_render_env_vars_are_ones_the_server_reads():
    code = (ROOT / "orchestrator" / "config.py").read_text()
    for key in _render_env():
        assert f'"{key}"' in code, f"{key} is not read by orchestrator/config.py"


def test_render_secrets_have_no_values():
    env = _render_env()
    for key in ("NEBIUS_API_KEY", "NEBIUS_AI_PROJECT", "LIVE_PASSCODE"):
        assert env[key] == {"sync": "false"}, key
    assert env["LIVE_ENABLED"]["value"] == "1" and env["OWNED_HOSTS"]["value"] == "hafsausmani.com"


def test_render_keeps_one_instance_and_a_disk_for_state():
    y = (ROOT / "render.yaml").read_text()
    assert "numInstances: 1" in y and "mountPath: /data" in y and "healthCheckPath: /api/health" in y


def test_dockerignore_keeps_secrets_and_third_party_captures_out():
    ign = (ROOT / ".dockerignore").read_text().split()
    for p in (".env", ".env.*", "benchmarks-dev", "var", "out", "**/node_modules", ".venv"):
        assert p in ign, p


def test_dockerfile_ships_what_the_server_loads_and_stores_state_on_the_disk():
    d = (ROOT / "Dockerfile").read_text()
    for need in ("tesseract-ocr", "nodejs", "@babel/parser", "COPY sandbox/fonts", "COPY orchestrator", "COPY tools",
                 "LIVE_DIR=/data/live", "LEDGER_PATH=/data/spend.jsonl", "VISION_CACHE_DIR=/data/cache/vision",
                 "orchestrator.preflight --static", "uvicorn orchestrator.api:app"):
        assert need in d, need
    pin = re.search(r'"@babel/parser": "([\d.]+)"', (ROOT / "sandbox" / "package.json").read_text()).group(1)
    assert f"@babel/parser@{pin}" in d


def test_vercel_rewrites_client_routes_but_not_assets_or_replays():
    v = json.loads((ROOT / "ui" / "vercel.json").read_text())
    src = re.compile("^" + v["rewrites"][0]["source"].replace("(?!", "(?!") + "$")
    for path in ("/run/abc", "/live/20261006-101740-bcabfc", "/check/x", "/brand"):
        assert src.match(path), path
    for path in ("/assets/index-abc.js", "/runs/index.json", "/favicon.svg"):
        assert not src.match(path), path
    assert v["outputDirectory"] == "dist"
