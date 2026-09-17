"""Phase 5: Immutable Prediction Snapshots Table

Revision ID: 0008_prediction_snapshots
Revises: 0007_phase2_indexes_and_idempotency
Create Date: 2026-09-16 19:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "0008_prediction_snapshots"
down_revision = "0007_phase2_indexes_and_idempotency"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    tables = set(insp.get_table_names())

    if "prediction_snapshots" not in tables:
        op.create_table(
            "prediction_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("prediction_id", sa.Integer(), sa.ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("model_version", sa.String(length=100), nullable=False),
            sa.Column("feature_schema_version", sa.String(length=50), nullable=False),
            sa.Column("feature_schema_hash", sa.String(length=64), nullable=True),
            sa.Column("model_hash", sa.String(length=64), nullable=True),
            sa.Column("calibrator_hash", sa.String(length=64), nullable=True),
            sa.Column("snapshot_data", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # Ensure indexes exist safely
    existing_indexes = set()
    try:
        existing_indexes = {ix["name"] for ix in insp.get_indexes("prediction_snapshots")}
    except Exception:
        pass

    if "ix_prediction_snapshots_id" not in existing_indexes:
        op.create_index("ix_prediction_snapshots_id", "prediction_snapshots", ["id"], unique=False)
    if "ix_prediction_snapshots_prediction_id" not in existing_indexes:
        op.create_index("ix_prediction_snapshots_prediction_id", "prediction_snapshots", ["prediction_id"], unique=True)
    if "ix_prediction_snapshots_complaint_id" not in existing_indexes:
        op.create_index("ix_prediction_snapshots_complaint_id", "prediction_snapshots", ["complaint_id"], unique=False)
    if "ix_prediction_snapshots_created_at" not in existing_indexes:
        op.create_index("ix_prediction_snapshots_created_at", "prediction_snapshots", ["created_at"], unique=False)


def downgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    tables = set(insp.get_table_names())

    if "prediction_snapshots" in tables:
        try:
            indexes = {ix["name"] for ix in insp.get_indexes("prediction_snapshots")}
        except Exception:
            indexes = set()

        for ix_name in [
            "ix_prediction_snapshots_created_at",
            "ix_prediction_snapshots_complaint_id",
            "ix_prediction_snapshots_prediction_id",
            "ix_prediction_snapshots_id"
        ]:
            if ix_name in indexes:
                try:
                    op.drop_index(ix_name, table_name="prediction_snapshots")
                except Exception:
                    pass

        op.drop_table("prediction_snapshots")
