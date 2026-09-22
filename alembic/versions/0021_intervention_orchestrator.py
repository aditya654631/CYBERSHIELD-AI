"""Phase 3: Add intervention_plans and intervention_plan_actions tables.

Revision ID: 0021_intervention_orchestrator
Revises: 0020_withdrawal_attribution_and_region_fix
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0021_intervention_orchestrator"
down_revision = "0020_withdrawal_attribution_and_region_fix"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    tables = set(insp.get_table_names())

    if "intervention_plans" not in tables:
        op.create_table(
            "intervention_plans",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("plan_uuid", sa.String(length=36), nullable=False),
            sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id"), nullable=False),
            sa.Column("prediction_id", sa.Integer(), sa.ForeignKey("predictions.id"), nullable=False),
            sa.Column("prediction_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("generated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
            sa.Column("plan_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("primary_candidate_cluster_id", sa.Integer(), sa.ForeignKey("location_clusters.id", ondelete="SET NULL"), nullable=True),
            sa.Column("operational_window_start", sa.DateTime(), nullable=True),
            sa.Column("operational_window_end", sa.DateTime(), nullable=True),
            sa.Column("summary_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_intervention_plans_plan_uuid", "intervention_plans", ["plan_uuid"], unique=True)
        op.create_index("ix_intervention_plans_complaint_id", "intervention_plans", ["complaint_id"])
        op.create_index("ix_intervention_plans_prediction_id", "intervention_plans", ["prediction_id"])
        op.create_index("ix_intervention_plans_status", "intervention_plans", ["status"])
        op.create_index("ix_intervention_plans_comp_status", "intervention_plans", ["complaint_id", "status"])

    if "intervention_plan_actions" not in tables:
        op.create_table(
            "intervention_plan_actions",
            sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
            sa.Column("plan_id", sa.Integer(), sa.ForeignKey("intervention_plans.id", ondelete="CASCADE"), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("action_type", sa.String(length=100), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("priority", sa.String(length=20), nullable=False, server_default="MEDIUM"),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="RECOMMENDED"),
            sa.Column("recommended_reason", sa.Text(), nullable=True),
            sa.Column("linked_alert_id", sa.Integer(), sa.ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("linked_bank_action_id", sa.Integer(), sa.ForeignKey("bank_actions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("linked_handoff_id", sa.Integer(), sa.ForeignKey("case_handoffs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assigned_role", sa.String(length=50), nullable=True),
            sa.Column("assigned_organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_intervention_plan_actions_plan_id", "intervention_plan_actions", ["plan_id"])
        op.create_index("ix_intervention_plan_actions_category", "intervention_plan_actions", ["category"])
        op.create_index("ix_intervention_plan_actions_status", "intervention_plan_actions", ["status"])
        op.create_index("ix_intervention_actions_plan_category", "intervention_plan_actions", ["plan_id", "category"])


def downgrade():
    op.drop_table("intervention_plan_actions")
    op.drop_table("intervention_plans")
