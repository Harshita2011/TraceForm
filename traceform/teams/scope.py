"""Central tenant boundary for ORM queries, writes, joins and independent worker tasks."""
from contextvars import ContextVar
from sqlalchemy import event,inspect
from sqlalchemy.orm import Session,with_loader_criteria
from db.models import Base

workspace=ContextVar('workspace',default=None)
identity=ContextVar('team_identity',default=None)
actor=ContextVar('audit_actor',default='system')
GLOBAL={'team_users','team_workspaces','team_members','team_sessions','team_invitations',
        'provider_configurations','active_provider','worker_states','api_keys'}

def team():return identity.get() is not None

@event.listens_for(Session,'do_orm_execute')
def isolate(state):
    space=workspace.get()
    if space is None:return # trusted worker admission / migrations, never an authenticated request
    for mapper in Base.registry.mappers:
        model=mapper.class_
        if model.__tablename__ not in GLOBAL:
            state.statement=state.statement.options(with_loader_criteria(model,model.workspace_id==space,include_aliases=True))

@event.listens_for(Session,'before_flush')
def stamp(session,context,instances):
    space=workspace.get()
    for obj in session.new:
        if isinstance(obj,Base) and obj.__tablename__ not in GLOBAL:
            if space and obj.workspace_id not in (None,space):raise ValueError('Cross-workspace write denied.')
            obj.workspace_id=space or obj.workspace_id or 'legacy'
    for obj in session.dirty|session.deleted:
        if isinstance(obj,Base) and obj.__tablename__ not in GLOBAL:
            if space and obj.workspace_id!=space:raise ValueError('Cross-workspace write denied.')
            if inspect(obj).attrs.workspace_id.history.has_changes():raise ValueError('Workspace ownership is immutable.')
            if obj.__tablename__ in {'team_decisions','audit_records','artifact_versions','benchmark_datasets','benchmark_cases','benchmark_outcomes'}:
                raise ValueError('This saved record is immutable.')
    from db.models import Source,Generation,AuditRecord
    from uuid import uuid4
    for obj in list(session.new|session.dirty):
        if not isinstance(obj,(Source,Generation)):continue
        state=inspect(obj)
        new=obj in session.new
        fields=['sensitivity','deleted_at'] if isinstance(obj,Source) else ['status']
        changed=[name for name in fields if state.attrs[name].history.has_changes()]
        if new or changed:
            if obj.id is None:obj.id=uuid4()
            who=identity.get()
            session.add(AuditRecord(workspace_id=space or obj.workspace_id or 'legacy',
                event_type=('SOURCE' if isinstance(obj,Source) else 'GENERATION')+('_CREATED' if new else '_UPDATED'),
                operator_id=who['user_id'] if who else actor.get(),resource_id=str(obj.id),metadata_json={'fields':changed}))
