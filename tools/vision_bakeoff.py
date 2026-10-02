"""Vision-model comparison for perception (strings + roles + layout notes; boxes always come from measurement).

    PYTHONPATH=.:sandbox .venv/bin/python tools/vision_bakeoff.py [--models a,b,...] [--pages p1,p2]

Per model and frame (Linux re-captures, benchmarks-dev/<page>-lx): read_frame(model) → merge with the SAME
measurement → spec. Reports per model: string recall of the vision output vs the DOM oracle (visible texts), merged
text recall, end-to-end match (fluid compiler, local render vs target), parse failures, $ and seconds.
Results: out/bakeoff/<model>/<page>/ and out/bakeoff/summary.json. Gemma's stored reading (spec raw_vlm) is reused.
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, "sandbox")
from orchestrator import config  # noqa: E402
from orchestrator.fluid import compile_fluid  # noqa: E402
from orchestrator.measure import measure  # noqa: E402
from orchestrator.perceive import merge, ocr_fallback, read_frame  # noqa: E402
from orchestrator.tf_client import TFClient  # noqa: E402
from tools.intent_eval import evaluate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BPS = ("mobile", "tablet", "desktop")
norm = lambda s: re.sub(r"\s+", " ", s or "").strip().lower()
DEFAULT = ["google/gemma-3-27b-it", "zai-org/GLM-5.3-Flash", "deepseek-ai/DeepSeek-V4.1-Flash",
           "moonshotai/Kimi-K2.6", "openbmb/MiniCPM-V-4_5"]


def recall(strings: list[str], oracle: list[dict]) -> tuple[int, int]:
    """Oracle texts found in the model's strings (a model string may hold several oracle lines)."""
    blob = [norm(s) for s in strings]
    joined = " ".join(blob)
    hit = sum(1 for o in oracle if norm(o["text"]) and (norm(o["text"]) in joined or any(
        SequenceMatcher(None, norm(o["text"]), b).ratio() >= 0.85 for b in blob)))
    return hit, len(oracle)


def run(models, pages):
    client = TFClient(run_id="vision-bakeoff", run_budget_usd=2.5)
    meas = {(p, bp): measure((ROOT / "benchmarks-dev" / f"{p}-lx" / f"{bp}.png").read_bytes()) for p in pages for bp in BPS}
    oracle = {p: json.loads((ROOT / "out" / "specs" / f"{p}-lx.oracle.json").read_text()) for p in pages}
    summary = {}
    for model in models:
        tag = model.split("/")[-1]
        spend0 = client.run_spend
        t0 = time.time()

        def read(key):
            p, bp = key
            if model == config.MODEL_VISION:
                stored = json.loads((ROOT / "out" / "specs" / f"{p}-lx.json").read_text())["raw_vlm"].get(bp)
                if stored:
                    return key, stored, None
            try:
                return key, read_frame(client, bp, (ROOT / "benchmarks-dev" / f"{p}-lx" / f"{bp}.png").read_bytes(), model=model), None
            except Exception as e:   # noqa: BLE001 — a failing model is a result, not a crash
                return key, None, f"{type(e).__name__}: {str(e)[:160]}"

        with ThreadPoolExecutor(6) as ex:
            reads = list(ex.map(read, [(p, bp) for p in pages for bp in BPS]))
        res = {"model": model, "failures": [], "pages": {}}
        vr, mr = [0, 0], [0, 0]
        for (p, bp), vlm, err in reads:
            if err or vlm is None:
                res["failures"].append(f"{p}/{bp}: {err}")
            o = oracle[p]["breakpoints"][bp]["texts"]
            h, n = recall([t.get("text", "") for t in (vlm or {}).get("texts", [])], o)
            vr[0] += h; vr[1] += n
            res["pages"].setdefault(p, {"frames": {}})["frames"][bp] = vlm or ocr_fallback(meas[(p, bp)])
        for p in pages:
            spec = {"breakpoints": {bp: merge(res["pages"][p]["frames"][bp], meas[(p, bp)]) for bp in BPS}}
            for bp in BPS:
                h, n = recall([t["text"] for t in spec["breakpoints"][bp]["texts"] if t.get("box") and not t.get("approx")],
                              oracle[p]["breakpoints"][bp]["texts"])
                mr[0] += h; mr[1] += n
            out = ROOT / "out" / "bakeoff" / tag / p
            out.mkdir(parents=True, exist_ok=True)
            (out / "spec.json").write_text(json.dumps(spec, indent=1))
            r = evaluate(f"{p}-lx", compile_fluid(spec), out)
            res["pages"][p] = {"match": round(r["match"], 1), "per": {k: round(v, 1) for k, v in r["per"].items()}}
        res.update(vision_recall=f"{vr[0]}/{vr[1]}", merged_recall=f"{mr[0]}/{mr[1]}",
                   usd=round(client.run_spend - spend0, 4), seconds=round(time.time() - t0, 1),
                   mean_match=round(sum(v["match"] for v in res["pages"].values()) / len(pages), 1))
        summary[model] = res
        print(f"{tag:22} vision {res['vision_recall']:>7}  merged {res['merged_recall']:>7}  mean {res['mean_match']:5.1f}  "
              + "  ".join(f"{p.split('-')[0]} {v['match']:5.1f}" for p, v in res["pages"].items())
              + f"  ${res['usd']:.3f} {res['seconds']}s  fail {len(res['failures'])}", flush=True)
        for f in res["failures"][:3]:
            print("    ", f)
    (ROOT / "out" / "bakeoff").mkdir(parents=True, exist_ok=True)
    (ROOT / "out" / "bakeoff" / "summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    arg = lambda k, d: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(k + "=")), d)
    models = arg("--models", ",".join(DEFAULT)).split(",")
    pages = arg("--pages", "netflix-signin,calcom-signup,vercel-pricing,lambda").split(",")
    run(models, pages)
