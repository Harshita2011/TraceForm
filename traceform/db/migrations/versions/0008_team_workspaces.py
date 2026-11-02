"""Add authenticated workspaces without moving or discarding existing business data."""
from alembic import op
import sqlalchemy as sa
revision='0008_team_workspaces'
down_revision='0007_multiple_sources'
branch_labels=None
depends_on=None

def upgrade():
    from db.models import Base
    import teams.models
    bind=op.get_bind()
    existing=set(sa.inspect(bind).get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            table.create(bind,checkfirst=True)
        elif 'workspace_id' not in {c['name'] for c in sa.inspect(bind).get_columns(table.name)}:
            op.add_column(table.name,sa.Column('workspace_id',sa.String(36),nullable=False,server_default='legacy'))
            op.create_index('ix_'+table.name+'_workspace_id',table.name,['workspace_id'])

def downgrade():raise RuntimeError('Restore a backup instead of deleting workspace identities and approvals.')
