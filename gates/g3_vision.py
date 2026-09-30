"""G3: can the vision model read a design? Text recall/precision vs capture ground truth.

Usage: .venv/bin/python -m gates.g3_vision --vlm <model-id> [--pages a,b] [--bps desktop,mobile]
Ground truth = benchmarks-dev/<page>/<bp>.text.json (visible text nodes from the live DOM).
Pass (BUILD_GUIDE G3): >= 90 % of text strings read correctly.
"""
import argparse, base64, difflib, json, re, time
from pathlib import Path

from openai import OpenAI

from orchestrator import config

DEV = Path("benchmarks-dev")
PROMPT = ("You are reading a UI design screenshot. List EVERY piece of visible text exactly as written, "
          "top to bottom, left to right, one entry per separate text element (a button label, a heading, "
          "a paragraph, a nav link). Do not paraphrase or summarise, do not invent text. "
          'Reply with JSON only: {"texts": [{"text": "...", "box": [x, y, w, h]}]} '
          "where box is the approximate pixel box in this {w}x{h} image.")


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def parse(content: str):
    m = re.search(r"\{.*\}", content or "", re.S)
    if not m:
        return None
    try:
        return [norm(t["text"]) for t in json.loads(m.group(0))["texts"] if norm(t.get("text", ""))]
    except Exception:
        return None


def match(gt, got):
    """GT string counts as read if contained in the output blob or fuzzy >= 0.85 to one entry."""
    blob = " ".join(got)
    hits = [g for g in gt if g in blob or max((difflib.SequenceMatcher(None, g, x).ratio() for x in got), default=0) >= 0.85]
    gtblob = " ".join(gt)
    invented = [x for x in got if x not in gtblob and max((difflib.SequenceMatcher(None, x, g).ratio() for g in gt), default=0) < 0.85]
    return hits, invented


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--vlm", required=True)
    ap.add_argument("--pages", default="netflix-signin,calcom-signup,vercel-pricing,lambda,lennysjobs")
    ap.add_argument("--bps", default="desktop,mobile")
    a = ap.parse_args()
    client = OpenAI(base_url=config.TF_BASE, api_key=config.api_key())
    rows, tot_gt, tot_hit, tot_inv, tot_got = [], 0, 0, 0, 0
    for page in a.pages.split(","):
        for bp in a.bps.split(","):
            w, h = config.BREAKPOINTS[bp]
            gt = list(dict.fromkeys(norm(x["text"]) for x in json.loads((DEV / page / f"{bp}.text.json").read_text())))
            b64 = base64.b64encode((DEV / page / f"{bp}.png").read_bytes()).decode()
            t0 = time.time()
            r = client.chat.completions.create(model=a.vlm, max_tokens=3000, temperature=0.0, messages=[{"role": "user", "content": [
                {"type": "text", "text": PROMPT.replace("{w}", str(w)).replace("{h}", str(h))},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
            dt = time.time() - t0
            got = parse(r.choices[0].message.content)
            if got is None:
                print(f"{page:15} {bp:8} UNPARSEABLE ({dt:.1f}s): {(r.choices[0].message.content or '')[:200]!r}")
                tot_gt += len(gt)
                continue
            hits, inv = match(gt, got)
            tot_gt += len(gt); tot_hit += len(hits); tot_inv += len(inv); tot_got += len(got)
            miss = [g for g in gt if g not in hits]
            print(f"{page:15} {bp:8} recall {len(hits)}/{len(gt)} invented {len(inv)}/{len(got)} "
                  f"{dt:4.1f}s in={r.usage.prompt_tokens} out={r.usage.completion_tokens} missed={miss[:4]} invented={inv[:3]}")
    rec = tot_hit / max(tot_gt, 1)
    print(f"\n{a.vlm}: recall {tot_hit}/{tot_gt} = {rec:.1%}, invented {tot_inv}/{tot_got} -> G3 {'PASS' if rec >= 0.9 else 'FAIL'}")
