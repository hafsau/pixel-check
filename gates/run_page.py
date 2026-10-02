"""Run the full loop on one dev page. Usage: .venv/bin/python -m gates.run_page <page> [--no-visual] [--rounds N]"""
import argparse, json, pathlib
from orchestrator import config
from orchestrator.loop import LoopConfig, run_loop
from orchestrator.perceive import perceive
from orchestrator.tf_client import TFClient

ap = argparse.ArgumentParser(); ap.add_argument("page"); ap.add_argument("--visual", action="store_true", help="enable Gemma visual notes (off by default)")
ap.add_argument("--rounds", type=int, default=config.MAX_ROUNDS); ap.add_argument("--tag", default="")
ap.add_argument("--no-scaffold", action="store_true"); ap.add_argument("--samples", type=int, default=config.INITIAL_SAMPLES)
a = ap.parse_args()
tg = {bp: pathlib.Path(f"benchmarks-dev/{a.page}/{bp}.png").read_bytes() for bp in config.BREAKPOINTS}
tt = {bp: json.loads(pathlib.Path(f"benchmarks-dev/{a.page}/{bp}.text.json").read_text()) for bp in config.BREAKPOINTS}
sp = pathlib.Path(f"out/specs/{a.page}.json")
spec = json.loads(sp.read_text()) if sp.exists() else perceive(TFClient(run_id="perceive"), tg)
res = run_loop(tg, spec, tt, run_id=f"{a.page}{a.tag}-" + __import__("time").strftime("%H%M%S"),
               cfg=LoopConfig(max_rounds=a.rounds, visual_notes=a.visual, scaffold=not a.no_scaffold,
                              initial_samples=a.samples))
print(json.dumps(res, indent=1))
