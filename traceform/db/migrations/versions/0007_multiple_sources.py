"""Versioned document selections, private collections and source analysis."""
from alembic import op
import sqlalchemy as sa

revision = '0007_multiple_sources'
down_revision = '0006_artifact_versions'
branch_labels = None
depends_on = None


def upgrade():
    for table, name in [('generations', 'synthesis'), ('knowledge_extractions', 'conflicts'),
                        ('knowledge_extractions', 'source_documents')]:
        if name not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column(name, sa.JSON(), nullable=True))
    from db.models import SourceCollection, GenerationDocument, SynthesisAnalysis
    for model in [SourceCollection, GenerationDocument, SynthesisAnalysis]:
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('Restore a backup rather than discard document versions and collections.')
