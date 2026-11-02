"""Bind compliance decisions to the reviewed content without changing old outcomes."""
from alembic import op
import sqlalchemy as sa

revision = '0005_review_evidence'
down_revision = '0004_source_library'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('compliance_overrides')}
    if 'content_version' not in columns:
        op.add_column('compliance_overrides', sa.Column('content_version', sa.String(64), nullable=True))


def downgrade():
    raise RuntimeError('Restore a backup rather than discard recorded review decisions.')
