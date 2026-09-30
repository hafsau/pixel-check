"""Token Factory inference client: prices from the API, persistent spend ledger, hard cap, trace.

- Prices come from GET /v1/models?verbose=true (per-token USD), cached per process.
- Every call's cost is appended to the ledger (config.LEDGER_PATH) BEFORE returning.
- A call is refused when ledger total ≥ SPEND_CAP_USD, or the run's own spend ≥ its budget.
- Retries: 429 / 5xx / transport errors with backoff. Content and reasoning_content both read.
"""
from __future__ import annotations

import base64
import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from . import config


class SpendCapExceeded(RuntimeError):
    pass


_prices: dict[str, tuple[float, float]] = {}
_lock = threading.Lock()


def prices() -> dict[str, tuple[float, float]]:
    """{model_id: (usd_per_input_token, usd_per_output_token)} from the live catalogue."""
    if not _prices:
        r = httpx.get(f"{config.TF_BASE}models?verbose=true", headers={"Authorization": f"Bearer {config.api_key()}"}, timeout=30)
        r.raise_for_status()
        for m in r.json()["data"]:
            p = m.get("pricing") or {}
            _prices[m["id"]] = (float(p.get("prompt", 0)), float(p.get("completion", 0)))
    return _prices


class Ledger:
    """Append-only JSONL of every paid call; total is the sum. Shared across runs and processes."""

    def __init__(self, path: Path = config.LEDGER_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def total(self) -> float:
        if not self.path.exists():
            return 0.0
        return sum(json.loads(l)["usd"] for l in self.path.read_text().splitlines() if l.strip())

    def add(self, entry: dict) -> None:
        with _lock, self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


@dataclass
class Reply:
    content: str
    reasoning: str
    data: dict | list | None      # parsed JSON when json_schema was requested
    model: str
    input_tokens: int
    output_tokens: int
    usd: float
    latency_s: float


class TFClient:
    def __init__(self, run_id: str = "adhoc", run_budget_usd: float | None = None, trace=None):
        self.oa = OpenAI(base_url=config.TF_BASE, api_key=config.api_key(), max_retries=0, timeout=config.LLM_TIMEOUT_S)
        self.ledger = Ledger()
        self.run_id = run_id
        self.run_budget = run_budget_usd if run_budget_usd is not None else config.RUN_BUDGET_USD
        self.run_spend = 0.0
        self.trace = trace   # callable(dict) or None

    def _check_budget(self):
        total = self.ledger.total()
        if total >= config.SPEND_CAP_USD:
            raise SpendCapExceeded(f"global spend ${total:.2f} ≥ cap ${config.SPEND_CAP_USD:.2f}")
        if self.run_spend >= self.run_budget:
            raise SpendCapExceeded(f"run spend ${self.run_spend:.3f} ≥ run budget ${self.run_budget:.2f}")

    def chat(self, model: str, messages: list, *, step: str, schema: dict | None = None, thinking: str = "off",
             max_tokens: int = 4000, temperature: float | None = None, top_p: float | None = None) -> Reply:
        """thinking: 'off' | 'low' | 'on' (Nemotron chat_template_kwargs); ignored for non-Nemotron models."""
        self._check_budget()
        extra = {}
        if "nemotron" in model.lower():
            kw = {"enable_thinking": thinking != "off"}
            if thinking == "low":
                kw["low_effort"] = True
            extra["chat_template_kwargs"] = kw
            if thinking == "on":
                extra["reasoning_budget"] = config.REASONING_BUDGET
        args = dict(model=model, messages=messages, max_tokens=max_tokens, extra_body=extra or None)
        if temperature is not None:
            args["temperature"] = temperature
        if top_p is not None:
            args["top_p"] = top_p
        if schema is not None:
            args["response_format"] = {"type": "json_schema", "json_schema": {"name": step.replace(" ", "_"), "schema": schema}}
        t0 = time.time()
        for attempt in range(6):
            try:
                r = self.oa.chat.completions.create(**args)
                break
            except (RateLimitError, APIConnectionError) as e:
                wait = min(2 ** attempt, 30)
            except APIStatusError as e:
                if e.status_code < 500:
                    raise
                wait = min(2 ** attempt, 30)
            if attempt == 5:
                raise RuntimeError(f"{step}: inference failed after retries")
            time.sleep(wait)
        dt = time.time() - t0
        msg = r.choices[0].message
        content = msg.content or ""
        reasoning = getattr(msg, "reasoning_content", None) or ""
        pin, pout = prices().get(model, (0.0, 0.0))
        if (pin, pout) == (0.0, 0.0):
            pin, pout = config.FALLBACK_PRICE
        u = r.usage
        usd = u.prompt_tokens * pin + u.completion_tokens * pout
        self.run_spend += usd
        entry = {"ts": time.time(), "run": self.run_id, "step": step, "model": model, "thinking": thinking,
                 "in": u.prompt_tokens, "out": u.completion_tokens, "usd": usd, "latency_s": round(dt, 2)}
        self.ledger.add(entry)
        data = None
        if schema is not None:
            data = parse_json(content) if content.strip() else parse_json(reasoning)
            entry["json_ok"] = data is not None
        if self.trace:
            self.trace({"kind": "llm", **entry, "finish_reason": r.choices[0].finish_reason})
        return Reply(content, reasoning, data, model, u.prompt_tokens, u.completion_tokens, usd, dt)


def parse_json(text: str):
    """Parse a JSON object/array from model output (tolerates ``` fences and leading prose)."""
    if not text:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    m = re.search(r"(\{.*\}|\[.*\])", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def image_part(png: bytes) -> dict:
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}}
