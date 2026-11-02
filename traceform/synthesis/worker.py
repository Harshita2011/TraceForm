from uuid import UUID
from db.models import Generation, SynthesisAnalysis
from schemas.enums import GenerationStatus
from orchestrator.runtime import current_run, fence
from synthesis.context import load_context
from synthesis.extraction import extract_bundle


async def execute(task, generation_id):
    context = current_run.get(); factory = context.session_factory
    async with factory() as db:
        generation = await db.get(Generation, UUID(generation_id))
        source = await load_context(db, generation)
    from agents.llm import create_llm_client, get_default_model
    from orchestrator.checkpoints import save_extraction
    model = get_default_model()
    extraction, _ = await extract_bundle(source, model, create_llm_client())
    ke_id = await save_extraction(source, extraction, model, factory)
    async with factory() as db:
        await fence(db)
        analysis = await db.get(SynthesisAnalysis, UUID(generation_id))
        analysis.extraction_id, analysis.conflicts = UUID(ke_id), extraction.conflicts
        generation = await db.get(Generation, UUID(generation_id))
        generation.status = GenerationStatus.COMPLETED
        await db.commit()
