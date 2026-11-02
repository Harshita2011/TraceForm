"""Private drafts and immutable versions. All writes use the same artifact lock."""
import difflib
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from api.dependencies import CurrentOperator, DbSession
from db.models import (Artifact, ArtifactDraft, ArtifactVersion, VersionReview, VersionOperation,
                       Generation, Source, DurableJob, AuditRecord, JobRequest, _event_time)
from schemas.workspace import DraftSave, Snapshot, Restore, VersionTask
from schemas.enums import GenerationStatus, ArtifactReviewStatus
from revisions.content import digest, payload_hash, sections, policy_hash, review_policy
from orchestrator.runtime import aware
from synthesis.context import load_context, copy_manifest
from teams.scope import team

router = APIRouter(prefix='/artifacts', tags=['editing'])


async def context(db, artifact_id, operator, lock=False):
    if lock:
        await db.execute(update(Artifact).where(Artifact.id == artifact_id).values(content=Artifact.content))
    artifact = await db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(404, 'Output not found.')
    generation = await db.get(Generation, artifact.generation_id)
    from api.routes.generations import _check_version_owner
    await _check_version_owner(db, generation.id, operator)
    if generation.status in {GenerationStatus.QUEUED, GenerationStatus.PENDING, GenerationStatus.RUNNING}:
        raise HTTPException(409, 'Wait for this run to finish before editing or exporting it.')
    source = await load_context(db, generation)
    return artifact, generation, source


async def draft_row(db, artifact_id, owner):
    return (await db.execute(select(ArtifactDraft).where(ArtifactDraft.artifact_id == artifact_id,
                                                      ArtifactDraft.owner == owner))).scalar_one_or_none()


def draft_data(row, artifact):
    return {'content': row.content if row else artifact.content or '', 'revision': row.revision if row else 0,
            'base_hash': row.base_hash if row else digest(artifact.content or ''),
            'updated_at': aware(row.updated_at).isoformat() if row else None}


def event(db, artifact_id, owner, event_type, details):
    db.add(AuditRecord(event_type=event_type, operator_id=owner, resource_id=str(artifact_id), metadata_json=details))


async def owned_version(db, artifact_id, version_id, owner):
    row = await db.get(ArtifactVersion, version_id)
    if not row or row.artifact_id != artifact_id or (row.owner != owner and not team()):
        raise HTTPException(404, 'Saved version not found.')
    return row


def version_meta(row):
    return {'id': str(row.id), 'label': row.label, 'origin': row.origin, 'content_hash': row.content_hash,
            'source_hash': row.source_hash, 'parent_id': str(row.parent_id) if row.parent_id else None,
            'created_at': aware(row.created_at).isoformat()}


async def latest_review(db, row, source):
    review = (await db.execute(select(VersionReview).where(VersionReview.version_id == row.id).order_by(
        VersionReview.created_at.desc()).limit(1))).scalar_one_or_none()
    current = bool(review and review.content_hash == row.content_hash and
                   review.source_hash == digest(source.extracted_text or '') and review.policy_hash == review_policy(source))
    return review if current else None


async def version_data(db, row, artifact, generation, source):
    from api.routes.generations import _artifact_to_response
    review = await latest_review(db, row, source)
    display = Artifact(id=artifact.id, generation_id=artifact.generation_id, output_type=artifact.output_type,
        content=row.content, facts_used=review.facts_used if review else [], review_results=review.results if review else [],
        review_status=(ArtifactReviewStatus.PASSED if review.passed else ArtifactReviewStatus.FAILED) if review else ArtifactReviewStatus.PENDING)
    response = _artifact_to_response(display, generation, source).model_dump(mode='json')
    if not review:
        response['assurance_status'] = 'unreviewed'
    return {**version_meta(row), 'content': row.content, 'sections': sections(row.content),
            'review_id': str(review.id) if review else None,
            'artifact': response}


async def store_version(db, artifact, source, owner, content, label, origin, request_id, request_hash, parent_id=None):
    previous = (await db.execute(select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact.id,
        ArtifactVersion.owner == owner, ArtifactVersion.request_id == request_id))).scalar_one_or_none()
    if previous:
        if previous.request_hash != request_hash:
            raise HTTPException(409, 'This request was already used with different content.')
        return previous
    row = ArtifactVersion(artifact_id=artifact.id, owner=owner, content=content, label=label.strip() or 'Saved version',
        origin=origin, content_hash=digest(content), source_hash=digest(source.extracted_text or ''),
        request_id=request_id, request_hash=request_hash, parent_id=parent_id)
    db.add(row)
    await db.flush()
    event(db, artifact.id, owner, 'VERSION_SAVED', {'version_id': str(row.id), 'content_hash': row.content_hash, 'origin': origin})
    return row


@router.get('/{artifact_id}/workspace')
async def workspace(artifact_id: UUID, db: DbSession, operator: CurrentOperator):
    artifact, _, _ = await context(db, artifact_id, operator)
    row = await draft_row(db, artifact_id, operator)
    return {'owner': operator, 'original_hash': digest(artifact.content or ''), 'draft': draft_data(row, artifact)}


async def write_draft(db, artifact, owner, request):
    row = await draft_row(db, artifact.id, owner)
    request_hash = payload_hash(request.model_dump())
    if row and row.last_request_id == str(request.request_id):
        if row.request_hash != request_hash:
            raise HTTPException(409, 'Save request reused with different text.')
        return row
    if (row.revision if row else 0) != request.expected_revision or request.base_hash != digest(artifact.content or ''):
        raise HTTPException(409, {'message': 'A newer draft exists. Keep your copy as a recovery version before loading it.',
                                  'draft': draft_data(row, artifact)})
    if not row:
        row = ArtifactDraft(artifact_id=artifact.id, owner=owner, revision=0)
        db.add(row)
    row.content, row.revision, row.base_hash = request.content, row.revision + 1, request.base_hash
    row.last_request_id, row.request_hash, row.updated_at = str(request.request_id), request_hash, _event_time()
    return row


@router.put('/{artifact_id}/draft')
async def save_draft(artifact_id: UUID, request: DraftSave, db: DbSession, operator: CurrentOperator):
    artifact, _, _ = await context(db, artifact_id, operator, True)
    row = await write_draft(db, artifact, operator, request)
    await db.commit()
    return draft_data(row, artifact)


@router.get('/{artifact_id}/versions')
async def versions(artifact_id: UUID, db: DbSession, operator: CurrentOperator,
                   offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    await context(db, artifact_id, operator)
    where = (ArtifactVersion.artifact_id == artifact_id, True if team() else ArtifactVersion.owner == operator)
    total = (await db.execute(select(func.count(ArtifactVersion.id)).where(*where))).scalar()
    rows = (await db.execute(select(ArtifactVersion).where(*where).order_by(
        ArtifactVersion.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return {'items': [version_meta(row) for row in rows], 'total': total}


@router.post('/{artifact_id}/versions', status_code=201)
async def snapshot(artifact_id: UUID, request: Snapshot, db: DbSession, operator: CurrentOperator):
    artifact, generation, source = await context(db, artifact_id, operator, True)
    # Idempotent response must survive a later draft revision.
    request_hash = payload_hash(request.model_dump())
    previous = (await db.execute(select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact_id,
        ArtifactVersion.owner == operator, ArtifactVersion.request_id == str(request.request_id)))).scalar_one_or_none()
    if previous:
        if previous.request_hash != request_hash:
            raise HTTPException(409, 'Request key reused with different settings.')
        return await version_data(db, previous, artifact, generation, source)
    if request.source == 'original':
        content = artifact.content or ''
    elif request.source == 'draft':
        draft = await draft_row(db, artifact_id, operator)
        if (draft.revision if draft else 0) != request.expected_revision:
            raise HTTPException(409, 'The draft changed. Reload it before saving a version.')
        content = draft.content if draft else artifact.content or ''
    else:
        if request.content is None:
            raise HTTPException(422, 'Imported content is required.')
        content = request.content
    row = await store_version(db, artifact, source, operator, content, request.label, request.source,
                              str(request.request_id), request_hash)
    await db.commit()
    return await version_data(db, row, artifact, generation, source)


@router.get('/{artifact_id}/versions/{version_id}')
async def get_version(artifact_id: UUID, version_id: UUID, db: DbSession, operator: CurrentOperator):
    artifact, generation, source = await context(db, artifact_id, operator)
    row = await owned_version(db, artifact_id, version_id, operator)
    return await version_data(db, row, artifact, generation, source)


@router.post('/{artifact_id}/versions/{version_id}/restore')
async def restore(artifact_id: UUID, version_id: UUID, request: Restore, db: DbSession, operator: CurrentOperator):
    artifact, _, source = await context(db, artifact_id, operator, True)
    version = await owned_version(db, artifact_id, version_id, operator)
    draft = await draft_row(db, artifact_id, operator)
    save = DraftSave(content=version.content, expected_revision=request.expected_revision,
                     base_hash=digest(artifact.content or ''), request_id=request.request_id)
    # Validate first, preserve the previous draft, then update it in this transaction.
    if not (draft and draft.last_request_id == str(request.request_id)):
        if (draft.revision if draft else 0) != request.expected_revision:
            raise HTTPException(409, 'The draft changed. Save a recovery version or load the latest draft.')
        if draft and draft.content != version.content:
            await store_version(db, artifact, source, operator, draft.content, 'Before restore', 'recovery',
                f'backup:{request.request_id}', payload_hash([draft.content, request.expected_revision]))
    row = await write_draft(db, artifact, operator, save)
    event(db, artifact_id, operator, 'VERSION_RESTORED', {'version_id': str(version_id), 'draft_revision': row.revision})
    await db.commit()
    return draft_data(row, artifact)


async def target_content(db, artifact, owner, target, version_id=None):
    if target == 'original':
        return artifact.content or '', None, None
    if target == 'draft':
        row = await draft_row(db, artifact.id, owner)
        return row.content if row else artifact.content or '', row.revision if row else 0, None
    if not version_id:
        raise HTTPException(422, 'Select a saved version.')
    row = await owned_version(db, artifact.id, version_id, owner)
    return row.content, None, row


@router.get('/{artifact_id}/compare')
async def compare(artifact_id: UUID, db: DbSession, operator: CurrentOperator,
                  left: str = 'original', right: str = 'draft'):
    artifact, _, _ = await context(db, artifact_id, operator)
    async def resolve(value):
        if value in {'original', 'draft'}:
            return await target_content(db, artifact, operator, value)
        try:
            return await target_content(db, artifact, operator, 'version', UUID(value))
        except ValueError:
            raise HTTPException(422, 'Invalid comparison target.')
    a, ar, _ = await resolve(left)
    b, br, _ = await resolve(right)
    # Bound diff input and output. Full documents remain available in each view/export.
    if len(a) + len(b) > 250000:
        return {'diff': 'Documents are too large for an inline comparison. Download both versions to compare.',
                'truncated': True, 'left_hash': digest(a), 'right_hash': digest(b)}
    lines = list(difflib.unified_diff(a.splitlines(), b.splitlines(), fromfile=left, tofile=right, lineterm=''))
    return {'diff': '\n'.join(lines[:5000]), 'truncated': len(lines) > 5000,
            'left_hash': digest(a), 'right_hash': digest(b), 'left_revision': ar, 'right_revision': br}


@router.post('/{artifact_id}/versions/{version_id}/tasks', status_code=202)
async def version_task(artifact_id: UUID, version_id: UUID, request: VersionTask, db: DbSession, operator: CurrentOperator):
    artifact, parent, source = await context(db, artifact_id, operator)
    row = await owned_version(db, artifact_id, version_id, operator)
    from api.routes.sources import usable
    if not usable(source):
        raise HTTPException(422, 'Restore a ready source before running AI tasks.')
    if row.source_hash != digest(source.extracted_text or ''):
        raise HTTPException(409, 'The source changed. Save a new version against the current source.')
    if request.operation == 'section' and not any(s['id'] == request.section_id for s in sections(row.content)):
        raise HTTPException(422, 'Choose a section from this saved version.')
    key = digest(f'version:{operator}:{artifact_id}:{request.request_id}')
    ph = payload_hash([str(version_id), request.model_dump()])
    existing = await db.get(JobRequest, key)
    if existing:
        if existing.payload_hash != ph:
            raise HTTPException(409, 'Request key already used with different task settings.')
        return {'job_id': str(existing.generation_id)}
    from config.provider import current_configuration
    from agents.availability import provider_health
    configuration, _ = await current_configuration(db)
    health = await provider_health(configuration)
    if not health['available']:
        raise HTTPException(503, health['message'])
    generation = Generation(kind='version', source_id=source.id, output_types=[artifact.output_type],
        synthesis=parent.synthesis,
        params=parent.params, model_version=configuration.model, status=GenerationStatus.QUEUED,
        budget_type=request.budget_type, budget_ceiling=request.budget_ceiling)
    db.add(generation)
    await db.flush()
    await copy_manifest(db, parent.id, generation.id)
    db.add(DurableJob(generation_id=generation.id, task_kind='version', configuration_id=configuration.id,
        parent_generation_id=parent.id, plan_fingerprint=policy_hash()))
    db.add(VersionOperation(job_id=generation.id, version_id=row.id, owner=operator,
                           operation=request.operation, payload=request.model_dump(mode='json')))
    db.add(JobRequest(key_hash=key, payload_hash=ph, generation_id=generation.id))
    event(db, artifact_id, operator, 'VERSION_TASK_STARTED', {'version_id': str(row.id), 'job_id': str(generation.id), 'operation': request.operation})
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        previous = await db.get(JobRequest, key)
        if not previous or previous.payload_hash != ph:
            raise HTTPException(409, 'Task submission conflict. Retry with the same request key.')
        return {'job_id': str(previous.generation_id)}
    return {'job_id': str(generation.id)}


@router.get('/{artifact_id}/version-tasks')
async def tasks(artifact_id: UUID, db: DbSession, operator: CurrentOperator):
    await context(db, artifact_id, operator)
    rows = (await db.execute(select(VersionOperation).join(ArtifactVersion, ArtifactVersion.id == VersionOperation.version_id).where(
        ArtifactVersion.artifact_id == artifact_id, (True if team() else VersionOperation.owner == operator)).order_by(
        VersionOperation.created_at.desc()).limit(30))).scalars().all()
    from orchestrator.queue import job_summary
    return [{'job_id': str(row.job_id), 'version_id': str(row.version_id), 'operation': row.operation,
             'result_version_id': str(row.result_version_id) if row.result_version_id else None,
             'job': await job_summary(db, row.job_id)} for row in rows]


@router.post('/{artifact_id}/version-tasks/{job_id}/cancel')
async def cancel_task(artifact_id: UUID, job_id: UUID, db: DbSession, operator: CurrentOperator):
    row = await db.get(VersionOperation, job_id)
    if not row or (row.owner != operator and not team()):
        raise HTTPException(404, 'Task not found.')
    await owned_version(db, artifact_id, row.version_id, operator)
    from api.routes.generations import cancel_generation
    return await cancel_generation(job_id, db, operator)


@router.get('/{artifact_id}/export')
async def export_artifact(artifact_id: UUID, db: DbSession, operator: CurrentOperator,
    format: str = Query(pattern=r'^(md|txt|docx|pdf|pptx)$'),
    target: str = Query(default='original', pattern=r'^(original|draft|version)$'), version_id: UUID | None = None,
    expected_hash: str = Query(pattern=r'^[a-f0-9]{64}$'), expected_revision: int | None = Query(default=None, ge=0),
    citations: bool = False, provenance: bool = False):
    artifact, generation, source = await context(db, artifact_id, operator)
    if format == 'pptx' and artifact.output_type != 'presentation':
        raise HTTPException(422, 'PowerPoint export is available for presentation outlines.')
    if source.deleted_at:
        raise HTTPException(409, 'Restore the source in the library before exporting linked content.')
    content, revision, row = await target_content(db, artifact, operator, target, version_id)
    if digest(content) != expected_hash or target == 'draft' and revision != expected_revision:
        raise HTTPException(409, 'The selected content changed. Save and reload before exporting.')
    from api.routes.generations import _artifact_to_response
    data = (await version_data(db, row, artifact, generation, source))['artifact'] if row else (
        _artifact_to_response(artifact, generation, source).model_dump(mode='json') if target == 'original' else {})
    status = data.get('assurance_status', 'unreviewed')
    label = row.label if row else target.capitalize()
    state = f'{label} · ' + {'checks_passed': 'Required checks passed', 'needs_review': 'Needs review',
                                'overridden': 'Exception recorded; checks still failed'}.get(status, 'Unreviewed')
    appendix = []
    if citations:
        evidence = data.get('evidence') or {}
        claims = evidence.get('claims') or []
        if not claims: appendix.append('No reviewed references are recorded for this content.')
        for i, claim in enumerate(claims, 1):
            appendix.append(f"[{i}] {claim.get('claim', '')} ({claim.get('status', 'unreviewed')})")
            for anchor in claim.get('anchors', []):
                appendix.append(f"Source {anchor.get('source_id')} · {anchor.get('start')}–{anchor.get('end')}: {anchor.get('text', '')}")
    if provenance:
        appendix.extend([f'Artifact: {artifact_id}', f'Content SHA-256: {expected_hash}',
            f'Source: {source.filename or source.id}', f'Source SHA-256: {digest(source.extracted_text or "")}',
            f'Saved version: {row.id}' if row else f'Target: {target}; revision: {revision}', f'Review state: {status}'])
        if row and team():
            from teams.models import ReviewDecision
            decision=(await db.execute(select(ReviewDecision).where(ReviewDecision.version_id==row.id,
                ReviewDecision.content_hash==row.content_hash).order_by(ReviewDecision.created_at.desc()).limit(1))).scalar_one_or_none()
            appendix.append('Human approval: '+(decision.decision if decision else 'unapproved'))
            if decision:appendix.extend([f'Approval actor: {decision.actor}',f'Approval recorded: {aware(decision.created_at).isoformat()}',f'Approval decision: {decision.id}'])
        for document in getattr(source, 'source_documents', []):
            appendix.append(f"Source document: {document['filename']} · {document['id']} · SHA-256 {document['source_version']} · {document['sensitivity']}")
        for conflict in getattr(source, 'conflicts', []):
            decision = conflict.get('resolution') or {}
            appendix.append(f"Potential source conflict {conflict['id']}: {conflict['reason']} · Resolution: {decision.get('choice', 'preserve')} · Preferred source: {decision.get('preferred_source_id') or 'none'}")
    # Snapshot has been captured. Release the read transaction before slow conversion.
    await db.commit()
    from starlette.concurrency import run_in_threadpool
    from fastapi.responses import Response
    from revisions.exports import export, MIMES
    try:
        data = await run_in_threadpool(export, content, artifact.output_type.replace('_', ' ').title(), state, '\n'.join(appendix), format)
    except ValueError:
        raise HTTPException(422, 'This document contains text that the selected format cannot represent. Remove control characters or export Markdown.')
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    event(db, artifact_id, operator, 'ARTIFACT_EXPORTED', {'target': target, 'version_id': str(row.id) if row else None,
        'content_hash': expected_hash, 'format': format, 'citations': citations, 'provenance': provenance})
    await db.commit()
    return Response(data, media_type=MIMES[format], headers={'Content-Disposition':
        f'attachment; filename="{artifact.output_type}-{target}-{expected_hash[:8]}.{format}"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
