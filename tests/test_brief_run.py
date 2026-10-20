"""tools/brief_run.py (Oct 20): write the fix brief for a stored check bundle (no re-capture); its cost is added."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import brief_run as R  # noqa: E402
from test_brief import LOVABLE, FakeClient, by_kind  # noqa: E402
from orchestrator import brief as B  # noqa: E402


def test_rebrief_writes_the_brief_into_check_json_and_adds_its_cost(tmp_path):
    p = tmp_path / "check.json"
    p.write_text(json.dumps({**LOVABLE, "type": "check", "usd": 0.05}))
    fid = by_kind(B.facts(LOVABLE), "font")[0]["id"]
    client = FakeClient({"summary": [], "fix_prompt": [{"text": "Use Lato instead of Roboto.", "facts": [fid]}]})
    client.run_spend = 0.0
    orig = client.chat

    def chat(*a, **k):
        client.run_spend += 0.0005
        return orig(*a, **k)
    client.chat = chat
    out = R.rebrief(tmp_path, client)
    saved = json.loads(p.read_text())
    assert saved["brief"]["source"] == "nemotron" and saved["brief"] == out
    assert saved["usd"] == 0.0505 and saved["report"] == LOVABLE["report"]


def test_rebrief_without_a_client_writes_the_template(tmp_path):
    (tmp_path / "check.json").write_text(json.dumps({**LOVABLE, "type": "check", "usd": None}))
    assert R.rebrief(tmp_path, None)["source"] == "template"
    assert json.loads((tmp_path / "check.json").read_text())["usd"] is None
