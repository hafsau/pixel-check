"""URL guard (tools/capture/guard.mjs) — council red team, Oct 7: IPv4-mapped / -compatible / NAT64 / 6to4 IPv6 forms
of private addresses passed (the URL parser rewrites [::ffff:127.0.0.1] to [::ffff:7f00:1]), and WebSockets were
never routed, so a captured page could read an internal service. Written before the fix (TDD)."""
import json
import subprocess
from pathlib import Path

import pytest

CAP = Path(__file__).resolve().parents[1] / "tools" / "capture"
pytestmark = pytest.mark.skipif(not (CAP / "node_modules").exists(), reason="capture deps not installed")


def private(addrs):
    js = ("import { privateIp } from './guard.mjs';"
          f"console.log(JSON.stringify({json.dumps(addrs)}.map((a) => privateIp(a))));")
    r = subprocess.run(["node", "--input-type=module", "-e", js], cwd=CAP, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.parametrize("addr", ["::ffff:7f00:1", "::ffff:127.0.0.1", "::ffff:a9fe:a9fe", "::7f00:1", "::127.0.0.1",
                                  "64:ff9b::7f00:1", "64:ff9b::a9fe:a9fe", "2002:7f00:1::1", "2002:a9fe:a9fe::",
                                  "fec0::1", "fc00::1", "fd12:3456::1", "fe80::1", "ff02::1", "::1", "::",
                                  "0:0:0:0:0:ffff:7f00:1", "::FFFF:7F00:0001", "100::1"])
def test_private_ipv6_forms_are_private(addr):
    assert private([addr]) == [True], addr


@pytest.mark.parametrize("addr", ["2606:4700:4700::1111", "2a00:1450:4001:82b::200e", "::ffff:5db8:d822",
                                  "64:ff9b::5db8:d822", "93.184.216.34"])
def test_public_addresses_stay_public(addr):
    assert private([addr]) == [False], addr


def test_capture_contexts_block_websockets_and_service_workers():
    g = (CAP / "guard.mjs").read_text()
    assert "routeWebSocket" in g
    for script in ("capture.mjs", "check_page.mjs"):
        assert "serviceWorkers: \"block\"" in (CAP / script).read_text(), script


import http.server
import threading


class _Secret(http.server.BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):
        _Secret.hits.append(self.path + " " + self.headers.get("Upgrade", ""))
        body = b"INTERNAL-SECRET-TOKEN-42"
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def test_a_captured_page_cannot_reach_an_internal_service(tmp_path):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Secret)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        page = tmp_path / "p.html"
        page.write_text(f"""<!doctype html><html><head><title>x</title></head><body><h1>Hello</h1><p id="o">none</p><script>
fetch('http://[::ffff:127.0.0.1]:{port}/mapped').then(r => r.text()).then(t => document.getElementById('o').textContent = 'mapped: ' + t).catch(() => {{}});
try {{ new WebSocket('ws://127.0.0.1:{port}/ws'); }} catch (e) {{}}
</script></body></html>""")
        for script, extra in (("capture.mjs", ["fx", page.as_uri(), "--bps", "mobile", "--out", str(tmp_path / "c")]),
                              ("check_page.mjs", [page.as_uri(), "--out", str(tmp_path / "k")])):
            _Secret.hits.clear()
            env = {**__import__("os").environ, "PC_RENDER": str(CAP.parents[1] / "sandbox" / "render.mjs")}
            r = subprocess.run(["node", script, *extra, "--wait", "1500", "--block-private"], cwd=CAP, capture_output=True,
                               text=True, timeout=180, env=env)
            assert r.returncode == 0, (script, r.stderr[-400:])
            dumped = "".join(p.read_text(errors="ignore") for p in tmp_path.rglob("*.json"))
            assert "INTERNAL-SECRET" not in dumped, script
            assert not _Secret.hits, (script, _Secret.hits)
    finally:
        srv.shutdown()
