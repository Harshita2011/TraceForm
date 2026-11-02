"""Reproducible human-adjudicated measurements; exact anchors do not establish truth."""
import json
from uuid import UUID
from sqlalchemy import select
from eval.models import BenchmarkCase,BenchmarkExecution,BenchmarkOutcome
from db.models import Generation,ArtifactVersion
from orchestrator.runtime import fence,current_run
from revisions.content import digest
from schemas.enums import GenerationStatus

VERSION='human-claims-and-anchors:1'

def counts(case):
    claims=case.annotations['claims']
    evidence=case.snapshot.get('evidence_claims',[])
    cited=sum(any(c.get('claim')==item['claim'] and c.get('anchors') and
        all(a.get('status')=='matched' for a in c['anchors']) for c in evidence) for item in claims)
    return {'claims':len(claims),'supported':sum(c['verdict']=='supported' for c in claims),
        'unsupported':sum(c['verdict']=='unsupported' for c in claims),'uncertain':sum(c['verdict']=='uncertain' for c in claims),
        'cited':cited,'complete':case.annotations['complete_claim_inventory'],
        'style_passed':case.annotations.get('style_passed')}

def aggregate(rows,total):
    valid=[r.counts for r in rows if r.status=='measured']
    n=sum(r['claims'] for r in valid);supported=sum(r['supported'] for r in valid)
    unsupported=sum(r['unsupported'] for r in valid);uncertain=sum(r['uncertain'] for r in valid)
    complete=bool(valid) and len(valid)==total and all(r['complete'] for r in valid) and uncertain==0 and n>0
    style=[r['style_passed'] for r in valid if r['style_passed'] is not None]
    return {'measurement_version':VERSION,'dataset_size':total,'measured_cases':len(valid),
        'failed_cases':sum(r.status!='measured' for r in rows),'pending_cases':total-len(rows),
        'claim_count':n,'supported_claims':supported,'unsupported_claims':unsupported,'uncertain_claims':uncertain,
        'complete_claim_inventory':complete,'fact_accuracy':supported/n if complete else None,
        'hallucination_rate':unsupported/n if complete else None,
        'citation_coverage':sum(r['cited'] for r in valid)/n if n else None,
        'citation_denominator':n,'style_adherence_rate':sum(style)/len(style) if style else None,
        'style_denominator':len(style),'provenance':'human_annotated',
        'definitions':{'fact_accuracy':'Human-supported claims / complete adjudicated claim inventory; not an automatic truth guarantee.',
            'hallucination_rate':'Human-unsupported claims / complete adjudicated claim inventory.',
            'citation_coverage':'Annotated claims with matching recorded citation anchors / annotated claims.',
            'style_adherence_rate':'Human style passes / explicitly style-assessed cases.'}}

async def assert_case(db,case):
    from db.models import Artifact
    from synthesis.context import load_context
    version=await db.get(ArtifactVersion,case.version_id)
    if not version:raise ValueError('Saved version is unavailable.')
    artifact=await db.get(Artifact,version.artifact_id)
    generation=await db.get(Generation,artifact.generation_id) if artifact else None
    if not generation:raise ValueError('Generation is unavailable.')
    source=await load_context(db,generation)
    if source.deleted_at:raise ValueError('Source is removed.')
    if version.content_hash!=case.snapshot['content_hash'] or digest(source.extracted_text or '')!=case.snapshot['source_hash']:
        raise ValueError('Source or saved content no longer matches this dataset version.')
    return version

async def execute(task,generation_id):
    run=current_run.get();gid=UUID(generation_id)
    async with run.session_factory() as db:
        await fence(db)
        execution=await db.get(BenchmarkExecution,gid)
        cases=(await db.execute(select(BenchmarkCase).where(BenchmarkCase.dataset_id==execution.dataset_id).order_by(BenchmarkCase.id))).scalars().all()
        generation=await db.get(Generation,gid);generation.status=GenerationStatus.RUNNING;await db.commit()
    for case in cases:
        async with run.session_factory() as db:
            await fence(db)
            previous=await db.scalar(select(BenchmarkOutcome.id).where(BenchmarkOutcome.execution_id==gid,BenchmarkOutcome.case_id==case.id))
            if previous:continue
            try:
                await assert_case(db,case);value=counts(case);status='measured';message=None
            except Exception as exc:
                from fastapi import HTTPException
                from synthesis.context import SourceUnavailable
                if not isinstance(exc,(ValueError,HTTPException,SourceUnavailable)):raise
                value={};status='failed';message='Saved source/version is unavailable or changed. Create a new dataset version.'
            db.add(BenchmarkOutcome(execution_id=gid,case_id=case.id,status=status,counts=value,message=message))
            await fence(db);await db.commit()
    async with run.session_factory() as db:
        await fence(db)
        execution=await db.get(BenchmarkExecution,gid)
        rows=(await db.execute(select(BenchmarkOutcome).where(BenchmarkOutcome.execution_id==gid))).scalars().all()
        execution.metrics=aggregate(rows,len(cases))
        generation=await db.get(Generation,gid)
        generation.status=GenerationStatus.PARTIAL_FAILURE if any(r.status!='measured' for r in rows) else GenerationStatus.COMPLETED
        from db.models import AuditRecord
        db.add(AuditRecord(event_type='EVALUATION_COMPLETED',operator_id=execution.creator,resource_id=str(gid),metadata_json={'dataset_id':str(execution.dataset_id),'measurement_version':VERSION}))
        await db.commit()
