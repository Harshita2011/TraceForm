"""Validated ingestion, searchable source library and reversible removal of unused sources."""
import asyncio
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query
from sqlalchemy import select, func, update, exists
from agents.analyst.classifier import SensitivityClassifier
from api.dependencies import CurrentOperator, DbSession
from db.models import Source, Generation, GenerationDocument
from ingestion.extractors import ExtractionError, VideoReferenceOnly, extract_text_from_file, validate_extraction_length
from schemas.enums import SensitivityLevel, SensitivitySource
from storage.local import save_raw_file
from orchestrator.runtime import utcnow
router=APIRouter(prefix='/sources',tags=['sources'])
MAX_FILE_SIZE_BYTES=50*1024*1024
_classifier=SensitivityClassifier()

def usable(source):
    return bool(source.extracted_text and source.extracted_text.strip() and
                not source.extracted_text.startswith('[Video file') and not source.deleted_at)

def source_data(s,uses=0):
    import re
    filename=s.filename or re.sub(r'_[0-9a-f]{8}(\.[^.]+)$',r'\1',(s.raw_content_ref or 'Text source').replace('\\','/').split('/')[-1])
    return {'id':str(s.id),'filename':filename,'sensitivity':s.sensitivity.value,
            'sensitivity_source':s.sensitivity_source.value,'classifier_suggestion':s.sensitivity.value if s.sensitivity_source==SensitivitySource.CLASSIFIER else None,
            'classifier_confidence':s.sensitivity_confidence if s.sensitivity_source==SensitivitySource.CLASSIFIER else None,
            'word_count':len(s.extracted_text.split()) if s.extracted_text and not s.extracted_text.startswith('[Video file') else 0,
            'created_at':s.created_at.isoformat(),'status':'ready' if usable(s) else 'removed' if s.deleted_at else 'reference_only',
            'content_type':s.content_type,'extraction_method':s.extraction_method or 'legacy',
            'was_truncated':s.was_truncated,'generation_count':uses,'can_delete':uses==0 and not s.deleted_at,
            'deleted_at':s.deleted_at.isoformat() if s.deleted_at else None}

@router.post('/',status_code=201)
async def ingest_source(db:DbSession,operator:CurrentOperator,file:UploadFile|None=File(default=None),
    text:str|None=Form(default=None),sensitivity:str|None=Form(default=None),
    truncate_long_content:bool=Form(default=False)):
    if (file is None and text is None) or (file is not None and text is not None):
        raise HTTPException(422,"Provide either a file or a text field, not both.")
    try: level=SensitivityLevel(sensitivity.lower()) if sensitivity else None
    except ValueError: raise HTTPException(422,'Choose public, internal, restricted or confidential sensitivity.')
    raw=None; method='text'; content_type='text/plain'; truncated=False
    filename=(file.filename or 'upload').replace('\\','/').split('/')[-1][:240] if file else 'Text source.txt'
    content=None
    try:
        if file:
            content=await file.read(MAX_FILE_SIZE_BYTES+1)
            if len(content)>MAX_FILE_SIZE_BYTES: raise ExtractionError('File exceeds 50 MB. Upload a smaller file.')
            if not content: raise ExtractionError('The file is empty. Upload a document containing readable text.')
            try:
                extracted,content_type=await asyncio.to_thread(extract_text_from_file,content,filename)
                suffix=Path(filename).suffix.lower()
                method='ocr' if suffix in {'.jpg','.jpeg','.png','.tiff','.bmp','.gif'} else suffix.lstrip('.')
            except VideoReferenceOnly:
                extracted='[Video file — reference only; transcription is unavailable]';method='reference_only';content_type='video/reference'
        else: extracted=text or ''
        if method!='reference_only':
            if not extracted.strip(): raise ExtractionError('No readable text found. Upload a text-based document or a clearer scan.')
            extracted,truncated=validate_extraction_length(extracted,operator_truncate=truncate_long_content)
    except ExtractionError as exc: raise HTTPException(422,str(exc))
    final,confidence,origin=_resolve_sensitivity(level,extracted)
    if content is not None: raw=save_raw_file(content,filename)
    source=Source(filename=filename,content_type=content_type,extraction_method=method,was_truncated=truncated,
        raw_content_ref=raw,extracted_text=extracted,sensitivity=final,sensitivity_source=origin,sensitivity_confidence=confidence)
    db.add(source);await db.commit();await db.refresh(source)
    return {**source_data(source),'sensitivity_source':origin.value,'sensitivity_confidence':confidence,
        'extracted_text_length':0 if method=='reference_only' else len(extracted),
        'message':'Reference saved. Video transcription is unavailable; this source cannot generate outputs.' if method=='reference_only' else
                  'Source ready. Content was explicitly truncated to the extraction limit.' if truncated else 'Source ready.'}

async def query_sources(db,q,sensitivity,offset,limit,trash):
    filters=[Source.deleted_at.is_not(None) if trash else Source.deleted_at.is_(None)]
    if q:
        # Escape wildcard characters: searches are literal, not SQL LIKE patterns.
        needle=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        filters.append(func.lower(func.coalesce(Source.filename,Source.raw_content_ref,'Text source')).like('%'+needle.lower()+'%',escape='\\'))
    if sensitivity: filters.append(Source.sensitivity==sensitivity)
    uses=select(func.count(Generation.id)).where((Generation.source_id==Source.id) | exists(select(GenerationDocument.source_id).where(
        GenerationDocument.source_id==Source.id, GenerationDocument.generation_id==Generation.id).correlate(Source,Generation))).correlate(Source).scalar_subquery()
    total=await db.scalar(select(func.count(Source.id)).where(*filters))
    rows=(await db.execute(select(Source,uses).where(*filters).order_by(Source.created_at.desc(),Source.id.desc()).offset(offset).limit(limit))).all()
    return {'items':[source_data(s,n) for s,n in rows],'total':total,'offset':offset,'limit':limit}

@router.get('/')
async def list_sources(db:DbSession,operator:CurrentOperator,limit:int=Query(50,ge=1,le=200),
                       q:str=Query('',max_length=240),offset:int=Query(0,ge=0),sensitivity:SensitivityLevel|None=None):
    return (await query_sources(db,q,sensitivity,offset,limit,False))['items']

@router.get('/library')
async def source_library(db:DbSession,operator:CurrentOperator,q:str=Query('',max_length=240),
    sensitivity:SensitivityLevel|None=None,offset:int=Query(0,ge=0),limit:int=Query(12,ge=1,le=100),trash:bool=False):
    return await query_sources(db,q,sensitivity,offset,limit,trash)

@router.get('/{source_id}')
async def source_detail(source_id:UUID,db:DbSession,operator:CurrentOperator):
    source=await db.get(Source,source_id)
    if not source: raise HTTPException(404,'Source not found.')
    uses=await db.scalar(select(func.count(Generation.id)).where((Generation.source_id==source_id) | exists(select(GenerationDocument.source_id).where(
        GenerationDocument.source_id==source_id, GenerationDocument.generation_id==Generation.id))))
    return {**source_data(source,uses),'text':source.extracted_text}

@router.get('/{source_id}/text')
async def get_source_text(source_id:UUID,db:DbSession,operator:CurrentOperator, generation_id:UUID|None=None,
                          expected_version:str|None=Query(default=None,max_length=64)):
    source=await db.get(Source,source_id)
    if not source: raise HTTPException(404,'Source not found.')
    if source.deleted_at: raise HTTPException(409,'Restore this source before inspecting linked evidence.')
    from evidence.validation import version
    text=source.extracted_text; filename=source.filename
    if generation_id:
        from api.routes.generations import _check_version_owner
        from synthesis.context import load_context, document_rows
        generation=await db.get(Generation,generation_id)
        if not generation: raise HTTPException(404,'Run not found.')
        await _check_version_owner(db,generation_id,operator)
        await load_context(db,generation)
        rows=await document_rows(db,generation_id)
        row=next((r for r in rows if r.source_id==source_id),None)
        if rows and not row or not rows and generation.source_id!=source_id:
            raise HTTPException(404,'This source is not part of the selected run.')
        if row: text,filename=row.text,row.filename
    digest=version(text)
    if expected_version and expected_version!=digest: raise HTTPException(409,'The requested source version is unavailable; no substitute text was returned.')
    return {'id':str(source.id),'filename':filename,'text':text,'source_version':digest}

@router.delete('/{source_id}')
async def remove_source(source_id:UUID,db:DbSession,operator:CurrentOperator):
    if not await db.get(Source,source_id): raise HTTPException(404,'Source not found.')
    changed=await db.execute(update(Source).where(Source.id==source_id,
        ~exists(select(Generation.id).where(Generation.source_id==source_id)),
        ~exists(select(GenerationDocument.source_id).where(GenerationDocument.source_id==source_id))).values(deleted_at=utcnow()))
    if not changed.rowcount: raise HTTPException(409,'This source is linked to saved runs. Keep it to preserve their evidence.')
    await db.commit(); return {'message':'Moved to trash. You can restore this source; its stored file is retained.'}

@router.post('/{source_id}/restore')
async def restore_source(source_id:UUID,db:DbSession,operator:CurrentOperator):
    source=await db.get(Source,source_id)
    if not source: raise HTTPException(404,'Source not found.')
    source.deleted_at=None;await db.commit();return source_data(source)

def _resolve_sensitivity(
    operator_sensitivity: SensitivityLevel | None,
    text: str,
) -> tuple[SensitivityLevel, float, SensitivitySource]:
    """
    §3.1.1 — Resolve final sensitivity.
    Operator-supplied value always wins. Falls back to classifier suggestion.
    Always records sensitivity_source so downstream code knows the provenance.
    """
    if operator_sensitivity is not None:
        return operator_sensitivity, 1.0, SensitivitySource.OPERATOR

    classified_level, confidence = _classifier.classify(text)
    return classified_level, confidence, SensitivitySource.CLASSIFIER
