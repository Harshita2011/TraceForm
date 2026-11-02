"""Source-library metadata and private durable creation presets; additive upgrade."""
from alembic import op
import sqlalchemy as sa
revision = '0004_source_library'
down_revision = '0003_cancelled_status'
branch_labels = None
depends_on = None

def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('sources')}
    for column in [sa.Column('filename',sa.String()), sa.Column('content_type',sa.String()),
                   sa.Column('extraction_method',sa.String()),
                   sa.Column('was_truncated',sa.Boolean(),nullable=False,server_default=sa.false()),
                   sa.Column('deleted_at',sa.DateTime(timezone=True))]:
        if column.name not in columns: op.add_column('sources',column)
    if not sa.inspect(op.get_bind()).has_table('creation_presets'):
        op.create_table('creation_presets',sa.Column('id',sa.UUID(),primary_key=True),
            sa.Column('owner',sa.String(),nullable=False),sa.Column('name',sa.String(),nullable=False),
            sa.Column('settings',sa.JSON(),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
        op.create_index('ix_creation_presets_owner','creation_presets',['owner'])

def downgrade():
    raise RuntimeError('Restore a backup rather than discard sources or saved presets.')
