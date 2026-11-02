"""Versioned human-adjudicated datasets and durable, reproducible measurements."""
from sqlalchemy import Column,String,Text,ForeignKey,UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID,JSON
from uuid import uuid4
from db.models import Base,_event_time
from sqlalchemy import DateTime

class BenchmarkDataset(Base):
    __tablename__='benchmark_datasets'
    id=Column(UUID(as_uuid=True),primary_key=True,default=uuid4)
    name=Column(String(100),nullable=False)
    version=Column(String(40),nullable=False)
    notes=Column(Text,nullable=False,default='')
    provenance=Column(String(30),nullable=False,default='human_annotated')
    creator=Column(String,nullable=False)
    digest=Column(String(64),nullable=False)
    created_at=Column(DateTime(timezone=True),default=_event_time,nullable=False)
    __table_args__=(UniqueConstraint('workspace_id','name','version',name='uq_benchmark_dataset_version'),)

class BenchmarkCase(Base):
    __tablename__='benchmark_cases'
    id=Column(UUID(as_uuid=True),primary_key=True,default=uuid4)
    dataset_id=Column(UUID(as_uuid=True),ForeignKey('benchmark_datasets.id'),nullable=False)
    version_id=Column(UUID(as_uuid=True),ForeignKey('artifact_versions.id'),nullable=False)
    title=Column(String(150),nullable=False)
    snapshot=Column(JSON,nullable=False)
    annotations=Column(JSON,nullable=False)

class BenchmarkExecution(Base):
    __tablename__='benchmark_executions'
    generation_id=Column(UUID(as_uuid=True),ForeignKey('generations.id'),primary_key=True)
    dataset_id=Column(UUID(as_uuid=True),ForeignKey('benchmark_datasets.id'),nullable=False)
    measurement_version=Column(String(60),nullable=False)
    creator=Column(String,nullable=False)
    metrics=Column(JSON,nullable=True)
    created_at=Column(DateTime(timezone=True),default=_event_time,nullable=False)

class BenchmarkOutcome(Base):
    __tablename__='benchmark_outcomes'
    id=Column(UUID(as_uuid=True),primary_key=True,default=uuid4)
    execution_id=Column(UUID(as_uuid=True),ForeignKey('benchmark_executions.generation_id'),nullable=False)
    case_id=Column(UUID(as_uuid=True),ForeignKey('benchmark_cases.id'),nullable=False)
    status=Column(String(20),nullable=False)
    counts=Column(JSON,nullable=False)
    message=Column(Text,nullable=True)
    created_at=Column(DateTime(timezone=True),default=_event_time,nullable=False)
    __table_args__=(UniqueConstraint('execution_id','case_id',name='uq_benchmark_outcome'),)
