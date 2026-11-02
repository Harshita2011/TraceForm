"""Reuse extraction only when source, sensitivity, model and analyst contract still match."""
import hashlib
import json
from db.models import DurableJob, KnowledgeExtractionModel, ProviderConfiguration
from orchestrator.runtime import current_run, fence
from schemas.knowledge import KnowledgeExtraction


def extraction_fingerprint(source, model, provider):
    from agents.analyst.prompt import build_analyst_prompt
    payload = [source.extracted_text, str(source.sensitivity), str(source.sensitivity_source),
               source.sensitivity_confidence, model, provider, build_analyst_prompt(source.extracted_text).system,
               KnowledgeExtraction.model_json_schema()]
    payload.append(getattr(source, 'context_version', None))
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


async def load_extraction(source, model, factory):
    context = current_run.get()
    if not context:
        return None
    fingerprint = extraction_fingerprint(source, model, context.configuration.provider)
    async with factory() as db:
        job = await db.get(DurableJob, context.generation_id)
        candidates = [job]
        if job.parent_generation_id:
            parent = await db.get(DurableJob, job.parent_generation_id)
            if parent:
                candidates.append(parent)
        for candidate in candidates:
            if candidate.extraction_id and candidate.extraction_fingerprint == fingerprint:
                row = await db.get(KnowledgeExtractionModel, candidate.extraction_id)
                if row and row.source_id == source.id:
                    extraction = KnowledgeExtraction(summary=row.summary, entities=row.entities, facts=row.facts,
                        relationships=row.relationships, domain=row.domain, source_tone=row.source_tone,
                        sensitivity=source.sensitivity, sensitivity_source=source.sensitivity_source,
                        sensitivity_confidence=source.sensitivity_confidence,
                        conflicts=row.conflicts or [], source_documents=row.source_documents or [])
                    valid = all(f.source_span in source.extracted_text for f in extraction.facts)
                    if len(getattr(source, 'documents', {})) > 1:
                        from evidence.validation import anchor
                        valid = all(f.anchors and all(anchor(a, source.evidence_text, source.id, None)['status'] == 'matched'
                                    for a in f.anchors) for f in extraction.facts)
                    if valid:
                        await fence(db)
                        job.extraction_id, job.extraction_fingerprint = row.id, fingerprint
                        job.extraction_reused = True
                        await db.commit()
                        return extraction, str(row.id)
    return None


async def save_extraction(source, extraction, model, factory):
    context = current_run.get()
    async with factory() as db:
        await fence(db)
        row = KnowledgeExtractionModel(source_id=source.id, summary=extraction.summary,
            entities=extraction.entities.model_dump(), facts=[f.model_dump() for f in extraction.facts],
            relationships=[r.model_dump() for r in extraction.relationships], domain=extraction.domain,
            source_tone=extraction.source_tone, conflicts=extraction.conflicts, source_documents=extraction.source_documents)
        db.add(row)
        await db.flush()
        if context:
            job = await db.get(DurableJob, context.generation_id)
            job.extraction_id = row.id
            job.extraction_fingerprint = extraction_fingerprint(source, model, context.configuration.provider)
        await db.commit()
        return str(row.id)
