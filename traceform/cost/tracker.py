"""
# §3.7 Token Usage & Cost Tracking Engine
# Configurable $/token pricing per model with full execution history logging.
# Supports Gemini and Claude models.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "model_pricing.yaml"

_HARDCODED_FALLBACK = {
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.5-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "claude-opus-4-5": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-3-5": {"input": 0.80, "output": 4.00},
    "default": {"input": 1.25, "output": 5.00},
}


def load_pricing_config(config_path: Path | str | None = None) -> dict[str, dict[str, float]]:
    """Load model pricing table from YAML config, falling back to built-in table if not found."""
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict) and "models" in data:
                    return data["models"]
        except Exception as exc:
            logger.warning("Could not read pricing config at %s: %s. Using default.", path, exc)
    return _HARDCODED_FALLBACK


def tokens_to_cost(usage: dict[str, Any] | None, model: str, pricing_table: dict[str, dict[str, float]] | None = None) -> float:
    """
    Calculate USD cost from input and output token counts using model pricing ($ / 1,000,000 tokens).
    """
    if not usage:
        return 0.0
    if "estimated_cost_usd" in usage and usage["estimated_cost_usd"] is not None:
        return usage["estimated_cost_usd"]
    table = pricing_table or load_pricing_config()
    rates = table.get(model, table.get("default", {"input": 1.25, "output": 5.00}))
    input_cost = (usage.get("input_tokens", 0) * rates["input"]) / 1_000_000
    output_cost = (usage.get("output_tokens", 0) * rates["output"]) / 1_000_000
    return round(input_cost + output_cost, 6)


def compute_analyst_cost_share(
    analyst_usage: dict[str, Any] | None,
    num_output_types: int,
    model: str,
    pricing_table: dict[str, dict[str, float]] | None = None,
) -> float:
    """
    §3.7 — Analyst cost distributed equally across all requested output types.
    Formula: analyst_total_cost / max(num_output_types, 1)
    """
    total_analyst_cost = tokens_to_cost(analyst_usage, model, pricing_table)
    return round(total_analyst_cost / max(num_output_types, 1), 6)


def build_artifact_cost_breakdown(
    analyst_share: float,
    generation_usage: dict[str, Any] | None,
    regeneration_usage: dict[str, Any] | None,
    style_usage: dict[str, Any] | None,
    fact_usage: dict[str, Any] | None,
    compliance_usage: dict[str, Any] | None,
    model: str,
    execution_history: list[dict[str, Any]] | None = None,
    pricing_table: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """
    Construct the complete, structured cost breakdown for an Artifact including execution history.
    """
    gen_cost = tokens_to_cost(generation_usage, model, pricing_table)
    regen_cost = tokens_to_cost(regeneration_usage, model, pricing_table)
    style_cost = tokens_to_cost(style_usage, model, pricing_table)
    fact_cost = tokens_to_cost(fact_usage, model, pricing_table)
    comp_cost = tokens_to_cost(compliance_usage, model, pricing_table)

    total = round(analyst_share + gen_cost + regen_cost + style_cost + fact_cost + comp_cost, 6)

    return {
        "analyst_share": analyst_share,
        "generation": gen_cost,
        "regeneration": regen_cost,
        "style_review": style_cost,
        "fact_review": fact_cost,
        "compliance_review": comp_cost,
        "total": total,
        "execution_history": execution_history or [],
    }
