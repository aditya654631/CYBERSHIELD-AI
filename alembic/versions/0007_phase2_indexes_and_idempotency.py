"""Phase 2: Performance Indexes and Workflow Idempotency

Revision ID: 0007_phase2_indexes_and_idempotency
Revises: 0006_bank_actions_lifecycle
Create Date: 2026-09-16 11:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "0007_phase2_indexes_and_idempotency"
down_revision = "0006_bank_actions_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)

    def get_existing_indexes(table_name):
        try:
            return {ix["name"] for ix in insp.get_indexes(table_name)}
        except Exception:
            return set()

    # 1. Complaint jurisdiction and temporal indexes
    comp_indexes = get_existing_indexes("complaints")
    if "ix_complaints_state_district" not in comp_indexes:
        op.create_index(
            "ix_complaints_state_district",
            "complaints",
            ["state", "district"],
            unique=False
        )
    if "ix_complaints_reported_at" not in comp_indexes:
        op.create_index(
            "ix_complaints_reported_at",
            "complaints",
            ["reported_at"],
            unique=False
        )

    # 2. Alert composite index for workflow queries
    alert_indexes = get_existing_indexes("alerts")
    if "ix_alerts_comp_pred_status" not in alert_indexes:
        op.create_index(
            "ix_alerts_comp_pred_status",
            "alerts",
            ["complaint_id", "prediction_id", "status"],
            unique=False
        )

    # 3. Transaction hop depth & path index
    tx_indexes = get_existing_indexes("transactions")
    if "ix_transactions_comp_hop" not in tx_indexes:
        op.create_index(
            "ix_transactions_comp_hop",
            "transactions",
            ["complaint_id", "hop_number"],
            unique=False
        )

    # 4. Bank actions complaint & status index
    bank_indexes = get_existing_indexes("bank_actions")
    if "ix_bank_actions_comp_status" not in bank_indexes:
        op.create_index(
            "ix_bank_actions_comp_status",
            "bank_actions",
            ["complaint_id", "status"],
            unique=False
        )

    # 5. Audit log officer & timeline query index
    audit_indexes = get_existing_indexes("audit_logs")
    if "ix_audit_logs_user_created_at" not in audit_indexes:
        op.create_index(
            "ix_audit_logs_user_created_at",
            "audit_logs",
            ["user_id", "created_at"],
            unique=False
        )


def downgrade():
    op.drop_index("ix_audit_logs_user_created_at", table_name="audit_logs")
    op.drop_index("ix_bank_actions_comp_status", table_name="bank_actions")
    op.drop_index("ix_transactions_comp_hop", table_name="transactions")
    op.drop_index("ix_alerts_comp_pred_status", table_name="alerts")
    op.drop_index("ix_complaints_reported_at", table_name="complaints")
    op.drop_index("ix_complaints_state_district", table_name="complaints")
