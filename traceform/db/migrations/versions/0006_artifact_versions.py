"""Add private drafts, immutable versions, and independently billed version tasks."""
from alembic import op
import sqlalchemy as sa

revision = '0006_artifact_versions'
down_revision = '0005_review_evidence'
branch_labels = None
depends_on = None


def upgrade():
    # Existing rows retain their original type. New tables are additive only.
    for table, column in [('generations', 'kind'), ('durable_jobs', 'task_kind')]:
        if column not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column(column, sa.String(), nullable=False, server_default='generation'))
    from db.models import ArtifactDraft, ArtifactVersion, VersionReview, VersionOperation
    for model in [ArtifactDraft, ArtifactVersion, VersionReview, VersionOperation]:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('Restore a backup rather than discard saved work.')
