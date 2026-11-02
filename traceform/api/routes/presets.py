"""Operator-private, server-backed creation presets with optimistic revision checks."""
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update, delete
from api.dependencies import CurrentOperator, DbSession
from db.models import CreationPreset
from teams.scope import team
from schemas.generation import GenerationParams
from schemas.formats import FORMAT_LABELS
router=APIRouter(prefix='/presets',tags=['presets'])

class PresetSettings(BaseModel):
    params: GenerationParams = Field(default_factory=GenerationParams)
    output_types: list[str] = Field(min_length=1,max_length=13)
    @field_validator('output_types')
    @classmethod
    def valid_formats(cls, values):
        if any(v not in FORMAT_LABELS for v in values) or len(values)!=len(set(values)):
            raise ValueError('Choose distinct supported output formats')
        return values
class PresetWrite(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    settings: PresetSettings
    expected_revision: int | None = Field(default=None,ge=1)
    @field_validator('name')
    @classmethod
    def nonempty(cls,value):
        if not value.strip(): raise ValueError('Enter a preset name')
        return value.strip()
def public(row):
    return {'id':str(row.id),'name':row.name,'settings':row.settings,'revision':row.revision}
@router.get('/')
async def list_presets(db:DbSession,operator:CurrentOperator):
    rows=(await db.execute(select(CreationPreset).where((True if team() else CreationPreset.owner==operator)).order_by(CreationPreset.created_at.desc()))).scalars().all()
    return [public(r) for r in rows]
@router.post('/',status_code=201)
async def create_preset(body:PresetWrite,db:DbSession,operator:CurrentOperator):
    row=CreationPreset(owner=operator,name=body.name,settings=body.settings.model_dump())
    db.add(row); await db.commit(); return public(row)
@router.put('/{preset_id}')
async def update_preset(preset_id:UUID,body:PresetWrite,db:DbSession,operator:CurrentOperator):
    row=await db.get(CreationPreset,preset_id)
    if not row or (row.owner!=operator and not team()): raise HTTPException(404,'Preset not found.')
    result=await db.execute(update(CreationPreset).where(CreationPreset.id==preset_id,
        (True if team() else CreationPreset.owner==operator),CreationPreset.revision==body.expected_revision).values(
        name=body.name,settings=body.settings.model_dump(),revision=CreationPreset.revision+1))
    if not result.rowcount: raise HTTPException(409,'Preset changed. Reload saved presets before updating.')
    await db.commit(); await db.refresh(row); return public(row)
@router.delete('/{preset_id}')
async def delete_preset(preset_id:UUID,db:DbSession,operator:CurrentOperator):
    result=await db.execute(delete(CreationPreset).where(CreationPreset.id==preset_id,(True if team() else CreationPreset.owner==operator)))
    if not result.rowcount: raise HTTPException(404,'Preset not found.')
    await db.commit(); return {'message':'Preset removed. Existing runs are unchanged.'}
