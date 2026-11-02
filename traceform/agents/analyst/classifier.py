"""
# §3.1.1 Sensitivity Classifier — heuristic-only, rules-based, no ML model.

STATED LIMITATION (§3.1.1, §10 Risks):
This is a keyword and structure-based classifier. A learned/probabilistic model is explicitly
deferred per §1.4. This classifier provides a SUGGESTION only — it is never authoritative when
an operator has set sensitivity_source="operator". The sensitivity_source field on every Source
record carries this provenance distinction downstream.

The keyword list is configurable via config/sensitivity_keywords.yaml — no code changes needed
to add/remove terms.
"""

import os
import re
from pathlib import Path

import yaml

from schemas.enums import SensitivityLevel

# Default config path; override via SENSITIVITY_KEYWORDS_PATH env var
_DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "config" / "sensitivity_keywords.yaml"


def _load_config(path: Path | None = None) -> dict:
    config_path = path or Path(os.getenv("SENSITIVITY_KEYWORDS_PATH", str(_DEFAULT_CONFIG)))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class SensitivityClassifier:
    """
    §3.1.1 — Heuristic sensitivity classifier.

    Returns a (SensitivityLevel, confidence) suggestion. This must NEVER be auto-applied
    without being distinguishable from operator-set values via sensitivity_source.

    STATED LIMITATION: This is a rules-based heuristic, not a learned model.
    The confidence_score reflects keyword density and match type, not ML confidence.
    See §3.1.1 and §10 Risks for the explicit acknowledgment of this limitation.
    """

    def __init__(self, config_path: Path | None = None):
        self._config = _load_config(config_path)
        self._high_markers: list[str] = [
            m.upper() for m in self._config.get("high_confidence_markers", [])
        ]
        self._internal_markers: list[str] = [
            m.upper() for m in self._config.get("internal_markers", [])
        ]
        self._structure_patterns: list[re.Pattern] = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in self._config.get("structure_patterns", [])
        ]

    def classify(self, text: str) -> tuple[SensitivityLevel, float]:
        """
        Classify the sensitivity of a text document.

        Args:
            text: The extracted text from a source document.

        Returns:
            Tuple of (SensitivityLevel, confidence_score 0.0-1.0).
            confidence_score reflects match strength — operator-set always overrides this.
        """
        upper_text = text.upper()
        # Check high-confidence markers first (confidential/restricted)
        for marker in self._high_markers:
            if marker in upper_text:
                # Higher confidence if found in first 500 chars (likely a header/banner)
                position_boost = 0.1 if marker in upper_text[:500] else 0.0
                return SensitivityLevel.CONFIDENTIAL, min(0.85 + position_boost, 0.95)

        # Check structure patterns (regex)
        for pattern in self._structure_patterns:
            match = pattern.search(text)
            if match:
                matched_text = match.group(0).upper()
                if any(
                    level in matched_text
                    for level in ("CONFIDENTIAL", "RESTRICTED")
                ):
                    return SensitivityLevel.CONFIDENTIAL, 0.80
                if "INTERNAL" in matched_text:
                    return SensitivityLevel.INTERNAL, 0.75

        # Check internal markers
        for marker in self._internal_markers:
            if marker in upper_text:
                position_boost = 0.05 if marker in upper_text[:500] else 0.0
                return SensitivityLevel.INTERNAL, min(0.65 + position_boost, 0.80)

        # Default: public with low confidence (classifier cannot assert absence of sensitivity)
        return SensitivityLevel.PUBLIC, 0.50
