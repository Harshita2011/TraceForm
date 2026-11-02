"""Add cancelled lifecycle state to the PostgreSQL enum; SQLite uses unbounded values."""
from alembic import op
revision = "0003_cancelled_status"
down_revision = "0002_durable_jobs"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE generationstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade():
    raise RuntimeError("Removing a lifecycle state requires a reviewed data migration")
