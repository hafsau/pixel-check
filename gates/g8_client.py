"""G8 (new): inference client — prices, ledger, caps, JSON, vision. Spends < $0.01.

Usage: .venv/bin/python -m gates.g8_client
"""
import os, pathlib, tempfile
from orchestrator import config
from orchestrator import tf_client as tf

tmp = pathlib.Path(tempfile.mkdtemp())
config.LEDGER_PATH = tmp / "spend.jsonl"
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}}, "required": ["ok", "word"], "additionalProperties": False}
ok = True
c = tf.TFClient(run_id="g8")
c.ledger = tf.Ledger(config.LEDGER_PATH)
r = c.chat(config.MODEL_CODER, [{"role": "user", "content": 'Return {"ok": true, "word": "pixel"} as JSON.'}], step="g8 json", schema=SCHEMA, max_tokens=200)
print(f"super json: data={r.data} in={r.input_tokens} out={r.output_tokens} usd={r.usd:.6f} {r.latency_s:.1f}s"); ok &= r.data == {"ok": True, "word": "pixel"}
r2 = c.chat(config.MODEL_FAST, [{"role": "user", "content": 'Return {"ok": true, "word": "fast"} as JSON.'}], step="g8 fast", schema=SCHEMA, max_tokens=200)
print(f"fast json: data={r2.data} usd={r2.usd:.6f} {r2.latency_s:.1f}s"); ok &= bool(r2.data and r2.data.get("ok"))
png = pathlib.Path("out/g5/desktop.png").read_bytes()
r3 = c.chat(config.MODEL_VISION, [{"role": "user", "content": [{"type": "text", "text": "What is the largest heading text? Reply with just the text."}, tf.image_part(png)]}], step="g8 vision", max_tokens=50, temperature=0)
print(f"vision: {r3.content.strip()!r} usd={r3.usd:.6f}"); ok &= "breakpoint" in r3.content.lower()
led = c.ledger.total(); print(f"ledger total ${led:.6f} (3 entries: {len(config.LEDGER_PATH.read_text().splitlines())})"); ok &= abs(led - (r.usd + r2.usd + r3.usd)) < 1e-12
config.SPEND_CAP_USD = led  # cap reached -> next call must be refused before any request
try:
    c.chat(config.MODEL_FAST, [{"role": "user", "content": "hi"}], step="g8 capped", max_tokens=5); print("CAP NOT ENFORCED"); ok = False
except tf.SpendCapExceeded as e:
    print("cap enforced:", e)
config.SPEND_CAP_USD = 100; c.run_budget = c.run_spend
try:
    c.chat(config.MODEL_FAST, [{"role": "user", "content": "hi"}], step="g8 run-capped", max_tokens=5); print("RUN BUDGET NOT ENFORCED"); ok = False
except tf.SpendCapExceeded as e:
    print("run budget enforced:", e)
print("G8", "PASS" if ok else "FAIL")
