Scaffold a FastAPI backend repo called "traceform" with this structure:

traceform/
  api/            # FastAPI routes (§3.11)
  orchestrator/   # job enqueue logic (stub for now, real Celery in Phase 2)
  agents/
    analyst/
    generators/
    reviewers/
  config/         # versioned YAML per output type (§5)
  db/             # SQLAlchemy models + Alembic migrations
  storage/        # object storage abstraction (local disk for now, S3-compatible later)
  eval/           # evaluation harness (Phase 5)
  tests/
  .env.example
  docker-compose.yml
  pyproject.toml

Requirements:
1. Use FastAPI + Pydantic v2 + SQLAlchemy 2.0 (async) + PostgreSQL + Alembic.
2. Define Pydantic schemas EXACTLY matching the PRD's Knowledge Extraction JSON shape (§3.2):
   - KnowledgeExtraction: summary, entities{organizations, people, locations, products},
     facts[{claim, source_span, start_char, end_char, confidence}], relationships[{source, relation, target}],
     domain, source_tone, sensitivity, sensitivity_source (operator|classifier), sensitivity_confidence.
3. Define the Data Model from §5 as SQLAlchemy models:
   - Source(id, raw_content_ref, extracted_text, sensitivity, sensitivity_source, sensitivity_confidence, created_at)
   - KnowledgeExtraction(id, source_id FK, summary, entities JSON, facts JSON, relationships JSON, domain, source_tone)
   - Generation(id, source_id FK, output_types JSON, params JSON, prompt_version, reviewer_version, model_version,
     status, budget_ceiling, budget_used, created_at)
   - Artifact(id, generation_id FK, output_type, content, rendered_file_ref, review_results JSON,
     review_status ENUM(passed, failed, budget_exceeded), facts_used JSON, cost JSON, feedback, retry_count)
   - EvaluationRun(id, dataset_version, dataset_size, fact_accuracy, style_adherence_rate, avg_latency, avg_cost, created_at)
   - ComplianceOverride(id, artifact_id FK, operator_id, reason, created_at)
4. Define the Generator/Reviewer interface from §5 as Python abstract base classes:
   generate(context: KnowledgeExtraction, params: GenerationParams) -> Artifact
   review(artifact: Artifact, context: KnowledgeExtraction) -> ReviewResult
   These must be the ONLY way agents receive source-derived content — never raw string interpolation.
5. Create versioned YAML config schema for output types (§5): output_type, prompt_template_version,
   output_json_schema, renderer. Write one example YAML for "linkedin_post".
6. Write .env.example with: DATABASE_URL, REDIS_URL, ANTHROPIC_API_KEY, LLM_CALL_BUDGET_TOKENS,
   LLM_CALL_BUDGET_CALLS, OBJECT_STORAGE_PATH, API_KEYS (comma-separated for now).
7. docker-compose.yml with services: api, postgres, redis (worker service added in Phase 2).
8. Alembic migration for all tables above.
9. Basic pytest setup with a conftest.py using an async test DB.

Do not implement any agent logic yet — this phase is schema and scaffolding only. Every model/schema
should have a docstring citing the PRD section it implements (e.g. "# §3.2 Knowledge Extraction Layer").