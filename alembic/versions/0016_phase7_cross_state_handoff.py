"""Add case handoffs table for controlled cross-state and cross-district case assignments.

Revision ID: 0016_phase7_cross_state_handoff
Revises: 0015_phase6_evidence_and_reports

Phase 7: Controlled Cross-State / Cross-District Handoff & Explicit Assignment.
Enforces explicit, auditable handoffs between case-owning LEA and action-taking
destination LEAs across state/district borders with scoped, time-bounded access.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0016_phase7_cross_state_handoff"
down_revision = "0015_phase6_evidence_and_reports"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)

    if not insp.has_table("case_handoffs"):
        op.create_table(
            "case_handoffs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("complaint_id", sa.Integer(), nullable=False),
            sa.Column("prediction_id", sa.Integer(), nullable=True),
            sa.Column("prediction_version", sa.Integer(), nullable=True),
            sa.Column("origin_organization_id", sa.Integer(), nullable=False),
            sa.Column("destination_organization_id", sa.Integer(), nullable=False),
            sa.Column("target_state", sa.String(100), nullable=False),
            sa.Column("target_district", sa.String(100), nullable=False),
            sa.Column("purpose", sa.String(100), nullable=False),
            sa.Column("evidence_scope", sa.String(50), server_default="METADATA_ONLY", nullable=False),
            sa.Column("shared_evidence_ids", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(50), server_default="REQUESTED", nullable=False),
            sa.Column("initiator_user_id", sa.Integer(), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("cancellation_reason", sa.Text(), nullable=True),
            sa.Column("completed_notes", sa.Text(), nullable=True),
            sa.Column("acknowledgement_deadline", sa.DateTime(), nullable=False),
            sa.Column("accepted_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["origin_organization_id"], ["organizations.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["destination_organization_id"], ["organizations.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["initiator_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_case_handoffs_id", "case_handoffs", ["id"])
        op.create_index("ix_case_handoffs_complaint_id", "case_handoffs", ["complaint_id"])
        op.create_index("ix_case_handoffs_origin_organization_id", "case_handoffs", ["origin_organization_id"])
        op.create_index("ix_case_handoffs_destination_organization_id", "case_handoffs", ["destination_organization_id"])
        op.create_index("ix_case_handoffs_initiator_user_id", "case_handoffs", ["initiator_user_id"])
        op.create_index("ix_case_handoffs_recipient_user_id", "case_handoffs", ["recipient_user_id"])
        op.create_index("ix_case_handoffs_status", "case_handoffs", ["status"])
        op.create_index("ix_case_handoffs_acknowledgement_deadline", "case_handoffs", ["acknowledgement_deadline"])
        op.create_index("ix_case_handoffs_created_at", "case_handoffs", ["created_at"])


def downgrade():
    op.drop_table("case_handoffs")
