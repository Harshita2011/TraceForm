"""Immutable datasets, durable executions and per-case measurement evidence."""
from alembic import op
revision='0009_measured_evaluations'
down_revision='0008_team_workspaces'
branch_labels=None
depends_on=None
def upgrade():
    from eval.models import BenchmarkDataset,BenchmarkCase,BenchmarkExecution,BenchmarkOutcome
    for model in [BenchmarkDataset,BenchmarkCase,BenchmarkExecution,BenchmarkOutcome]:
        model.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():raise RuntimeError('Restore a backup instead of discarding evaluation evidence.')
