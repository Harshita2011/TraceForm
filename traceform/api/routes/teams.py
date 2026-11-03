"""User authentication, workspace membership and version-bound collaboration."""
import asyncio,secrets
from datetime import timedelta
from uuid import UUID,uuid4
from fastapi import APIRouter,HTTPException,Request,Response,Query
from pydantic import BaseModel,Field,field_validator
from typing import Literal
from sqlalchemy import select,func,update
from sqlalchemy.exc import IntegrityError
from api.dependencies import DbSession,CurrentOperator,CurrentAdmin
from db.models import ArtifactVersion,Artifact,Generation,AuditRecord
from teams.models import User,Workspace,Member,SessionToken,Invitation,ReviewRequest,ReviewDecision,Comment
from teams.auth import COOKIE,digest,password,matches,issue,current,require,DUMMY_PASSWORD_HASH
from teams.scope import identity,workspace
from orchestrator.runtime import utcnow,aware

router=APIRouter(tags=['teams'])
Role=Literal['owner','editor','reviewer','viewer']
class Credentials(BaseModel):
    email:str=Field(max_length=254)
    password:str=Field(min_length=12,max_length=128)
    name:str=Field(default='Workspace owner',min_length=1,max_length=100)
    @field_validator('name')
    @classmethod
    def name_valid(cls,value):
        if not value.strip():raise ValueError('Enter your name.')
        return value.strip()
    @field_validator('email')
    @classmethod
    def email_valid(cls,value):
        value=value.strip().lower()
        if '@' not in value or any(c.isspace() for c in value):raise ValueError('Enter an email address.')
        return value
class SpaceWrite(BaseModel):name:str=Field(min_length=1,max_length=100)
class InviteWrite(BaseModel):
    email:str=Field(max_length=254)
    role:Literal['editor','reviewer','viewer']
    @field_validator('email')
    @classmethod
    def email_valid(cls,value):return Credentials.email_valid(value)
class Accept(Credentials):token:str=Field(min_length=20,max_length=100)
class Switch(BaseModel):workspace_id:str=Field(max_length=36)
class RoleWrite(BaseModel):role:Role

def audit(db,action,resource=None,**details):
    who=identity.get()
    db.add(AuditRecord(event_type=action,operator_id=who['user_id'] if who else 'setup',
        resource_id=str(resource) if resource else None,metadata_json=details))

@router.get('/auth/status')
async def status(db:DbSession):
    installation=await db.get(Workspace,'legacy')
    return {'setup_required':installation is None,'authenticated':bool(identity.get())}

@router.post('/auth/register',status_code=201)
async def register(data:Credentials,db:DbSession,response:Response,request:Request):
    """Public registration owns a new workspace, never the installation's data."""
    from teams.login_limits import attempt
    try:
        attempt(request.client.host if request.client else 'unknown','registration')
    except HTTPException as exc:
        if exc.status_code==429:
            raise HTTPException(429,'Too many account creation attempts. Try again in five minutes.') from None
        raise
    user=User(email=data.email,name=data.name,password_hash=await asyncio.to_thread(password,data.password))
    space=Workspace(name=f"{data.name[:80]}'s workspace")
    try:
        db.add_all([user,space]);await db.flush()
        db.add(Member(space_id=space.id,user_id=user.id,role='owner'))
        await issue(db,user,space.id,response)
        db.add(AuditRecord(workspace_id=space.id,event_type='ACCOUNT_CREATED',operator_id=user.id,
                           resource_id=user.id,metadata_json={}))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409,'Unable to create this account. Try signing in or use another email address.') from None
    return {'id':user.id,'workspace_id':space.id}

@router.post('/auth/setup',status_code=201)
async def setup(data:Credentials,db:DbSession,response:Response,operator:CurrentAdmin):
    if await db.get(Workspace,'legacy'):raise HTTPException(409,'Installation setup is already complete. Sign in or create a separate account.')
    user=User(email=data.email,name=data.name.strip(),password_hash=await asyncio.to_thread(password,data.password))
    db.add(user);db.add(Workspace(id='legacy',name='My workspace'))
    try:
        await db.flush();db.add(Member(space_id='legacy',user_id=user.id,role='owner'))
        await issue(db,user,'legacy',response)
        db.add(AuditRecord(event_type='WORKSPACE_CLAIMED',operator_id=operator,resource_id='legacy',metadata_json={'owner':user.id}))
        await db.commit()
    except IntegrityError:
        await db.rollback();raise HTTPException(409,'Account setup is already complete.')
    return {'id':user.id,'workspace_id':'legacy'}

@router.post('/auth/login')
async def login(data:Credentials,db:DbSession,response:Response,request:Request):
    # In-process guard is supplemented by deployment rate limiting; bounded and expiry based.
    from teams.login_limits import attempt
    attempt(request.client.host if request.client else 'unknown',data.email)
    user=(await db.execute(select(User).where(User.email==data.email))).scalar_one_or_none()
    stored=user.password_hash if user else DUMMY_PASSWORD_HASH
    valid=await asyncio.to_thread(matches,data.password,stored)
    if not user or not user.active or not valid:raise HTTPException(401,'Email or password is incorrect.')
    member=(await db.execute(select(Member).where(Member.user_id==user.id).order_by(Member.space_id).limit(1))).scalar_one_or_none()
    if not member:raise HTTPException(403,'No workspace membership. Ask a workspace owner for an invitation.')
    await issue(db,user,member.space_id,response);await db.commit()
    return {'id':user.id,'workspace_id':member.space_id}

@router.post('/auth/logout')
async def logout(request:Request,response:Response,db:DbSession):
    token=request.cookies.get(COOKIE) or request.headers.get('authorization','').removeprefix('Bearer ')
    row=await db.get(SessionToken,digest(token)) if token else None
    if row:await db.delete(row)
    response.delete_cookie(COOKIE,path='/');await db.commit();return {'message':'Signed out.'}

@router.get('/auth/me')
async def me(db:DbSession):
    who=current()
    rows=(await db.execute(select(Workspace,Member.role).join(Member,Member.space_id==Workspace.id).where(Member.user_id==who['user_id']))).all()
    return {**who,'workspaces':[{'id':w.id,'name':w.name,'role':role} for w,role in rows]}

@router.post('/auth/switch')
async def switch(data:Switch,request:Request,db:DbSession):
    who=current();member=await db.get(Member,(data.workspace_id,who['user_id']))
    if not member:raise HTTPException(404,'Workspace not found.')
    token=request.cookies.get(COOKIE) or request.headers.get('authorization','').removeprefix('Bearer ')
    row=await db.get(SessionToken,digest(token));row.space_id=data.workspace_id
    await db.commit();return {'workspace_id':data.workspace_id}

@router.post('/team-workspaces',status_code=201)
async def create_space(data:SpaceWrite,db:DbSession):
    who=current()
    if not data.name.strip():raise HTTPException(422,'Enter a workspace name.')
    row=Workspace(name=data.name.strip());db.add(row);await db.flush()
    db.add(Member(space_id=row.id,user_id=who['user_id'],role='owner'))
    token=workspace.set(row.id)
    try:
        audit(db,'WORKSPACE_CREATED',row.id,name=row.name);await db.commit()
    finally:workspace.reset(token)
    return {'id':row.id,'name':row.name}

@router.get('/team-members')
async def members(db:DbSession):
    who=current()
    rows=(await db.execute(select(User,Member.role).join(Member,Member.user_id==User.id).where(Member.space_id==who['workspace_id']))).all()
    return [{'id':u.id,'name':u.name,'email':u.email,'role':r} for u,r in rows]

@router.put('/team-members/{user_id}')
async def change_member(user_id:str,data:RoleWrite,db:DbSession):
    who=require('owner')
    # Lock the workspace to serialize last-owner protection on PostgreSQL.
    await db.execute(update(Workspace).where(Workspace.id==who['workspace_id']).values(name=Workspace.name))
    member=await db.get(Member,(who['workspace_id'],user_id))
    if not member:raise HTTPException(404,'Member not found.')
    if member.role=='owner' and data.role!='owner':
        owners=await db.scalar(select(func.count()).select_from(Member).where(Member.space_id==who['workspace_id'],Member.role=='owner'))
        if owners<=1:raise HTTPException(409,'Keep at least one workspace owner.')
    old=member.role;member.role=data.role;audit(db,'MEMBER_ROLE_CHANGED',user_id,previous=old,role=data.role)
    await db.commit();return {'id':user_id,'role':data.role}

@router.delete('/team-members/{user_id}')
async def remove_member(user_id:str,db:DbSession):
    who=require('owner')
    if who['user_id']==user_id:raise HTTPException(409,'Ask another owner to remove your membership.')
    await db.execute(update(Workspace).where(Workspace.id==who['workspace_id']).values(name=Workspace.name))
    row=await db.get(Member,(who['workspace_id'],user_id))
    if not row:raise HTTPException(404,'Member not found.')
    if row.role=='owner':
        count=await db.scalar(select(func.count()).select_from(Member).where(Member.space_id==who['workspace_id'],Member.role=='owner'))
        if count<=1:raise HTTPException(409,'Keep at least one workspace owner.')
    await db.delete(row);audit(db,'MEMBER_REMOVED',user_id);await db.commit();return {'message':'Membership removed. Workspace data is retained.'}

@router.post('/team-invitations',status_code=201)
async def invite(data:InviteWrite,db:DbSession):
    who=require('owner');email=Credentials.email_valid(data.email)
    token=secrets.token_urlsafe(32)
    row=Invitation(space_id=who['workspace_id'],email=email,role=data.role,token_hash=digest(token),expires_at=utcnow()+timedelta(days=3))
    db.add(row);await db.flush();audit(db,'INVITATION_CREATED',row.id,email=email,role=data.role);await db.commit()
    return {'id':row.id,'token':token,'expires_at':aware(row.expires_at).isoformat()}

@router.get('/team-invitations')
async def invitations(db:DbSession):
    who=require('owner')
    rows=(await db.execute(select(Invitation).where(Invitation.space_id==who['workspace_id']).order_by(Invitation.expires_at.desc()).limit(100))).scalars().all()
    return [{'id':r.id,'email':r.email,'role':r.role,'expires_at':aware(r.expires_at).isoformat(),'revoked':r.revoked,'accepted':bool(r.accepted_at)} for r in rows]

@router.delete('/team-invitations/{invite_id}')
async def revoke(invite_id:str,db:DbSession):
    who=require('owner');row=await db.get(Invitation,invite_id)
    if not row or row.space_id!=who['workspace_id']:raise HTTPException(404,'Invitation not found.')
    row.revoked=True;audit(db,'INVITATION_REVOKED',row.id);await db.commit();return {'message':'Invitation revoked.'}

@router.post('/auth/accept',status_code=201)
async def accept(data:Accept,db:DbSession,response:Response):
    invitation=(await db.execute(select(Invitation).where(Invitation.token_hash==digest(data.token)).with_for_update())).scalar_one_or_none()
    if not invitation or invitation.revoked or invitation.accepted_at or aware(invitation.expires_at)<=utcnow():raise HTTPException(410,'Invitation expired, used or revoked. Ask for a new invitation.')
    if invitation.email!=data.email:raise HTTPException(403,'Use the email address on the invitation.')
    user=(await db.execute(select(User).where(User.email==data.email))).scalar_one_or_none()
    if user and not await asyncio.to_thread(matches,data.password,user.password_hash):raise HTTPException(401,'Use your existing account password.')
    if user and not user.active:raise HTTPException(403,'Account is inactive.')
    if not user:
        user=User(email=data.email,name=data.name.strip(),password_hash=await asyncio.to_thread(password,data.password));db.add(user);await db.flush()
    old=await db.get(Member,(invitation.space_id,user.id))
    if old:raise HTTPException(409,'Already a member. Sign in instead.')
    # CAS prevents two simultaneous invitation redemptions on SQLite as well.
    won=await db.execute(update(Invitation).where(Invitation.id==invitation.id,Invitation.accepted_at.is_(None),Invitation.revoked.is_(False),Invitation.expires_at>utcnow()).values(accepted_at=utcnow()).execution_options(synchronize_session=False))
    if not won.rowcount:raise HTTPException(409,'Invitation already used.')
    db.add(Member(space_id=invitation.space_id,user_id=user.id,role=invitation.role));await issue(db,user,invitation.space_id,response)
    db.add(AuditRecord(workspace_id=invitation.space_id,event_type='INVITATION_ACCEPTED',operator_id=user.id,resource_id=invitation.id,metadata_json={}))
    await db.commit();return {'id':user.id,'workspace_id':invitation.space_id}

class RequestReview(BaseModel):
    version_id:UUID
    assignee:str=Field(max_length=36)
class Decide(BaseModel):
    decision:Literal['approved','changes_requested']
    reason:str=Field(min_length=3,max_length=5000)
    expected_revision:int=Field(ge=1)
    @field_validator('reason')
    @classmethod
    def reason_valid(cls,value):
        if len(value.strip())<3:raise ValueError('Add decision notes with at least three characters.')
        return value.strip()
class CommentWrite(BaseModel):
    version_id:UUID
    body:str=Field(min_length=1,max_length=5000)
    parent_id:UUID|None=None

async def visible_version(db,vid):
    current()
    row=await db.get(ArtifactVersion,vid)
    if not row:raise HTTPException(404,'Saved version not found.')
    from api.routes.workspaces import context
    await context(db,row.artifact_id,current()['user_id'])
    return row

def review_data(row):
    return {'id':str(row.id),'version_id':str(row.version_id),'artifact_id':str(row.artifact_id),
        'requester':row.requester,'assignee':row.assignee,'content_hash':row.content_hash,
        'status':row.status,'revision':row.revision,'created_at':aware(row.created_at).isoformat()}

@router.post('/team-reviews',status_code=201)
async def request_review(data:RequestReview,db:DbSession):
    who=require('owner','editor');version=await visible_version(db,data.version_id)
    member=await db.get(Member,(who['workspace_id'],data.assignee))
    if not member or member.role not in {'owner','reviewer'}:raise HTTPException(422,'Assign an owner or reviewer in this workspace.')
    pending=(await db.execute(select(ReviewRequest).where(ReviewRequest.version_id==version.id,ReviewRequest.assignee==data.assignee,ReviewRequest.status=='pending'))).scalar_one_or_none()
    if pending:return review_data(pending)
    row=ReviewRequest(version_id=version.id,artifact_id=version.artifact_id,requester=who['user_id'],assignee=data.assignee,content_hash=version.content_hash)
    db.add(row);await db.flush();audit(db,'REVIEW_ASSIGNED',version.artifact_id,version_id=str(version.id),review_id=str(row.id),assignee=data.assignee)
    await db.commit();return review_data(row)

@router.get('/team-reviews')
async def review_inbox(db:DbSession,status:Literal['all','pending','approved','changes_requested']='pending',
                       mine:bool=True,offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100)):
    who=current();stmt=select(ReviewRequest)
    if mine:stmt=stmt.where(ReviewRequest.assignee==who['user_id'])
    if status!='all':stmt=stmt.where(ReviewRequest.status==status)
    total=await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=(await db.execute(stmt.order_by(ReviewRequest.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    items=[]
    for r in rows:
        version=await db.get(ArtifactVersion,r.version_id)
        items.append({**review_data(r),'label':version.label if version else 'Unavailable version'})
    return {'items':items,'total':total}

@router.get('/team-reviews/{review_id}')
async def review_detail(review_id:UUID,db:DbSession):
    current();row=await db.get(ReviewRequest,review_id)
    if not row:raise HTTPException(404,'Review not found.')
    version=await visible_version(db,row.version_id)
    decision=(await db.execute(select(ReviewDecision).where(ReviewDecision.review_id==row.id))).scalar_one_or_none()
    return {**review_data(row),'content':version.content,'label':version.label,
        'decision':{'actor':decision.actor,'reason':decision.reason,'decision':decision.decision,'created_at':aware(decision.created_at).isoformat()} if decision else None}

@router.post('/team-reviews/{review_id}/decision')
async def decide(review_id:UUID,data:Decide,db:DbSession):
    who=require('owner','reviewer');row=await db.get(ReviewRequest,review_id)
    if not row:raise HTTPException(404,'Review not found.')
    if row.assignee!=who['user_id']:raise HTTPException(403,'Only the assigned reviewer can decide. Ask an editor for a new assignment.')
    version=await visible_version(db,row.version_id)
    if version.content_hash!=row.content_hash:raise HTTPException(409,'The version changed. Request a new review.')
    won=await db.execute(update(ReviewRequest).where(ReviewRequest.id==row.id,ReviewRequest.status=='pending',ReviewRequest.revision==data.expected_revision).values(status=data.decision,revision=ReviewRequest.revision+1))
    if not won.rowcount:raise HTTPException(409,'This review already has a decision. Reload to see it.')
    db.add(ReviewDecision(review_id=row.id,version_id=version.id,content_hash=version.content_hash,actor=who['user_id'],decision=data.decision,reason=data.reason.strip()))
    audit(db,'VERSION_'+data.decision.upper(),version.artifact_id,version_id=str(version.id),content_hash=version.content_hash,reason=data.reason.strip())
    await db.commit();return {'status':data.decision,'version_id':str(version.id),'content_hash':version.content_hash}

@router.get('/team-versions/{version_id}/approval')
async def approval(version_id:UUID,db:DbSession):
    row=await visible_version(db,version_id)
    decisions=(await db.execute(select(ReviewDecision).where(ReviewDecision.version_id==row.id).order_by(ReviewDecision.created_at.desc()))).scalars().all()
    return {'version_id':str(row.id),'content_hash':row.content_hash,'status':decisions[0].decision if decisions else 'unapproved'}

@router.get('/team-comments')
async def comments(version_id:UUID,db:DbSession,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100)):
    await visible_version(db,version_id)
    rows=(await db.execute(select(Comment).where(Comment.version_id==version_id).order_by(Comment.created_at).offset(offset).limit(limit))).scalars().all()
    return [{'id':str(r.id),'version_id':str(r.version_id),'parent_id':str(r.parent_id) if r.parent_id else None,
        'actor':r.actor,'body':r.body,'resolved':r.resolved,'created_at':aware(r.created_at).isoformat()} for r in rows]

@router.post('/team-comments',status_code=201)
async def comment(data:CommentWrite,db:DbSession):
    who=require('owner','editor','reviewer');row=await visible_version(db,data.version_id)
    if not data.body.strip():raise HTTPException(422,'Enter a comment.')
    if data.parent_id:
        parent=await db.get(Comment,data.parent_id)
        if not parent or parent.version_id!=row.id or parent.parent_id:raise HTTPException(422,'Choose a root thread on this version.')
    value=Comment(version_id=row.id,actor=who['user_id'],parent_id=data.parent_id,body=data.body.strip())
    db.add(value);await db.flush();audit(db,'COMMENT_ADDED',row.artifact_id,version_id=str(row.id),comment_id=str(value.id));await db.commit();return {'id':str(value.id)}

@router.put('/team-comments/{comment_id}/resolve')
async def resolve_comment(comment_id:UUID,db:DbSession,resolved:bool=True):
    who=require('owner','editor','reviewer');row=await db.get(Comment,comment_id)
    if not row:raise HTTPException(404,'Comment not found.')
    version=await visible_version(db,row.version_id)
    if row.parent_id:raise HTTPException(422,'Resolve the root thread.')
    row.resolved=resolved;audit(db,'COMMENT_RESOLVED' if resolved else 'COMMENT_REOPENED',version.artifact_id,version_id=str(version.id),comment_id=str(row.id))
    await db.commit();return {'resolved':resolved}

@router.get('/team-activity')
async def activity(db:DbSession,q:str=Query('',max_length=120),actor:str=Query('',max_length=36),
                   action:str=Query('',max_length=80),offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100)):
    current();stmt=select(AuditRecord)
    if actor:stmt=stmt.where(AuditRecord.operator_id==actor)
    if action:stmt=stmt.where(AuditRecord.event_type==action)
    if q:
        term='%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        stmt=stmt.where(AuditRecord.event_type.ilike(term,escape='\\')|AuditRecord.resource_id.ilike(term,escape='\\'))
    total=await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows=(await db.execute(stmt.order_by(AuditRecord.created_at.desc(),AuditRecord.id).offset(offset).limit(limit))).scalars().all()
    return {'total':total,'items':[{'id':str(r.id),'actor':r.operator_id,'action':r.event_type,'resource_id':r.resource_id,
        'created_at':aware(r.created_at).isoformat(),'details':r.metadata_json} for r in rows]}
