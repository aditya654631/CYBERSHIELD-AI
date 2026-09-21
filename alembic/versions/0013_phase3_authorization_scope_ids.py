"""Add trusted organization ownership and bank scope identifiers.

Revision ID: 0013_phase3_authorization_scope_ids
Revises: 0012_transaction_created_by_user_id

Historical rows intentionally remain NULL: the migration must not infer legal case
ownership or bank participation from free-text names.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0013_phase3_authorization_scope_ids"
down_revision = "0012_transaction_created_by_user_id"
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

    complaint_cols = get_column_names("complaints")
    complaint_ixs = get_existing_indexes("complaints")
    account_cols = get_column_names("accounts")
    account_ixs = get_existing_indexes("accounts")
    bank_action_cols = get_column_names("bank_actions")
    bank_action_ixs = get_existing_indexes("bank_actions")

    with op.batch_alter_table("complaints", schema=None) as batch_op:
        if "owner_organization_id" not in complaint_cols:
            batch_op.add_column(sa.Column("owner_organization_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_complaints_owner_organization_id", "organizations",
                ["owner_organization_id"], ["id"], ondelete="SET NULL"
            )
        if "owner_user_id" not in complaint_cols:
            batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_complaints_owner_user_id", "users",
                ["owner_user_id"], ["id"], ondelete="SET NULL"
            )
        if "ix_complaints_owner_organization_id" not in complaint_ixs:
            batch_op.create_index("ix_complaints_owner_organization_id", ["owner_organization_id"])
        if "ix_complaints_owner_user_id" not in complaint_ixs:
            batch_op.create_index("ix_complaints_owner_user_id", ["owner_user_id"])

    with op.batch_alter_table("accounts", schema=None) as batch_op:
        if "bank_organization_id" not in account_cols:
            batch_op.add_column(sa.Column("bank_organization_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_accounts_bank_organization_id", "organizations",
                ["bank_organization_id"], ["id"], ondelete="SET NULL"
            )
        if "ix_accounts_bank_organization_id" not in account_ixs:
            batch_op.create_index("ix_accounts_bank_organization_id", ["bank_organization_id"])

    if insp.has_table("bank_actions"):
        with op.batch_alter_table("bank_actions", schema=None) as batch_op:
            if "bank_organization_id" not in bank_action_cols:
                batch_op.add_column(sa.Column("bank_organization_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_bank_actions_bank_organization_id", "organizations",
                    ["bank_organization_id"], ["id"], ondelete="SET NULL"
                )
            if "ix_bank_actions_bank_organization_id" not in bank_action_ixs:
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
