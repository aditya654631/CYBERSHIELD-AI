"""Phase 1: Truthful Bank Actions Lifecycle table

Revision ID: 0006_bank_actions_lifecycle
Revises: 0005_prediction_result_metadata
Create Date: 2026-09-16 02:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_bank_actions_lifecycle"
down_revision = "0005_prediction_result_metadata"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bank_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("action_reference", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id"), nullable=False),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("action_type", sa.String(length=50), server_default="ATM_DISBURSEMENT_HOLD", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="REQUESTED", nullable=False),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("simulation_notes", sa.String(length=255), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("action_notes", sa.Text(), nullable=True),
        sa.Column("provider_reference_id", sa.String(length=100), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bank_actions_id", "bank_actions", ["id"])
    op.create_index("ix_bank_actions_action_reference", "bank_actions", ["action_reference"], unique=True)
    op.create_index("ix_bank_actions_idempotency_key", "bank_actions", ["idempotency_key"], unique=True)
    op.create_index("ix_bank_actions_complaint_id", "bank_actions", ["complaint_id"])
    op.create_index("ix_bank_actions_alert_id", "bank_actions", ["alert_id"])
    op.create_index("ix_bank_actions_status", "bank_actions", ["status"])


def downgrade():
    op.drop_index("ix_bank_actions_status", table_name="bank_actions")
    op.drop_index("ix_bank_actions_alert_id", table_name="bank_actions")
    op.drop_index("ix_bank_actions_complaint_id", table_name="bank_actions")
    op.drop_index("ix_bank_actions_idempotency_key", table_name="bank_actions")
    op.drop_index("ix_bank_actions_action_reference", table_name="bank_actions")
    op.drop_index("ix_bank_actions_id", table_name="bank_actions")
    op.drop_table("bank_actions")
