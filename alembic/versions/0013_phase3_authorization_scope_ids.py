"""Add trusted organization ownership and bank scope identifiers.

Revision ID: 0013_phase3_authorization_scope_ids
Revises: 0012_transaction_created_by_user_id

Historical rows intentionally remain NULL: the migration must not infer legal case
ownership or bank participation from free-text names.
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_phase3_authorization_scope_ids"
down_revision = "0012_transaction_created_by_user_id"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("complaints", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_organization_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_complaints_owner_organization_id", "organizations",
            ["owner_organization_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_foreign_key(
            "fk_complaints_owner_user_id", "users",
            ["owner_user_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_complaints_owner_organization_id", ["owner_organization_id"])
        batch_op.create_index("ix_complaints_owner_user_id", ["owner_user_id"])

    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bank_organization_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_accounts_bank_organization_id", "organizations",
            ["bank_organization_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_accounts_bank_organization_id", ["bank_organization_id"])

    with op.batch_alter_table("bank_actions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bank_organization_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_bank_actions_bank_organization_id", "organizations",
            ["bank_organization_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_bank_actions_bank_organization_id", ["bank_organization_id"])


def downgrade():
    with op.batch_alter_table("bank_actions", schema=None) as batch_op:
        batch_op.drop_index("ix_bank_actions_bank_organization_id")
        batch_op.drop_constraint("fk_bank_actions_bank_organization_id", type_="foreignkey")
        batch_op.drop_column("bank_organization_id")

    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_index("ix_accounts_bank_organization_id")
        batch_op.drop_constraint("fk_accounts_bank_organization_id", type_="foreignkey")
        batch_op.drop_column("bank_organization_id")

    with op.batch_alter_table("complaints", schema=None) as batch_op:
        batch_op.drop_index("ix_complaints_owner_user_id")
        batch_op.drop_index("ix_complaints_owner_organization_id")
        batch_op.drop_constraint("fk_complaints_owner_user_id", type_="foreignkey")
        batch_op.drop_constraint("fk_complaints_owner_organization_id", type_="foreignkey")
        batch_op.drop_column("owner_user_id")
        batch_op.drop_column("owner_organization_id")
