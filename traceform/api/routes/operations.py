"""Recorded timings and usage, with explicit denominators and missing-data counts."""
from datetime import datetime,timedelta,timezone
import math
from collections import defaultdict
from fastapi import APIRouter,HTTPException,Query
from sqlalchemy import select,func
from api.dependencies import DbSession,CurrentOperator
from db.models import Generation,DurableJob,LLMCall,Artifact,WorkerState
from orchestrator.runtime import utcnow,aware

router=APIRouter(prefix='/operations',tags=['operations'])
def window(since,until):
    end=aware(until) if until else utcnow()
    start=aware(since) if since else end-timedelta(days=30)
    if start>=end or end-start>timedelta(days=366):raise HTTPException(422,'Choose an increasing date range of at most 366 days.')
    return start,end
def elapsed(start,end):return max(0,(aware(end)-aware(start)).total_seconds()*1000) if start and end else None
def percentile(values,p):
    if not values:return None
    values=sorted(values);k=(len(values)-1)*p;low=math.floor(k);high=math.ceil(k)
    return round(values[low]*(high-k)+values[high]*(k-low),3) if high!=low else round(values[low],3)
def usage(call):
    value=call.usage or {};known=call.status=='succeeded' and value.get('usage_recorded',True) and value.get('estimated_cost_usd') is not None
    return value,known

@router.get('/summary')
async def summary(db:DbSession,operator:CurrentOperator,since:datetime|None=None,until:datetime|None=None):
    start,end=window(since,until)
    filters=(LLMCall.created_at>=start,LLMCall.created_at<end)
    n=await db.scalar(select(func.count(LLMCall.id)).where(*filters))
    if n>50000:raise HTTPException(422,'This range contains over 50,000 requests. Choose a narrower range.')
    calls=(await db.execute(select(LLMCall).where(*filters))).scalars().all()
    admitted=(await db.execute(select(Generation.id,Generation.kind,Generation.created_at).where(Generation.created_at>=start,Generation.created_at<end))).all()
    completed=(await db.execute(select(DurableJob).where(DurableJob.finished_at>=start,DurableJob.finished_at<end))).scalars().all()
    artifacts=(await db.execute(select(Artifact.review_status,func.count(Artifact.id)).join(Generation,Generation.id==Artifact.generation_id)
        .where(Generation.created_at>=start,Generation.created_at<end).group_by(Artifact.review_status))).all()
    model_rows={};series=defaultdict(lambda:{'admitted_jobs':0,'finished_jobs':0,'provider_requests':0,'known_tokens':0,'estimated_cost_usd':0.0})
    known_cost=0;known_tokens=0;unknown=0;durations=[]
    for call in calls:
        value,known=usage(call);duration=elapsed(call.created_at,call.finished_at)
        if duration is not None:durations.append(duration)
        key=(call.provider,call.model)
        row=model_rows.setdefault(key,{'provider':call.provider,'model':call.model,'requests':0,'succeeded':0,'failed':0,'uncertain':0,'started':0,'known_usage_requests':0,'unknown_usage_requests':0,'tokens':0,'estimated_cost_usd':0.0,'durations':[]})
        row['requests']+=1;row[call.status]+=1
        daily=series[aware(call.created_at).date().isoformat()];daily['provider_requests']+=1
        if duration is not None:row['durations'].append(duration)
        if known:
            tokens=value.get('input_tokens',0)+value.get('output_tokens',0);cost=value['estimated_cost_usd']
            known_tokens+=tokens;known_cost+=cost;row['tokens']+=tokens;row['estimated_cost_usd']+=cost;row['known_usage_requests']+=1
            daily['known_tokens']+=tokens;daily['estimated_cost_usd']+=cost
        else:unknown+=1;row['unknown_usage_requests']+=1
    for gid,kind,created in admitted:series[aware(created).date().isoformat()]['admitted_jobs']+=1
    job_durations=[]
    for job in completed:
        series[aware(job.finished_at).date().isoformat()]['finished_jobs']+=1
        value=elapsed(job.created_at,job.finished_at)
        if value is not None:job_durations.append(value)
    models=[]
    for row in model_rows.values():
        d=row.pop('durations');row.update(p50_ms=percentile(d,.5),p95_ms=percentile(d,.95),duration_samples=len(d))
        row['estimated_cost_usd']=round(row['estimated_cost_usd'],8);models.append(row)
    recent=await db.scalar(select(func.max(WorkerState.last_seen_at)))
    return {'since':start.isoformat(),'until':end.isoformat(),'measurement_version':'operations:1',
        'admitted_jobs':len(admitted),'job_kinds':{k:sum(kind==k for _,kind,_ in admitted) for k in {kind for _,kind,_ in admitted}},
        'finished_jobs':len(completed),'successful_jobs':sum(j.status=='completed' for j in completed),
        'finished_jobs_per_hour':len(completed)/((end-start).total_seconds()/3600),
        'provider_requests':len(calls),'failed_requests':sum(c.status=='failed' for c in calls),
        'uncertain_requests':sum(c.status=='uncertain' for c in calls),'known_usage_requests':len(calls)-unknown,
        'unknown_usage_requests':unknown,'tokens':known_tokens,'estimated_cost_usd':round(known_cost,8),
        'call_latency':{'p50_ms':percentile(durations,.5),'p95_ms':percentile(durations,.95),'samples':len(durations)},
        'job_latency':{'p50_ms':percentile(job_durations,.5),'p95_ms':percentile(job_durations,.95),'samples':len(job_durations)},
        'review_outcomes':{status.value if status else 'unreviewed':count for status,count in artifacts},
        'models':models,'daily':[{'date':day,**values} for day,values in sorted(series.items())],
        'worker_online':bool(recent and (utcnow()-aware(recent)).total_seconds()<30),
        'definitions':{'latency':'Elapsed wall time from recorded start to finish. Job latency includes queueing; missing finish times are excluded.',
            'cost':'Sum of provider usage × the pricing saved with each request. Estimates, not invoices; unknown usage is excluded and counted.',
            'throughput':'Jobs finishing in the selected UTC window / window hours. Admissions are counted separately.',
            'quality':'Reviewer outcomes are workflow results; they are not benchmark factual accuracy.'}}

@router.get('/requests')
async def requests(db:DbSession,operator:CurrentOperator,since:datetime|None=None,until:datetime|None=None,
                   status:str=Query('',max_length=20),model:str=Query('',max_length=150),offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100)):
    start,end=window(since,until);stmt=select(LLMCall).where(LLMCall.created_at>=start,LLMCall.created_at<end)
    if status:
        if status not in {'started','succeeded','failed','uncertain'}:raise HTTPException(422,'Choose a recorded request status.')
        stmt=stmt.where(LLMCall.status==status)
    if model:stmt=stmt.where(LLMCall.model==model)
    total=await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=(await db.execute(stmt.order_by(LLMCall.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return {'total':total,'items':[{'id':str(c.id),'generation_id':str(c.generation_id),'provider':c.provider,'model':c.model,
        'status':c.status,'stage':c.stage,'created_at':aware(c.created_at).isoformat(),'elapsed_ms':elapsed(c.created_at,c.finished_at),
        'estimated_cost_usd':usage(c)[0].get('estimated_cost_usd') if usage(c)[1] else None,
        'tokens':usage(c)[0].get('input_tokens',0)+usage(c)[0].get('output_tokens',0) if usage(c)[1] else None,
        'message':c.error} for c in rows]}
