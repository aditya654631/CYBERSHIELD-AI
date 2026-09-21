"""Add durable notification outbox and alert lifecycle tracking fields.

Revision ID: 0014_phase5_durable_alerts_and_outbox
Revises: 0013_phase3_authorization_scope_ids

Phase 5: Persistent Transactional Notification Outbox.
Ensures alert creation, acknowledgement, escalation, expiry, and supersession
events commit atomically in the database and are durably dispatched to recipients.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0014_phase5_durable_alerts_and_outbox"
down_revision = "0013_phase3_authorization_scope_ids"
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

    def get_existing_indexes(table_name):
        try:
            return {ix["name"] for ix in insp.get_indexes(table_name)}
        except Exception:
            return set()

    alert_cols = get_column_names("alerts")
    alert_ixs = get_existing_indexes("alerts")

    # 1. Add supersession and expiry fields to alerts
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        if "superseded_by_prediction_id" not in alert_cols:
            batch_op.add_column(sa.Column("superseded_by_prediction_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_alerts_superseded_by_prediction_id", "predictions",
                ["superseded_by_prediction_id"], ["id"], ondelete="SET NULL"
            )
        if "superseded_at" not in alert_cols:
            batch_op.add_column(sa.Column("superseded_at", sa.DateTime(), nullable=True))
        if "expires_at" not in alert_cols:
            batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))
        if "ix_alerts_expires_at" not in alert_ixs:
            batch_op.create_index("ix_alerts_expires_at", ["expires_at"])

    # 2. Create notification_outbox table if not exists
    if not insp.has_table("notification_outbox"):
        op.create_table(
            "notification_outbox",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("alert_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("prediction_id", sa.Integer(), nullable=True),
            sa.Column("prediction_version", sa.Integer(), nullable=True),
            sa.Column("channel", sa.String(50), server_default="DASHBOARD_WEBSOCKET", nullable=False),
            sa.Column("recipient_role", sa.String(50), nullable=True),
            sa.Column("recipient_user_id", sa.Integer(), nullable=True),
            sa.Column("recipient_organization_id", sa.Integer(), nullable=True),
            sa.Column("recipient_state", sa.String(100), nullable=True),
            sa.Column("recipient_district", sa.String(100), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(50), server_default="QUEUED", nullable=False),
            sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
            sa.Column("next_retry_at", sa.DateTime(), nullable=True),
            sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("worker_id", sa.String(100), nullable=True),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
            sa.Column("delivered_at", sa.DateTime(), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
            sa.Column("acknowledged_by", sa.String(255), nullable=True),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], name="fk_notification_outbox_alert_id", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], name="fk_notification_outbox_prediction_id", ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], name="fk_notification_outbox_recipient_user_id", ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["recipient_organization_id"], ["organizations.id"], name="fk_notification_outbox_recipient_org_id", ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key", name="uq_notification_outbox_idempotency_key")
        )

        with op.batch_alter_table("notification_outbox", schema=None) as batch_op:
            batch_op.create_index("ix_notification_outbox_alert_id", ["alert_id"])
            batch_op.create_index("ix_notification_outbox_event_type", ["event_type"])
            batch_op.create_index("ix_notification_outbox_prediction_id", ["prediction_id"])
            batch_op.create_index("ix_notification_outbox_channel", ["channel"])
            batch_op.create_index("ix_notification_outbox_status", ["status"])
            batch_op.create_index("ix_notification_outbox_next_retry_at", ["next_retry_at"])
            batch_op.create_index("ix_notification_outbox_lease_expires_at", ["lease_expires_at"])
            batch_op.create_index("ix_notification_outbox_created_at", ["created_at"])
            batch_op.create_index("ix_outbox_status_retry", ["status", "next_retry_at"])
            batch_op.create_index("ix_outbox_lease", ["status", "lease_expires_at"])


def downgrade():
    op.drop_table("notification_outbox")

    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_index("ix_alerts_expires_at")
        batch_op.drop_constraint("fk_alerts_superseded_by_prediction_id", type_="foreignkey")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("superseded_at")
        batch_op.drop_column("superseded_by_prediction_id")
