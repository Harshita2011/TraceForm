"""
# §3.2 Knowledge Extraction Layer — Analyst Agent implementation.
# Supports Google Gemini API (and mock clients) to extract structured KnowledgeExtraction from source text.

VALIDATION POLICY (§3.2):
- LLM output MUST validate against the fixed KnowledgeExtraction Pydantic schema.
- On validation failure: retry ONCE with the validation error fed back to the model.
- On second failure: raise AnalystExtractionError — no silent coercion.

ADVERSARIAL INPUT PROTECTION (§3.1.1):
- Source text is always passed through build_analyst_prompt() which enforces structural separation.
- The Analyst Agent NEVER constructs prompts with raw string interpolation of source content.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import ValidationError

from agents.analyst.prompt import AnalystPrompt, build_analyst_prompt
from agents.llm import call_llm, get_default_model
from db.models import KnowledgeExtractionModel, Source
from schemas.enums import SensitivitySource
from schemas.knowledge import KnowledgeExtraction

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096


class AnalystExtractionError(Exception):
    """Raised when the Analyst Agent cannot produce a valid KnowledgeExtraction after retries."""
    pass


class AnalystAgent:
    """
    §3.2 — Analyst Agent that extracts structured knowledge from a source document.

    Enforces:
    - Adversarial input separation via build_analyst_prompt()
    - Schema validation with exactly one retry on failure
    - Operator sensitivity override: if source.sensitivity_source == OPERATOR, the operator's
      sensitivity value replaces the classifier's output in the returned schema.
    """

    def __init__(self, client: Any = None, model: str | None = None):
        self._client = client
        self._model = model or get_default_model()

    async def extract(
        self,
        source: Source,
    ) -> tuple[KnowledgeExtraction, dict]:
        """
        Extract structured knowledge from a Source record.

        Args:
            source: The Source DB model containing extracted_text and sensitivity metadata.

        Returns:
            Tuple of (KnowledgeExtraction schema object, token_usage dict).

        Raises:
            AnalystExtractionError: If the LLM output fails validation after one retry.
        """
        # §3.1.1 — source text goes through the adversarial-safe prompt builder only
        prompt: AnalystPrompt = build_analyst_prompt(source.extracted_text)

        raw_response, usage = await self._call_llm(prompt, correction_notes=None)

        try:
            extraction = self._parse_and_validate(raw_response, source.extracted_text)
        except (json.JSONDecodeError, ValidationError, ValueError) as first_error:
            logger.warning(
                "Analyst extraction failed validation on first attempt, retrying with error context",
                extra={"source_id": str(source.id), "error": str(first_error)},
            )
            # Retry once: feed the validation error back as correction context
            correction_notes = (
                f"Your previous response failed validation with this error:\n{first_error}\n\n"
                "Please correct your JSON output and ensure it matches the required schema exactly."
            )
            raw_response_retry, usage_retry = await self._call_llm(prompt, correction_notes)
            # Merge token usage
            usage = {
                "input_tokens": usage["input_tokens"] + usage_retry["input_tokens"],
                "output_tokens": usage["output_tokens"] + usage_retry["output_tokens"],
            }
            try:
                extraction = self._parse_and_validate(raw_response_retry, source.extracted_text)
            except (json.JSONDecodeError, ValidationError, ValueError) as second_error:
                raise AnalystExtractionError(
                    f"Analyst Agent failed to produce valid KnowledgeExtraction after retry. "
                    f"First error: {first_error}. Second error: {second_error}."
                ) from second_error

        # §3.1.1 — Operator sensitivity always overrides classifier suggestion
        if source.sensitivity_source == SensitivitySource.OPERATOR:
            extraction = extraction.model_copy(update={
                "sensitivity": source.sensitivity,
                "sensitivity_source": "operator",
                "sensitivity_confidence": source.sensitivity_confidence,
            })

        return extraction, usage

    async def _call_llm(
        self,
        prompt: AnalystPrompt,
        correction_notes: str | None,
    ) -> tuple[str, dict]:
        """
        Make a single LLM API call via Gemini or mock adapter.
        """
        user_content = prompt.messages[0]["content"] if prompt.messages else ""
        if correction_notes:
            user_content = f"{user_content}\n\n[Previous Attempt Error]:\n{correction_notes}"

        raw_text, usage = await call_llm(
            client=self._client,
            model=self._model,
            system_prompt=prompt.system,
            user_content=user_content,
            max_tokens=_MAX_TOKENS,
            json_mode=True,
        )
        return raw_text, usage

    def _parse_and_validate(self, raw_text: str, source_text: str | None = None) -> KnowledgeExtraction:
        """
        Parse JSON and validate against KnowledgeExtraction Pydantic schema.
        Strips markdown fences if the LLM wraps its output in them.
        """
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        data = json.loads(text)
        extraction = KnowledgeExtraction(**data)

        # §3.7 Traceability: verify every fact's [start_char:end_char] is non-empty
        for fact in extraction.facts:
            fact.source_id = fact.source_version = fact.fact_key = None
            fact.anchors = []
            # Only the server assigns anchoring provenance, never the model.
            fact.anchor_resolution = 'exact'
            fact.model_start_char = fact.model_end_char = None
            if fact.end_char <= fact.start_char:
                raise ValueError(
                    f"Fact '{fact.claim[:50]}' has invalid char offsets: "
                    f"start_char={fact.start_char} >= end_char={fact.end_char}"
                )
            if source_text is not None and source_text[fact.start_char:fact.end_char] != fact.source_span:
                quote = fact.source_span
                first = source_text.find(quote) if quote.strip() else -1
                if first < 0 or source_text.find(quote, first + 1) >= 0:
                    raise ValueError('A fact passage is missing or ambiguous and its exact source offsets do not match')
                fact.model_start_char, fact.model_end_char = fact.start_char, fact.end_char
                fact.start_char, fact.end_char = first, first + len(quote)
                fact.anchor_resolution = 'unique_quote'

        return extraction

    @property
    def model(self) -> str:
        return self._model
