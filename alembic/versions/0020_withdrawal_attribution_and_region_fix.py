"""Add withdrawal attribution columns and correct non-Delhi region contamination.

Revision ID: 0020_withdrawal_attribution_and_region_fix
Revises: 0019_phase12_geography_catalog_and_regions

Phase 13: Withdrawal Case-Attribution and Region Fix.
Introduces:
  1. `complaint_id` FK column to `withdrawals` table (ForeignKey('complaints.id', ondelete='SET NULL')).
  2. `withdrawal_ref` unique column to `withdrawals` table (String(100)).
  3. Regional boundary cleanup: ensures any non-Delhi clusters or ATMs do not retain region_id='delhi'.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0020_withdrawal_attribution_and_region_fix"
down_revision = "0019_phase12_geography_catalog_and_regions"
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

    wdl_cols = get_column_names("withdrawals")

    # 1. Add columns to withdrawals using batch mode
    with op.batch_alter_table("withdrawals", schema=None) as batch_op:
        if "complaint_id" not in wdl_cols:
            batch_op.add_column(
                sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id", ondelete="SET NULL", name="fk_withdrawals_complaint_id"), nullable=True)
            )
            try:
                batch_op.create_index("ix_withdrawals_complaint_id", ["complaint_id"])
            except Exception:
                pass

        if "withdrawal_ref" not in wdl_cols:
            batch_op.add_column(
                sa.Column("withdrawal_ref", sa.String(100), nullable=True)
            )
            try:
                batch_op.create_index("ix_withdrawals_withdrawal_ref", ["withdrawal_ref"], unique=True)
            except Exception:
                pass

    # 2. Clean up non-Delhi region_id contamination
    cluster_cols = get_column_names("location_clusters")
    if "region_id" in cluster_cols:
        op.execute(
            """
            UPDATE location_clusters
            SET region_id = NULL
            WHERE region_id = 'delhi'
              AND LOWER(COALESCE(state, '')) NOT IN ('delhi', 'new delhi');
            """
        )

    atm_cols = get_column_names("atm_locations")
    if "region_id" in atm_cols:
        op.execute(
            """
            UPDATE atm_locations
            SET region_id = NULL
            WHERE region_id = 'delhi'
              AND LOWER(COALESCE(state, '')) NOT IN ('delhi', 'new delhi');
            """
        )


def downgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)

    def get_column_names(table_name):
        try:
            return {c["name"] for c in insp.get_columns(table_name)}
        except Exception:
            return set()

    wdl_cols = get_column_names("withdrawals")
    with op.batch_alter_table("withdrawals", schema=None) as batch_op:
        if "withdrawal_ref" in wdl_cols:
            try:
                batch_op.drop_index("ix_withdrawals_withdrawal_ref")
            except Exception:
                pass
            batch_op.drop_column("withdrawal_ref")

        if "complaint_id" in wdl_cols:
            try:
                batch_op.drop_index("ix_withdrawals_complaint_id")
            except Exception:
                pass
            batch_op.drop_column("complaint_id")
