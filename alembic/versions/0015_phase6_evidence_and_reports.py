"""Add evidence files table for versioned tamper-evident evidence documentation.

Revision ID: 0015_phase6_evidence_and_reports
Revises: 0014_phase5_durable_alerts_and_outbox

Phase 6: Tamper-Evident Versioned Evidence Documentation.
Preserves immutable cryptographic hashes, upload metadata, replacement lineage,
and honest malware scanning state for case evidence files.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0015_phase6_evidence_and_reports"
down_revision = "0014_phase5_durable_alerts_and_outbox"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)

    if not insp.has_table("evidence_files"):
        op.create_table(
            "evidence_files",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("complaint_id", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(50), server_default="OFFICER_UPLOAD", nullable=False),
            sa.Column("uploader_user_id", sa.Integer(), nullable=True),
            sa.Column("uploader_role", sa.String(50), nullable=False),
            sa.Column("uploader_org_id", sa.Integer(), nullable=True),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("storage_key", sa.String(255), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("sha256_hash", sa.String(64), nullable=False),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("status", sa.String(50), server_default="ACTIVE", nullable=False),
            sa.Column("malware_scan_status", sa.String(50), server_default="PENDING_SCAN", nullable=False),
            sa.Column("malware_scan_details", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("superseded_by_evidence_id", sa.Integer(), nullable=True),
            sa.Column("superseded_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["uploader_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["uploader_org_id"], ["organizations.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["superseded_by_evidence_id"], ["evidence_files.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_evidence_files_id", "evidence_files", ["id"])
        op.create_index("ix_evidence_files_complaint_id", "evidence_files", ["complaint_id"])
        op.create_index("ix_evidence_files_storage_key", "evidence_files", ["storage_key"], unique=True)
        op.create_index("ix_evidence_files_sha256_hash", "evidence_files", ["sha256_hash"])
        op.create_index("ix_evidence_files_status", "evidence_files", ["status"])
        op.create_index("ix_evidence_files_created_at", "evidence_files", ["created_at"])
        op.create_index("ix_evidence_complaint_status", "evidence_files", ["complaint_id", "status"])
        op.create_index("ix_evidence_sha256", "evidence_files", ["sha256_hash"])


def downgrade():
    op.drop_index("ix_evidence_sha256", table_name="evidence_files")
    op.drop_index("ix_evidence_complaint_status", table_name="evidence_files")
    op.drop_table("evidence_files")
