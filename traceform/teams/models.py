from sqlalchemy import Column,String,DateTime,Boolean,Integer,Text,ForeignKey,UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from db.models import Base,_event_time
from uuid import uuid4

class User(Base):
    __tablename__='team_users'
    id=Column(String(36),primary_key=True,default=lambda:str(uuid4()))
    email=Column(String(254),unique=True,nullable=False)
    name=Column(String(100),nullable=False)
    password_hash=Column(String,nullable=False)
    active=Column(Boolean,nullable=False,default=True)
    created_at=Column(DateTime(timezone=True),default=_event_time,nullable=False)

class Workspace(Base):
    __tablename__='team_workspaces'
    id=Column(String(36),primary_key=True,default=lambda:str(uuid4()))
    name=Column(String(100),nullable=False)
    created_at=Column(DateTime(timezone=True),default=_event_time,nullable=False)

class Member(Base):
    __tablename__='team_members'
    space_id=Column(String(36),ForeignKey('team_workspaces.id'),primary_key=True)
    user_id=Column(String(36),ForeignKey('team_users.id'),primary_key=True)
    role=Column(String(12),nullable=False)

class SessionToken(Base):
    __tablename__='team_sessions'
    token_hash=Column(String(64),primary_key=True)
    user_id=Column(String(36),ForeignKey('team_users.id'),nullable=False)
    space_id=Column(String(36),ForeignKey('team_workspaces.id'),nullable=False)
    expires_at=Column(DateTime(timezone=True),nullable=False)

class Invitation(Base):
    __tablename__='team_invitations'
    id=Column(String(36),primary_key=True,default=lambda:str(uuid4()))
    space_id=Column(String(36),ForeignKey('team_workspaces.id'),nullable=False)
    email=Column(String(254),nullable=False)
    role=Column(String(12),nullable=False)
    token_hash=Column(String(64),unique=True,nullable=False)
    expires_at=Column(DateTime(timezone=True),nullable=False)
    accepted_at=Column(DateTime(timezone=True),nullable=True)
    revoked=Column(Boolean,nullable=False,default=False)

class ReviewRequest(Base):
    __tablename__='team_reviews'
    id=Column(UUID(as_uuid=True),primary_key=True,default=uuid4)
    version_id=Column(UUID(as_uuid=True),ForeignKey('artifact_versions.id'),nullable=False)
    artifact_id=Column(UUID(as_uuid=True),ForeignKey('artifacts.id'),nullable=False)
    requester=Column(String(36),nullable=False)
    assignee=Column(String(36),nullable=False)
    content_hash=Column(String(64),nullable=False)
    status=Column(String(20),nullable=False,default='pending')
    revision=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime(timezone=True),default=_event_time,nullable=False)

class ReviewDecision(Base):
    __tablename__='team_decisions'
    id=Column(UUID(as_uuid=True),primary_key=True,default=uuid4)
    review_id=Column(UUID(as_uuid=True),ForeignKey('team_reviews.id'),nullable=False,unique=True)
    version_id=Column(UUID(as_uuid=True),ForeignKey('artifact_versions.id'),nullable=False)
    content_hash=Column(String(64),nullable=False)
    actor=Column(String(36),nullable=False)
    decision=Column(String(20),nullable=False)
    reason=Column(Text,nullable=False)
    created_at=Column(DateTime(timezone=True),default=_event_time,nullable=False)

class Comment(Base):
    __tablename__='team_comments'
    id=Column(UUID(as_uuid=True),primary_key=True,default=uuid4)
    version_id=Column(UUID(as_uuid=True),ForeignKey('artifact_versions.id'),nullable=False)
    actor=Column(String(36),nullable=False)
    parent_id=Column(UUID(as_uuid=True),ForeignKey('team_comments.id'),nullable=True)
    body=Column(Text,nullable=False)
    resolved=Column(Boolean,nullable=False,default=False)
    created_at=Column(DateTime(timezone=True),default=_event_time,nullable=False)
