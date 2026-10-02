"""All tunables in one place. Model IDs and prices only ever live here (overridable via env)."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TF_BASE = os.environ.get("TF_BASE", "https://api.tokenfactory.nebius.com/v1/")
SANDBOX_BASE = os.environ.get("SANDBOX_BASE", "https://api.tokenfactory.nebius.com/sandboxes/v1")
RUNTIME_IMAGE = os.environ.get("RUNTIME_IMAGE", "tag:pixel-check-runtime:v7")

SANDBOX_TIMEOUT_S = int(os.environ.get("SANDBOX_TIMEOUT_S", "180"))
SANDBOX_POLL_S = 1.0
SANDBOX_OUTPUT_CAP = 10 * 1024 * 1024  # API max for truncate_output_at

BREAKPOINTS = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1280, 800)}


def api_key() -> str:
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("NEBIUS_API_KEY missing (set it in .env)")
    return key


def project_id() -> str:
    pid = os.environ.get("NEBIUS_AI_PROJECT")
    if not pid:
        raise RuntimeError("NEBIUS_AI_PROJECT missing (set it in .env)")
    return pid

# --- Models (IDs only here; override via env when models are deprecated) ---
MODEL_CODER = os.environ.get("MODEL_CODER", "nvidia/nemotron-3-super-120b-a12b")
MODEL_PLANNER = os.environ.get("MODEL_PLANNER", "nvidia/nemotron-3-super-120b-a12b")
# responsive-intent planner (Oct 1 probe, vercel cards): Ultra thinking-off found all 3 cards (48 ids, $0.004, 2 s);
# Super off found 2 partial cards; Super/Ultra with thinking ran out of 8-12k tokens without an answer
MODEL_INTENT = os.environ.get("MODEL_INTENT", "nvidia/Nemotron-3-Ultra-550b-a55b")
MODEL_EDITOR = os.environ.get("MODEL_EDITOR", "nvidia/nemotron-3-super-120b-a12b")
MODEL_CRITIC = os.environ.get("MODEL_CRITIC", "nvidia/nemotron-3-super-120b-a12b")
MODEL_FAST = os.environ.get("MODEL_FAST", "nvidia/Nemotron-3_5-Lightning")
MODEL_VISION = os.environ.get("MODEL_VISION", "google/gemma-3-27b-it")
CODER_THINKING = os.environ.get("CODER_THINKING", "low")   # coder_settings: low ≥ off on median (n=3/page)
REVISE_TEMPERATURE = float(os.environ.get("REVISE_TEMPERATURE", "0.6"))
CRITIC_THINKING = os.environ.get("CRITIC_THINKING", "low")
CODER_TEMPERATURE = float(os.environ.get("CODER_TEMPERATURE", "1.0"))
REASONING_BUDGET = int(os.environ.get("REASONING_BUDGET", "2048"))
LLM_TIMEOUT_S = float(os.environ.get("LLM_TIMEOUT_S", "180"))

# --- Spend (no billing alert exists in the console; this is the only guard) ---
SPEND_CAP_USD = float(os.environ.get("SPEND_CAP_USD", "40"))   # of $50 credit; leaves headroom
RUN_BUDGET_USD = float(os.environ.get("RUN_BUDGET_USD", "0.75"))
FALLBACK_PRICE = (1.0e-6, 3.0e-6)  # USD/token if a model is missing from the catalogue: assume expensive
LEDGER_PATH = Path(os.environ.get("LEDGER_PATH", Path(__file__).resolve().parents[1] / "var" / "spend.jsonl"))

# --- Loop ---
# Step D ablation (Oct 2): Ultra drafts and editing rounds added 0 points at 7–10× the cost → opt-in
INITIAL_SAMPLES = int(os.environ.get("INITIAL_SAMPLES", "0"))
BRANCHES = int(os.environ.get("BRANCHES", "3"))
MAX_ROUNDS = int(os.environ.get("MAX_ROUNDS", "0"))
STOP_MATCH = float(os.environ.get("STOP_MATCH", "92"))
