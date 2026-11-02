"""
# §3.3 Executive Summary Generator — instantiates GenericGeneratorAgent with executive_summary YAML config.
"""

import anthropic

from agents.generators.base import GenericGeneratorAgent


class ExecutiveSummaryGenerator(GenericGeneratorAgent):
    """§3.3 — Executive Summary generator. Config: config/output_types/executive_summary.yaml"""

    def __init__(self, client: anthropic.AsyncAnthropic, model: str | None = None):
        kwargs = {"output_type_key": "executive_summary", "client": client}
        if model:
            kwargs["model"] = model
        super().__init__(**kwargs)
