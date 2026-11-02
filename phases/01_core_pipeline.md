Building on the existing "traceform" repo (Phase 0 scaffold), implement the synchronous core pipeline.

1. SOURCE INGESTION (§3.1)
   - POST /api/v1/sources accepting: plain text, PDF (pdfplumber/PyMuPDF), DOCX (python-docx),
     images (pytesseract OCR fallback), free-form prompt text.
   - Video: accept as attachment only — store the file reference, link it to the Source record,
     do NOT transcribe or extract claims from it. This is explicit V1 scope per §3.1.
   - Validate extraction quality (e.g. minimum extracted character count, OCR confidence threshold)
     before proceeding; on failure return 422 with an actionable error message naming what failed
     and why (not a generic "extraction failed").
   - Enforce input validation from §7: file type/size limits, extracted text length caps (~15k words
     per §1.4's context-window rationale — reject or truncate-with-warning beyond that, operator's choice
     surfaced in the error).
   - Sensitivity tagging: accept an operator-supplied sensitivity value (public|internal|restricted|confidential).
     If absent, run the heuristic classifier (build this now, see #2) and use its suggestion, but always
     record sensitivity_source so downstream code can distinguish "operator" from "classifier" provenance.

2. SENSITIVITY CLASSIFIER (§3.1.1) — rules/heuristic ONLY, not a learned model (explicitly deferred, §1.4)
   - Keyword and structure-based: scan for markers like "CONFIDENTIAL", "INTERNAL USE ONLY", an
     org-internal terminology list (make this list configurable via YAML, not hardcoded), document
     structure hints (e.g. headers, classification banners).
   - Return (sensitivity_label, confidence_score). This must be a pure suggestion — never auto-applied
     without being distinguishable from operator-set values (sensitivity_source field carries this).
   - Explicitly document in code comments that this is a stated limitation, not "solved" — matches
     the PRD's framing in §3.1.1 and Risks (§10).

3. ADVERSARIAL INPUT HANDLING (§3.1.1) — this is the security-critical part, implement carefully:
   - Source content must NEVER be concatenated into the instruction/system portion of any prompt sent
     to an LLM. Use Anthropic API message roles correctly: system prompt = instructions only; source
     text goes in a clearly delimited user-turn data block (e.g. wrapped in <source_content> tags or
     passed as a separate structured field), never merged with instruction text.
   - Build a helper `build_analyst_prompt(source_text: str) -> list[Message]` that enforces this
     separation structurally (not just by convention) — e.g. the function signature should make it
     impossible to call without going through the delimited-block path.
   - Any source-derived text resembling an instruction ("ignore previous instructions", "system:",
     role markers, etc.) must be extractable as a fact/quote ABOUT the source (i.e. the Analyst Agent
     may report "the source contains text attempting prompt injection: '...'" as a fact), but must
     never be executed as an instruction to any agent. Write a test fixture with such adversarial text
     and assert the pipeline treats it as inert data.

4. KNOWLEDGE EXTRACTION LAYER — ANALYST AGENT (§3.2)
   - Implement the Analyst Agent using the Anthropic API (direct SDK per §6).
   - Output MUST validate against the fixed KnowledgeExtraction JSON schema from Phase 0 — use
     Pydantic to validate the LLM's structured output; on schema validation failure, retry once with
     the validation error fed back to the model, then fail loudly (no silent coercion).
   - Facts must carry source_span, start_char, end_char as exact character offsets into extracted_text
     — this is the traceability mechanism the whole product is built on (§1.3, §3.7). Write a test that
     asserts every fact's [start_char:end_char] slice of extracted_text is non-empty and plausible.
   - Persist the result as a KnowledgeExtraction row linked to its Source.

5. TWO GENERATOR AGENTS (pick LinkedIn Post + Executive Summary, per the PRD's representative flow §2)
   - Each generator implements generate(context: KnowledgeExtraction, params: GenerationParams) -> Artifact
     from the Phase 0 interface.
   - Generators receive ONLY the structured KnowledgeExtraction object — never raw source text
     re-inserted into their prompt. Enforce this at the type-signature level.
   - Each generator's prompt template lives in versioned YAML (§5) with prompt_template_version pinned
     into the resulting Artifact/Generation record (§3.5's reproducibility requirement, detailed in Phase 4).
   - No review layer yet (that's Phase 3) — for now, generated artifacts are persisted with
     review_status left null/pending.

6. API ENDPOINTS (subset of §3.11, synchronous only for now)
   - POST /api/v1/sources
   - POST /api/v1/generations  (accepts source_id + output_types + params; runs synchronously inline,
     no Celery yet — that's Phase 2)
   - GET /api/v1/generations/{id}
   - GET /api/v1/generations/{id}/artifacts/{type}
   - GET /api/v1/healthz

7. TESTS
   - Unit tests for the classifier, the prompt-injection delimiter helper, and each generator, against
     fixed KnowledgeExtraction fixtures (don't call the real LLM in unit tests — mock the Anthropic client).
   - One integration test that runs a real small source through ingestion → extraction → both
     generators end-to-end (can hit the real API behind a flag, default to mocked).
   - One adversarial-input fixture test per #3 above.

Do not implement Celery/queueing, review agents, cost tracking, or the eval harness yet — those are
later phases. Keep this synchronous and single-process.