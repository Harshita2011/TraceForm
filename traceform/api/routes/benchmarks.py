"""Workspace-scoped, immutable evaluation evidence; no provider call is made by scoring."""
import json
from uuid import UUID,uuid4
from typing import Literal
from fastapi import APIRouter,HTTPException,Query
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from api.dependencies import CurrentOperator,DbSession
from db.models import Generation,DurableJob,JobRequest,Artifact,AuditRecord
from eval.models import BenchmarkDataset,BenchmarkCase,BenchmarkExecution,BenchmarkOutcome
from eval.measured import VERSION,aggregate,assert_case
from revisions.content import digest,payload_hash
from orchestrator.runtime import plan_fingerprint,aware
from teams.scope import workspace,team

router=APIRouter(prefix='/evaluations',tags=['measured evaluations'])
class Claim(BaseModel):
    claim:str=Field(min_length=1,max_length=3000)
    verdict:Literal['supported','unsupported','uncertain']
    reason:str=Field(min_length=3,max_length=2000)
    source_span:str=Field(default='',max_length=3000)
    source_id:UUID|None=None
class CaseWrite(BaseModel):
    version_id:UUID
    title:str=Field(min_length=1,max_length=150)
    claims:list[Claim]=Field(default_factory=list,max_length=100)
    complete_claim_inventory:bool=False
    style_passed:bool|None=None
    style_notes:str=Field(default='',max_length=2000)
class DatasetWrite(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    version:str=Field(min_length=1,max_length=40)
    notes:str=Field(default='',max_length=3000)
    cases:list[CaseWrite]=Field(min_length=1,max_length=50)
    @field_validator('name','version')
    @classmethod
    def nonempty(cls,value):
        if not value.strip():raise ValueError('Enter a nonempty name/version.')
        return value.strip()
class Execute(BaseModel):
    dataset_id:UUID
    request_id:UUID

def permitted(row,operator):
    return row is not None and (team() or row.creator==operator)

def visibility(model,operator):
    return True if team() else model.creator==operator

def dataset_data(row,count):
    return {'id':str(row.id),'name':row.name,'version':row.version,'notes':row.notes,'case_count':count,
        'digest':row.digest,'provenance':row.provenance,'creator':row.creator,'created_at':aware(row.created_at).isoformat()}

@router.get('/datasets')
async def datasets(db:DbSession,operator:CurrentOperator,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
    total=await db.scalar(select(func.count(BenchmarkDataset.id)).where(visibility(BenchmarkDataset,operator)))
    rows=(await db.execute(select(BenchmarkDataset).where(visibility(BenchmarkDataset,operator)).order_by(BenchmarkDataset.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    items=[]
    for row in rows:
        n=await db.scalar(select(func.count(BenchmarkCase.id)).where(BenchmarkCase.dataset_id==row.id))
        items.append(dataset_data(row,n))
    return {'items':items,'total':total}

@router.post('/datasets',status_code=201)
async def create_dataset(data:DatasetWrite,db:DbSession,operator:CurrentOperator):
    from api.routes.workspaces import owned_version,context,version_data
    from synthesis.context import evidence_text
    if len({c.version_id for c in data.cases})!=len(data.cases):raise HTTPException(422,'Each saved version can appear only once in a dataset.')
    prepared=[]
    for case in data.cases:
        from db.models import ArtifactVersion
        version=await db.get(ArtifactVersion,case.version_id)
        if not version:raise HTTPException(404,'Saved version not found.')
        artifact,generation,source=await context(db,version.artifact_id,operator)
        version=await owned_version(db,artifact.id,case.version_id,operator)
        if version.source_hash!=digest(source.extracted_text or ''):raise HTTPException(409,'Source changed. Save a new output version before annotating it.')
        if not case.claims and case.style_passed is None:raise HTTPException(422,'Annotate at least one claim or provide a style assessment.')
        if case.style_passed is not None and len(case.style_notes.strip())<3:raise HTTPException(422,'Explain the style assessment.')
        if len({c.claim for c in case.claims})!=len(case.claims):raise HTTPException(422,'Annotate each claim once.')
        text=evidence_text(source)
        for claim in case.claims:
            if not claim.claim.strip() or claim.claim not in version.content:raise HTTPException(422,'Each annotated claim must be an exact passage in the saved output.')
            if len(claim.reason.strip())<3:raise HTTPException(422,'Explain each human assessment.')
            if claim.verdict=='supported':
                sid=str(claim.source_id or source.id)
                document=text.get(sid) if isinstance(text,dict) else text if sid==str(source.id) else None
                document=document.get('text') if isinstance(document,dict) else document
                if not claim.source_span.strip() or not document or claim.source_span not in document:
                    raise HTTPException(422,'Supported claims require an exact quote from the selected source document.')
                claim.source_id=UUID(sid)
        report=await version_data(db,version,artifact,generation,source)
        snapshot={'artifact_id':str(artifact.id),'generation_id':str(generation.id),'content_hash':version.content_hash,
            'source_hash':version.source_hash,'content':version.content,'output_type':artifact.output_type,
            'model_version':generation.model_version,'prompt_version':generation.prompt_version,
            'reviewer_version':generation.reviewer_version,'evidence_claims':(report['artifact'].get('evidence') or {}).get('claims',[])}
        prepared.append((case,snapshot))
    value=payload_hash([[c.model_dump(mode='json'),s] for c,s in prepared])
    row=BenchmarkDataset(name=data.name,version=data.version,notes=data.notes,creator=operator,digest=value)
    db.add(row)
    try:
        await db.flush()
        for case,snapshot in prepared:
            db.add(BenchmarkCase(dataset_id=row.id,version_id=case.version_id,title=case.title,snapshot=snapshot,
                annotations=case.model_dump(mode='json',exclude={'version_id','title'})))
        db.add(AuditRecord(event_type='EVALUATION_DATASET_CREATED',operator_id=operator,resource_id=str(row.id),metadata_json={'digest':value,'cases':len(prepared)}))
        await db.commit()
    except IntegrityError:
        await db.rollback();raise HTTPException(409,'This dataset name and version already exist. Choose a new version.')
    return dataset_data(row,len(prepared))

@router.get('/datasets/{dataset_id}')
async def get_dataset(dataset_id:UUID,db:DbSession,operator:CurrentOperator,offset:int=Query(0,ge=0),limit:int=Query(5,ge=1,le=5)):
    row=await db.get(BenchmarkDataset,dataset_id)
    if not permitted(row,operator):raise HTTPException(404,'Dataset not found.')
    cases=(await db.execute(select(BenchmarkCase).where(BenchmarkCase.dataset_id==row.id).order_by(BenchmarkCase.id))).scalars().all()
    values=[]
    for case in cases[offset:offset+limit]:
        try:
            await assert_case(db,case)
            values.append({'id':str(case.id),'title':case.title,'version_id':str(case.version_id),'snapshot':case.snapshot,'annotations':case.annotations,'available':True})
        except (ValueError,HTTPException):values.append({'id':str(case.id),'title':case.title,'available':False})
    return {**dataset_data(row,len(cases)),'cases':values}

@router.post('/execute',status_code=202)
async def execute(data:Execute,db:DbSession,operator:CurrentOperator):
    key=digest(f'benchmark:{workspace.get() or "legacy"}:{operator}:{data.request_id}')
    ph=payload_hash(data.model_dump(mode='json'))
    old=await db.get(JobRequest,key)
    if old:
        if old.payload_hash!=ph:raise HTTPException(409,'Request ID reused with different settings.')
        return {'id':str(old.generation_id)}
    dataset=await db.get(BenchmarkDataset,data.dataset_id)
    if not permitted(dataset,operator):raise HTTPException(404,'Dataset not found.')
    cases=(await db.execute(select(BenchmarkCase).where(BenchmarkCase.dataset_id==dataset.id))).scalars().all()
    if not cases:raise HTTPException(409,'Dataset has no cases.')
    from db.models import ArtifactVersion
    first=await db.get(ArtifactVersion,cases[0].version_id)
    if not first:raise HTTPException(409,'The first saved version is unavailable.')
    artifact=await db.get(Artifact,first.artifact_id)
    parent=await db.get(Generation,artifact.generation_id)
    from config.provider import current_configuration
    configuration,_=await current_configuration(db)
    from schemas.enums import GenerationStatus
    gen=Generation(kind='evaluation',source_id=parent.source_id,output_types=[],params={},status=GenerationStatus.QUEUED,
        budget_type='tokens',budget_ceiling=0,model_version='human-annotations')
    db.add(gen);await db.flush()
    db.add(BenchmarkExecution(generation_id=gen.id,dataset_id=dataset.id,measurement_version=VERSION,creator=operator))
    db.add(DurableJob(generation_id=gen.id,task_kind='evaluation',configuration_id=configuration.id,plan_fingerprint=plan_fingerprint()))
    db.add(JobRequest(key_hash=key,payload_hash=ph,generation_id=gen.id))
    db.add(AuditRecord(event_type='EVALUATION_STARTED',operator_id=operator,resource_id=str(gen.id),metadata_json={'dataset_id':str(dataset.id),'measurement_version':VERSION}))
    await db.commit();return {'id':str(gen.id)}

@router.get('/executions')
async def executions(db:DbSession,operator:CurrentOperator,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
    total=await db.scalar(select(func.count(BenchmarkExecution.generation_id)).where(visibility(BenchmarkExecution,operator)))
    rows=(await db.execute(select(BenchmarkExecution,Generation,BenchmarkDataset).join(Generation,Generation.id==BenchmarkExecution.generation_id)
        .join(BenchmarkDataset,BenchmarkDataset.id==BenchmarkExecution.dataset_id).where(visibility(BenchmarkExecution,operator)).order_by(BenchmarkExecution.created_at.desc()).offset(offset).limit(limit))).all()
    return {'total':total,'items':[{'id':str(r.generation_id),'dataset_id':str(r.dataset_id),'name':d.name,'version':d.version,
        'status':g.status.value,'measurement_version':r.measurement_version,'metrics':r.metrics,'created_at':aware(r.created_at).isoformat()} for r,g,d in rows]}

@router.get('/executions/{execution_id}')
async def execution(execution_id:UUID,db:DbSession,operator:CurrentOperator,offset:int=Query(0,ge=0),limit:int=Query(5,ge=1,le=5)):
    row=await db.get(BenchmarkExecution,execution_id)
    if not permitted(row,operator):raise HTTPException(404,'Execution not found.')
    gen=await db.get(Generation,execution_id);job=await db.get(DurableJob,execution_id)
    cases=(await db.execute(select(BenchmarkCase).where(BenchmarkCase.dataset_id==row.dataset_id).order_by(BenchmarkCase.id))).scalars().all()
    outcomes=(await db.execute(select(BenchmarkOutcome).where(BenchmarkOutcome.execution_id==execution_id))).scalars().all()
    by_case={o.case_id:o for o in outcomes};values=[]
    for case in cases[offset:offset+limit]:
        outcome=by_case.get(case.id)
        try:await assert_case(db,case);available=True
        except (ValueError,HTTPException):available=False
        values.append({'case_id':str(case.id),'title':case.title,'version_id':str(case.version_id),
            'artifact_id':case.snapshot['artifact_id'],'available':available,
            'status':outcome.status if outcome else 'pending','counts':outcome.counts if outcome else None,
            'message':outcome.message if outcome else None,'annotations':case.annotations if available else None,
            'content':case.snapshot['content'] if available else None})
    recomputed=aggregate(outcomes,len(cases)) if row.measurement_version==VERSION else None
    return {'id':str(execution_id),'dataset_id':str(row.dataset_id),'status':gen.status.value,'measurement_version':row.measurement_version,
        'metrics':row.metrics,'recomputed_metrics':recomputed,'recomputation_matches':row.metrics==recomputed if row.metrics else None,
        'can_cancel':job.status in {'queued','running'},'message':job.message,'cases':values,'case_count':len(cases),'provenance':'human_annotated'}

@router.post('/executions/{execution_id}/cancel')
async def cancel(execution_id:UUID,db:DbSession,operator:CurrentOperator):
    if not permitted(await db.get(BenchmarkExecution,execution_id),operator):raise HTTPException(404,'Execution not found.')
    from api.routes.generations import cancel_generation
    return await cancel_generation(execution_id,db,operator)
