"""
# §3.1.1 Tests — Sensitivity Classifier unit tests.
# No LLM calls. Pure heuristic logic tested against keyword fixtures.
"""

import pytest

from agents.analyst.classifier import SensitivityClassifier
from schemas.enums import SensitivityLevel
from tests.fixtures.adversarial_sources import (
    CLEAN_SOURCE,
    CONFIDENTIAL_SOURCE,
    INTERNAL_SOURCE,
)


@pytest.fixture
def classifier():
    return SensitivityClassifier()


class TestSensitivityClassifier:

    def test_confidential_header_detected(self, classifier):
        label, confidence = classifier.classify(CONFIDENTIAL_SOURCE)
        assert label == SensitivityLevel.CONFIDENTIAL
        assert confidence >= 0.80

    def test_internal_header_detected(self, classifier):
        label, confidence = classifier.classify(INTERNAL_SOURCE)
        # INTERNAL USE ONLY should map to at minimum INTERNAL sensitivity
        assert label in (SensitivityLevel.INTERNAL, SensitivityLevel.CONFIDENTIAL)
        assert confidence >= 0.60

    def test_clean_source_returns_public(self, classifier):
        label, confidence = classifier.classify(CLEAN_SOURCE)
        assert label == SensitivityLevel.PUBLIC

    def test_inline_confidential_keyword(self, classifier):
        text = "This document is CONFIDENTIAL and contains trade secrets."
        label, confidence = classifier.classify(text)
        assert label == SensitivityLevel.CONFIDENTIAL

    def test_restricted_keyword(self, classifier):
        text = "RESTRICTED — For authorised personnel only."
        label, confidence = classifier.classify(text)
        assert label == SensitivityLevel.CONFIDENTIAL  # restricted maps to confidential

    def test_internal_use_only_phrase(self, classifier):
        text = "FOR INTERNAL USE ONLY\n\nStaff memo regarding upcoming restructure."
        label, confidence = classifier.classify(text)
        assert label in (SensitivityLevel.INTERNAL, SensitivityLevel.CONFIDENTIAL)
        assert confidence >= 0.60

    def test_header_position_boosts_confidence(self, classifier):
        # Marker at start of doc should yield higher confidence than marker buried deep
        header_text = "CONFIDENTIAL\n\nSome content here."
        buried_text = "Some content here. " * 100 + "CONFIDENTIAL"
        _, conf_header = classifier.classify(header_text)
        _, conf_buried = classifier.classify(buried_text)
        assert conf_header >= conf_buried

    def test_empty_text_returns_public(self, classifier):
        label, confidence = classifier.classify("")
        assert label == SensitivityLevel.PUBLIC

    def test_return_types(self, classifier):
        label, confidence = classifier.classify("Test text.")
        assert isinstance(label, SensitivityLevel)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_custom_config_path(self, tmp_path):
        """Classifier should work with a custom YAML config."""
        import yaml
        config = {
            "high_confidence_markers": ["SUPER_SECRET"],
            "internal_markers": [],
            "structure_patterns": [],
            "label_map": {},
        }
        config_file = tmp_path / "keywords.yaml"
        config_file.write_text(yaml.dump(config))

        custom_classifier = SensitivityClassifier(config_path=config_file)
        label, confidence = custom_classifier.classify("SUPER_SECRET — project files.")
        assert label == SensitivityLevel.CONFIDENTIAL
