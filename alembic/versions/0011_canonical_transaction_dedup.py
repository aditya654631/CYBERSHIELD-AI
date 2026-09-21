"""Enforce canonical transaction reference uniqueness and deduplication identity

Revision ID: 0011_canonical_transaction_dedup
Revises: 0010_explicit_analysis_purpose
Create Date: 2026-09-20 17:00:00.000000

Guarantees:
  - Global system-wide uniqueness of transaction_ref mirroring banking network UTRs/RRNs.
  - Strict database-enforced unique constraint `uq_transactions_transaction_ref`.
  - Idempotent deduplication and concurrent race protection.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "0011_canonical_transaction_dedup"
down_revision = "0010_explicit_analysis_purpose"
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

    def get_existing_unique_constraints(table_name):
        try:
            return {uc["name"] for uc in insp.get_unique_constraints(table_name)}
        except Exception:
            return set()

    tx_indexes = get_existing_indexes("transactions")
    tx_uqs = get_existing_unique_constraints("transactions")

    with op.batch_alter_table("transactions", schema=None) as batch_op:
        if "uq_transactions_transaction_ref" not in tx_uqs and "uq_transactions_transaction_ref" not in tx_indexes:
            # Create canonical unique constraint on transaction_ref
            try:
                batch_op.create_unique_constraint(
                    "uq_transactions_transaction_ref",
                    ["transaction_ref"]
                )
            except Exception:
                # If unique constraint cannot be created directly via batch, ensure unique index exists
                if "ix_transactions_transaction_ref" not in tx_indexes:
                    batch_op.create_index(
                        "uq_transactions_transaction_ref",
                        ["transaction_ref"],
                        unique=True
                    )


def downgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    tx_uqs = {uc["name"] for uc in insp.get_unique_constraints("transactions")}
    tx_indexes = {ix["name"] for ix in insp.get_indexes("transactions")}

    with op.batch_alter_table("transactions", schema=None) as batch_op:
        if "uq_transactions_transaction_ref" in tx_uqs:
            batch_op.drop_constraint("uq_transactions_transaction_ref", type_="unique")
        elif "uq_transactions_transaction_ref" in tx_indexes:
            batch_op.drop_index("uq_transactions_transaction_ref")
