"""Add created_by_user_id to Transaction for truthful actor attribution

Revision ID: 0012_transaction_created_by_user_id
Revises: 0011_canonical_transaction_dedup
Create Date: 2026-09-20 19:30:00.000000

Guarantees:
  - Nullable foreign key `created_by_user_id` on `transactions` referencing `users.id`.
  - Preserves NULL for historical rows whose actor cannot be proven.
  - Safe for SQLite (via batch mode) and PostgreSQL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "0012_transaction_created_by_user_id"
down_revision = "0011_canonical_transaction_dedup"
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

    tx_cols = get_column_names("transactions")
    tx_indexes = get_existing_indexes("transactions")

    with op.batch_alter_table("transactions", schema=None) as batch_op:
        if "created_by_user_id" not in tx_cols:
            batch_op.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_transactions_created_by_user_id",
                "users",
                ["created_by_user_id"],
                ["id"]
            )
        if "ix_transactions_created_by_user_id" not in tx_indexes:
            batch_op.create_index(
                "ix_transactions_created_by_user_id",
                ["created_by_user_id"]
            )


def downgrade():
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

    tx_cols = get_column_names("transactions")
    tx_indexes = get_existing_indexes("transactions")

    with op.batch_alter_table("transactions", schema=None) as batch_op:
        if "ix_transactions_created_by_user_id" in tx_indexes:
            batch_op.drop_index("ix_transactions_created_by_user_id")
        if "created_by_user_id" in tx_cols:
            try:
                batch_op.drop_constraint("fk_transactions_created_by_user_id", type_="foreignkey")
            except Exception:
                pass
            batch_op.drop_column("created_by_user_id")
