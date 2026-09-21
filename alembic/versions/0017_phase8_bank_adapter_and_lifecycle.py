"""Add Phase 8 bank adapter lifecycle, environment, and financial intervention fields.

Revision ID: 0017_phase8_bank_adapter_and_lifecycle
Revises: 0016_phase7_cross_state_handoff

Phase 8: Bank Adapter & Truthful External Action Lifecycle.
Adds environment separation (SIMULATED, SANDBOX, LIVE), target account attributes,
requested vs held amounts, reviewer tracking, hold/release timestamps,
verified callback evidence, and status history tracking.
"""
from alembic import op
import sqlalchemy as sa


revision = "0017_phase8_bank_adapter_and_lifecycle"
down_revision = "0016_phase7_cross_state_handoff"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("bank_actions") as batch_op:
        batch_op.add_column(sa.Column("environment", sa.String(50), server_default="SIMULATED", nullable=False))
        batch_op.add_column(sa.Column("target_account_number", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("target_ifsc", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("requested_amount", sa.Numeric(14, 2), nullable=True))
        batch_op.add_column(sa.Column("held_amount", sa.Numeric(14, 2), server_default="0.0", nullable=False))
        batch_op.add_column(sa.Column("currency", sa.String(10), server_default="INR", nullable=False))
        batch_op.add_column(sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("held_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("released_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("release_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("callback_evidence", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("status_history", sa.JSON(), nullable=True))
        batch_op.create_foreign_key("fk_bank_actions_reviewed_by_user", "users", ["reviewed_by_user_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_bank_actions_environment", ["environment"], unique=False)


def downgrade():
    with op.batch_alter_table("bank_actions") as batch_op:
        batch_op.drop_index("ix_bank_actions_environment")
        batch_op.drop_constraint("fk_bank_actions_reviewed_by_user", type_="foreignkey")
        batch_op.drop_column("status_history")
        batch_op.drop_column("callback_evidence")
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("release_reason")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("released_at")
        batch_op.drop_column("held_at")
        batch_op.drop_column("reviewed_by_user_id")
        batch_op.drop_column("currency")
        batch_op.drop_column("held_amount")
        batch_op.drop_column("requested_amount")
        batch_op.drop_column("target_ifsc")
        batch_op.drop_column("target_account_number")
        batch_op.drop_column("environment")
