"""Private source collections and explicitly budgeted multiple-document analysis."""
from uuid import UUID
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from api.dependencies import DbSession, CurrentOperator
from db.models import (SourceCollection, Source, Generation, DurableJob, JobRequest, SynthesisAnalysis,
                       KnowledgeExtractionModel, _event_time)
from schemas.synthesis import CollectionWrite, AnalyzeSources
from teams.scope import team
from schemas.enums import GenerationStatus
from synthesis.context import selected_sources, save_manifest, metadata, manifest_hash, load_context, document_rows, SourceUnavailable
from revisions.content import digest, payload_hash

router = APIRouter(tags=['source synthesis'])


def collection_data(row):
    return {'id':str(row.id),'name':row.name,'source_ids':row.source_ids,'revision':row.revision,
            'archived':row.deleted_at is not None}


async def owned_collection(db, collection_id, operator):
    row = await db.get(SourceCollection, collection_id)
    if not row or (row.owner != operator and not team()): raise HTTPException(404, 'Collection not found.')
    return row


@router.get('/collections')
async def collections(db: DbSession, operator: CurrentOperator, archived: bool = False):
    rows = (await db.execute(select(SourceCollection).where((True if team() else SourceCollection.owner == operator),
        SourceCollection.deleted_at.is_not(None) if archived else SourceCollection.deleted_at.is_(None))
        .order_by(SourceCollection.updated_at.desc()).limit(200))).scalars().all()
    return [collection_data(row) for row in rows]


@router.get('/collections/{collection_id}')
async def collection(collection_id: UUID, db: DbSession, operator: CurrentOperator):
    row = await owned_collection(db, collection_id, operator)
    from api.routes.sources import source_data
    sources = (await db.execute(select(Source).where(Source.id.in_([UUID(i) for i in row.source_ids])))).scalars().all()
    by_id = {str(s.id): s for s in sources}
    return {**collection_data(row), 'sources':[source_data(by_id[i]) if i in by_id else
        {'id':i, 'filename':'Unavailable source', 'status':'unavailable','sensitivity':'confidential','word_count':0} for i in row.source_ids]}


@router.post('/collections', status_code=201)
async def create_collection(request: CollectionWrite, db: DbSession, operator: CurrentOperator):
    if not request.name.strip(): raise HTTPException(422, 'Enter a collection name.')
    await selected_sources(db, request.source_ids, True)
    row = SourceCollection(owner=operator, name=request.name.strip(), source_ids=[str(i) for i in request.source_ids])
    db.add(row); await db.commit()
    return collection_data(row)


@router.put('/collections/{collection_id}')
async def update_collection(collection_id: UUID, request: CollectionWrite, db: DbSession, operator: CurrentOperator):
    row = await owned_collection(db, collection_id, operator)
    if not request.name.strip(): raise HTTPException(422, 'Enter a collection name.')
    if row.deleted_at: raise HTTPException(409, 'Restore this collection before editing it.')
    await selected_sources(db, request.source_ids, True)
    changed = await db.execute(update(SourceCollection).where(SourceCollection.id == collection_id,
        (True if team() else SourceCollection.owner == operator), SourceCollection.revision == request.expected_revision,
        SourceCollection.deleted_at.is_(None)).values(name=request.name.strip(), source_ids=[str(i) for i in request.source_ids],
        revision=SourceCollection.revision + 1, updated_at=_event_time()))
    if not changed.rowcount: raise HTTPException(409, 'This collection changed. Reload it before saving.')
    await db.commit(); await db.refresh(row)
    return collection_data(row)


@router.post('/collections/{collection_id}/archive')
async def archive_collection(collection_id: UUID, db: DbSession, operator: CurrentOperator):
    row = await owned_collection(db, collection_id, operator)
    await db.execute(update(SourceCollection).where(SourceCollection.id == row.id).values(
        deleted_at=_event_time(), revision=SourceCollection.revision + 1, updated_at=_event_time()))
    await db.commit()
    return {'message':'Collection archived. Its source documents and existing runs are kept.'}


@router.post('/collections/{collection_id}/restore')
async def restore_collection(collection_id: UUID, db: DbSession, operator: CurrentOperator):
    row = await owned_collection(db, collection_id, operator)
    await db.execute(update(SourceCollection).where(SourceCollection.id == row.id).values(
        deleted_at=None, revision=SourceCollection.revision + 1, updated_at=_event_time()))
    await db.commit(); await db.refresh(row)
    return collection_data(row)


@router.post('/source-analyses', status_code=202)
async def analyze(request: AnalyzeSources, db: DbSession, operator: CurrentOperator):
    from teams.scope import workspace
    key = digest(f'analysis:{workspace.get() or "legacy"}:{operator}:{request.request_id}'); ph = payload_hash(request.model_dump())
    previous = await db.get(JobRequest, key)
    if previous:
        if previous.payload_hash != ph: raise HTTPException(409, 'Request key reused with different analysis settings.')
        return {'id':str(previous.generation_id)}
    sources = await selected_sources(db, request.source_ids, True)
    from config.provider import current_configuration
    from agents.availability import provider_health
    from orchestrator.runtime import plan_fingerprint
    configuration, _ = await current_configuration(db)
    health = await provider_health(configuration)
    if not health['available']: raise HTTPException(503, health['message'])
    generation = Generation(kind='source_analysis', source_id=sources[0].id, output_types=[], params={},
        model_version=configuration.model, status=GenerationStatus.QUEUED, budget_type=request.budget_type,
        budget_ceiling=request.budget_ceiling, synthesis={'owner':operator})
    db.add(generation); await db.flush()
    rows = await save_manifest(db, generation.id, sources)
    db.add(SynthesisAnalysis(generation_id=generation.id, owner=operator, manifest_hash=manifest_hash([metadata(r) for r in rows])))
    db.add(DurableJob(generation_id=generation.id, task_kind='source_analysis', configuration_id=configuration.id,
                      plan_fingerprint=plan_fingerprint()))
    db.add(JobRequest(key_hash=key, payload_hash=ph, generation_id=generation.id))
    try: await db.commit()
    except IntegrityError:
        await db.rollback(); previous = await db.get(JobRequest, key)
        if not previous or previous.payload_hash != ph: raise HTTPException(409, 'Analysis submission conflict. Retry with the same request key.')
        return {'id':str(previous.generation_id)}
    return {'id':str(generation.id)}


@router.get('/source-analyses')
async def previous_analyses(db: DbSession, operator: CurrentOperator):
    rows = (await db.execute(select(Generation).join(SynthesisAnalysis, SynthesisAnalysis.generation_id == Generation.id)
        .where((True if team() else SynthesisAnalysis.owner == operator)).order_by(Generation.created_at.desc()).limit(30))).scalars().all()
    return [{'id':str(row.id),'status':row.status.value,'filenames':[doc.filename for doc in await document_rows(db,row.id)],
             'created_at':row.created_at.isoformat()} for row in rows]


@router.get('/source-analyses/{analysis_id}')
async def analysis(analysis_id: UUID, db: DbSession, operator: CurrentOperator):
    row = await db.get(SynthesisAnalysis, analysis_id)
    if not row or (row.owner != operator and not team()): raise HTTPException(404, 'Analysis not found.')
    generation = await db.get(Generation, analysis_id)
    from orchestrator.queue import job_summary
    try:
        source = await load_context(db, generation)
    except SourceUnavailable as exc:
        job = await job_summary(db, analysis_id)
        job['message'] = str(exc)
        return {'id':str(analysis_id),'status':'unavailable','documents':[metadata(r) for r in await document_rows(db,analysis_id)],
                'manifest_hash':row.manifest_hash,'conflicts':[],'facts':[],'unique_facts':0,'job':job}
    extraction = await db.get(KnowledgeExtractionModel, row.extraction_id) if row.extraction_id else None
    return {'id':str(analysis_id), 'status':generation.status.value, 'documents':source.source_documents,
        'manifest_hash':row.manifest_hash, 'conflicts':row.conflicts or [], 'facts':extraction.facts if extraction else [],
        'unique_facts':len(extraction.facts) if extraction else 0, 'job':await job_summary(db, analysis_id)}


@router.post('/source-analyses/{analysis_id}/cancel')
async def cancel_analysis(analysis_id: UUID, db: DbSession, operator: CurrentOperator):
    row = await db.get(SynthesisAnalysis, analysis_id)
    if not row or (row.owner != operator and not team()): raise HTTPException(404, 'Analysis not found.')
    from api.routes.generations import cancel_generation
    return await cancel_generation(analysis_id, db, operator)


async def admitted_analysis(db, request, operator, configuration):
    row = await db.get(SynthesisAnalysis, request.analysis_id)
    if not row or (row.owner != operator and not team()): raise HTTPException(404, 'Analysis not found.')
    generation = await db.get(Generation, row.generation_id)
    job = await db.get(DurableJob, row.generation_id)
    from orchestrator.runtime import plan_fingerprint
    from db.models import ProviderConfiguration
    prior = await db.get(ProviderConfiguration, job.configuration_id)
    if generation.status != GenerationStatus.COMPLETED or not row.extraction_id:
        raise HTTPException(409, 'Wait for source analysis to finish before creating outputs.')
    if job.plan_fingerprint != plan_fingerprint() or (prior.provider,prior.model) != (configuration.provider,configuration.model):
        raise HTTPException(409, 'The analysis model or implementation changed. Analyze the selected documents again.')
    source = await load_context(db, generation)
    if [UUID(doc['id']) for doc in source.source_documents] != request.source_ids:
        raise HTTPException(409, 'The source selection changed. Analyze the current selection again.')
    conflicts = row.conflicts or []
    if set(request.conflict_resolutions) != {c['id'] for c in conflicts}:
        raise HTTPException(422, 'Choose a resolution for every recorded conflict; do not include unknown conflicts.')
    decisions = {key:value.model_dump(mode='json') for key,value in request.conflict_resolutions.items()}
    for conflict in conflicts:
        decision = decisions[conflict['id']]
        allowed = {a['source_id'] for fact in conflict['facts'] for a in fact['anchors']}
        if decision['choice'] == 'prefer' and decision['preferred_source_id'] not in allowed:
            raise HTTPException(422, 'Choose a source that supports one of the disputed accounts.')
        if decision['choice'] != 'prefer' and decision['preferred_source_id'] is not None:
            raise HTTPException(422, 'A preferred source is only valid for the prefer-source resolution.')
    return {'owner':operator,'analysis_id':str(row.generation_id),'manifest_hash':row.manifest_hash,
            'resolutions':decisions,'conflicts':[{**c,'resolution':decisions[c['id']]} for c in conflicts]}
