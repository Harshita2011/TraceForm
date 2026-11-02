import asyncio,hashlib,hmac,os,secrets
from datetime import timedelta
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import select
from api.dependencies import get_db
from teams.models import User,Member,SessionToken
from teams.scope import workspace,identity,actor
from orchestrator.runtime import utcnow,aware

COOKIE='traceform_session'
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def password(value,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(value.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def matches(value,stored):return hmac.compare_digest(password(value,stored.split(':')[0]),stored)
DUMMY_PASSWORD_HASH=password('dummy-nonaccount-credential')

async def issue(db,user,space,response):
    token=secrets.token_urlsafe(32)
    db.add(SessionToken(token_hash=digest(token),user_id=user.id,space_id=space,expires_at=utcnow()+timedelta(hours=8)))
    response.set_cookie(COOKIE,token,max_age=28800,httponly=True,samesite='strict',
                        secure=os.getenv('APP_ENV')=='production',path='/')

class WorkspaceBoundary(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        # Auth endpoints independently validate their session/invitation/setup authority.
        token=request.cookies.get(COOKIE)
        bearer=request.headers.get('authorization','')
        if bearer.startswith('Bearer '):token=bearer[7:]
        ctx=None
        if token:
            dependency=request.app.dependency_overrides.get(get_db,get_db)
            generator=dependency()
            try:
                db=await anext(generator)
                session=await db.get(SessionToken,digest(token))
                user=await db.get(User,session.user_id) if session else None
                member=await db.get(Member,(session.space_id,user.id)) if user and user.active else None
                if session and member and aware(session.expires_at)>utcnow():
                    ctx={'user_id':user.id,'email':user.email,'name':user.name,'role':member.role,'workspace_id':session.space_id}
            finally:await generator.aclose()
            if not ctx and request.url.path not in {'/api/v1/auth/login','/api/v1/auth/logout','/api/v1/auth/status','/api/v1/auth/accept','/api/v1/auth/setup'}:
                return JSONResponse({'detail':'Your session expired. Sign in again.'},status_code=401)
        if request.method not in {'GET','HEAD','OPTIONS'}:
            origin=request.headers.get('origin')
            allowed={x.strip() for x in os.getenv('TRACEFORM_WEB_ORIGINS','http://localhost:3000,http://127.0.0.1:3000').split(',')}
            if origin and origin not in allowed:return JSONResponse({'detail':'Request origin denied.'},status_code=403)
        if ctx and request.method not in {'GET','HEAD','OPTIONS'}:
            path=request.url.path
            auth_action=path.startswith('/api/v1/auth/')
            comment_action='/team-comments' in path
            decision_action='/team-reviews/' in path and path.endswith('/decision')
            if not auth_action and (ctx['role']=='viewer' or ctx['role']=='reviewer' and not(comment_action or decision_action)):
                return JSONResponse({'detail':'Your workspace role is read-only for this action.'},status_code=403)
        t=workspace.set(None if request.url.path=='/api/v1/auth/accept' else ctx['workspace_id'] if ctx else 'legacy');u=identity.set(ctx)
        from security.api_keys import resolve_operator_from_key
        key_context=resolve_operator_from_key(request.headers.get('x-api-key'))
        a=actor.set(ctx['user_id'] if ctx else key_context.operator_id if key_context else 'dev-no-auth')
        try:return await call_next(request)
        finally:actor.reset(a);identity.reset(u);workspace.reset(t)

def current():
    value=identity.get()
    if not value:raise HTTPException(401,'Sign in to use team features.')
    return value
def require(*roles):
    value=current()
    if value['role'] not in roles:raise HTTPException(403,'Your workspace role cannot perform this action.')
    return value
