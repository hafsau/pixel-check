"""Pixel-Check platform gates G1-G3 (no Sandbox access needed).

Usage:
  pip install openai python-dotenv
  python gates_g1_g3.py                      # G1 + G2
  python gates_g1_g3.py --image design.png   # + G3 vision test
Reads NEBIUS_API_KEY from .env (never hard-code it).
Paste the printed summary into docs/PLATFORM.md and docs/FEEDBACK.md.
"""
import argparse, base64, json, os, sys, time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
KEY = os.environ.get("NEBIUS_API_KEY")
if not KEY:
    sys.exit("NEBIUS_API_KEY missing from .env")
client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/", api_key=KEY)

SCHEMA = {
    "type": "object",
    "properties": {
        "components": {"type": "array", "items": {"type": "string"}},
        "layout": {"type": "string", "enum": ["stack", "grid", "sidebar"]},
    },
    "required": ["components", "layout"],
    "additionalProperties": False,
}
PROMPT = ("A pricing page has a header, three plan cards and a footer. "
          "Return JSON matching this schema exactly: " + json.dumps(SCHEMA))


def g1():
    ids = sorted(m.id for m in client.models.list().data)
    print(f"\n== G1: {len(ids)} models ==")
    for i in ids:
        tag = " <-- NVIDIA" if "nvidia" in i.lower() or "nemotron" in i.lower() else ""
        tag += " <-- VISION?" if any(k in i.lower() for k in ("vl", "vision", "omni", "gemma-3", "gemma-4")) else ""
        print(" ", i, tag)
    return ids


def pick(ids, *words):
    for i in ids:
        if all(w in i.lower() for w in words):
            return i
    return None


def call(model, mode):
    kwargs = {"chat_template_kwargs": {"enable_thinking": mode != "off"}}
    if mode == "low":
        kwargs["chat_template_kwargs"]["low_effort"] = True
    if mode == "on":
        kwargs["reasoning_budget"] = 2048
    t = time.time()
    r = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": PROMPT}],
        response_format={"type": "json_schema", "json_schema": {"name": "plan", "schema": SCHEMA}},
        max_tokens=4000, temperature=1.0, top_p=0.95, extra_body=kwargs)
    dt = time.time() - t
    msg = r.choices[0].message
    content = msg.content or ""
    reasoning = getattr(msg, "reasoning_content", None) or ""
    try:
        json.loads(content); ok = "valid JSON in content"
    except Exception:
        ok = "INVALID/empty content" + (" (check reasoning_content)" if reasoning else "")
    u = r.usage
    print(f"  mode={mode:4} {dt:5.1f}s in={u.prompt_tokens} out={u.completion_tokens} -> {ok}")
    return ok.startswith("valid")


def g2(model, n=10):
    print(f"\n== G2: {model} (x{n} per mode) ==")
    for mode in ("off", "low", "on"):
        wins = sum(call(model, mode) for _ in range(n if mode == "off" else 3))
        total = n if mode == "off" else 3
        print(f"  -> {mode}: {wins}/{total} valid")


def g3(model, path):
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    t = time.time()
    r = client.chat.completions.create(model=model, max_tokens=2000, messages=[{"role": "user", "content": [
        {"type": "text", "text": "List every text string visible in this UI with its approximate box (x,y,w,h in px). JSON list."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
    print(f"\n== G3: {model} {time.time()-t:.1f}s ==\n{r.choices[0].message.content}")
    print("  -> Compare against the real text in the design; pass if >= 90% correct.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--image"); ap.add_argument("--vlm"); ap.add_argument("--super")
    a = ap.parse_args()
    ids = g1()
    sup = a.super or pick(ids, "nemotron", "super")
    if not sup:
        sys.exit("No Nemotron Super ID found; pass --super <id> from the G1 list")
    g2(sup)
    if a.image:
        vlm = a.vlm or pick(ids, "nemotron", "vl") or pick(ids, "vl")
        if not vlm:
            sys.exit("No vision model auto-detected; pass --vlm <id> from the G1 list")
        g3(vlm, a.image)
