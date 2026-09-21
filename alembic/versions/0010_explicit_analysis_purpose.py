"""Add analysis_purpose column to predictions

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-20

Replaces the "within 5 minutes of created_at" heuristic with an explicit persisted field.
  - 'OPERATIONAL': live analysis (analysis_as_of IS NULL or explicit purpose set at ingestion)
  - 'HISTORICAL_REPLAY': point-in-time replay with an explicit analysis_as_of cutoff

Existing rows are backfilled deterministically:
  - analysis_as_of IS NULL     -> 'OPERATIONAL'
  - analysis_as_of IS NOT NULL -> 'HISTORICAL_REPLAY'
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "0010_explicit_analysis_purpose"
down_revision = "0009_phase2_causal_transactions"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)

    def get_column_names(table_name):
        try:
            return {c["name"] for c in insp.get_columns(table_name)}
        except Exception:
            return set()

    pred_cols = get_column_names("predictions")

    # Add analysis_purpose as nullable VARCHAR(50)
    if "analysis_purpose" not in pred_cols:
        with op.batch_alter_table("predictions", schema=None) as batch_op:
            batch_op.add_column(sa.Column(
                "analysis_purpose",
                sa.String(length=50),
                nullable=True,
                server_default=None,
            ))

    # Deterministic backfill: classify existing rows by analysis_as_of presence
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE predictions SET analysis_purpose = 'OPERATIONAL' WHERE analysis_as_of IS NULL AND analysis_purpose IS NULL"
    ))
    conn.execute(sa.text(
        "UPDATE predictions SET analysis_purpose = 'HISTORICAL_REPLAY' WHERE analysis_as_of IS NOT NULL AND analysis_purpose IS NULL"
    ))


def downgrade():
    with op.batch_alter_table("predictions", schema=None) as batch_op:
        batch_op.drop_column("analysis_purpose")
