"""Phase 4: Add location_type, bank_code, source, source_reference, source_updated_at, is_active columns to atm_locations table.

Revision ID: 0022_atm_csp_context
Revises: 0021_intervention_orchestrator
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0022_atm_csp_context"
down_revision = "0021_intervention_orchestrator"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    columns = {c["name"] for c in insp.get_columns("atm_locations")}

    if "location_type" not in columns:
        op.add_column("atm_locations", sa.Column("location_type", sa.String(length=50), nullable=False, server_default="ATM"))
    if "bank_code" not in columns:
        op.add_column("atm_locations", sa.Column("bank_code", sa.String(length=50), nullable=True))
    if "source" not in columns:
        op.add_column("atm_locations", sa.Column("source", sa.String(length=100), nullable=False, server_default="INTERNAL_CONTROLLED_DATA"))
    if "source_reference" not in columns:
        op.add_column("atm_locations", sa.Column("source_reference", sa.String(length=255), nullable=True))
    if "source_updated_at" not in columns:
        op.add_column("atm_locations", sa.Column("source_updated_at", sa.DateTime(), nullable=True))
    if "is_active" not in columns:
        op.add_column("atm_locations", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"))


def downgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    columns = {c["name"] for c in insp.get_columns("atm_locations")}

    if "is_active" in columns:
        op.drop_column("atm_locations", "is_active")
    if "source_updated_at" in columns:
        op.drop_column("atm_locations", "source_updated_at")
    if "source_reference" in columns:
        op.drop_column("atm_locations", "source_reference")
    if "source" in columns:
        op.drop_column("atm_locations", "source")
    if "bank_code" in columns:
        op.drop_column("atm_locations", "bank_code")
    if "location_type" in columns:
        op.drop_column("atm_locations", "location_type")
