"""Step D decision (Oct 2): the loop's editing rounds and Ultra drafts added 0 points at 7–10× the cost
(tools/ablation.py). Defaults = compiler + verified Nemotron plan seeds only; rounds/drafts stay opt-in."""
from orchestrator import config
from orchestrator.loop import LoopConfig


def test_defaults_are_compiler_plus_plan():
    cfg = LoopConfig()
    assert cfg.scaffold and cfg.fluid and cfg.intents
    assert cfg.max_rounds == 0, "editing rounds are opt-in (0 points in the ablation, $0.25–0.39/run)"
    assert cfg.initial_samples == 0, "Ultra drafts are opt-in (pre-compiler approach)"


def test_default_run_budget_covers_one_run():
    assert config.RUN_BUDGET_USD >= 0.15


def test_rounds_still_configurable():
    assert LoopConfig(max_rounds=2, initial_samples=1).max_rounds == 2
