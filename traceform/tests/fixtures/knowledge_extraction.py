"""
# §3.2 Test fixtures — canonical KnowledgeExtraction objects for unit tests.
# All unit tests mock the Anthropic client and use these fixed fixtures instead.
# This ensures tests never call the real LLM API by default.
"""

from schemas.knowledge import Entities, Fact, KnowledgeExtraction, Relationship

# A minimal valid KnowledgeExtraction for basic generator/reviewer tests
APPLE_REVENUE_EXTRACTION = KnowledgeExtraction(
    summary="Apple Inc. reported Q3 2024 revenue of $85.8 billion, driven by strong iPhone sales.",
    entities=Entities(
        organizations=["Apple Inc."],
        people=["Tim Cook"],
        locations=["Cupertino, California"],
        products=["iPhone", "Mac", "iPad"],
    ),
    facts=[
        Fact(
            claim="Apple reported Q3 2024 revenue of $85.8 billion.",
            source_span="Apple reported Q3 2024 revenue of $85.8 billion",
            start_char=0,
            end_char=48,
            confidence=0.95,
        ),
        Fact(
            claim="iPhone was the primary revenue driver.",
            source_span="driven by strong iPhone sales",
            start_char=50,
            end_char=79,
            confidence=0.88,
        ),
        Fact(
            claim="Tim Cook is the CEO of Apple.",
            source_span="CEO Tim Cook",
            start_char=80,
            end_char=92,
            confidence=0.99,
        ),
    ],
    relationships=[
        Relationship(source="Apple Inc.", relation="CEO", target="Tim Cook"),
        Relationship(source="Apple Inc.", relation="headquarters", target="Cupertino, California"),
    ],
    domain="technology",
    source_tone="journalistic",
    sensitivity="public",
    sensitivity_source="classifier",
    sensitivity_confidence=0.50,
)

# Source text that matches the extraction above (for offset validation tests)
APPLE_REVENUE_SOURCE_TEXT = (
    "Apple reported Q3 2024 revenue of $85.8 billion, "
    "driven by strong iPhone sales. "
    "CEO Tim Cook commented on the strong performance."
)

# A minimal extraction with a single fact — for isolation tests
MINIMAL_EXTRACTION = KnowledgeExtraction(
    summary="A company launched a new product.",
    entities=Entities(organizations=["Acme Corp"], people=[], locations=[], products=["Widget X"]),
    facts=[
        Fact(
            claim="Acme Corp launched Widget X.",
            source_span="Acme Corp launched Widget X",
            start_char=0,
            end_char=len("Acme Corp launched Widget X"),
            confidence=0.90,
        ),
    ],
    relationships=[],
    domain="general",
    source_tone="formal",
    sensitivity="public",
    sensitivity_source="classifier",
    sensitivity_confidence=0.50,
)

# Source text matching MINIMAL_EXTRACTION
MINIMAL_SOURCE_TEXT = "Acme Corp launched Widget X in the third quarter."
