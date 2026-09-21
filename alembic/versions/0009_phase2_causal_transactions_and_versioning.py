"""Phase 2: Causal Transactions and Immutable Prediction Versioning

Revision ID: 0009_phase2_causal_transactions
Revises: 0008_prediction_snapshots
Create Date: 2026-09-20 01:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "0009_phase2_causal_transactions"
down_revision = "0008_prediction_snapshots"
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

    pred_cols = get_column_names("predictions")
    tx_cols = get_column_names("transactions")

    # 1. Additive columns to `predictions` via batch_alter_table for SQLite & Postgres compatibility
    with op.batch_alter_table("predictions", schema=None) as batch_op:
        if "version_number" not in pred_cols:
            batch_op.add_column(sa.Column("version_number", sa.Integer(), nullable=True, server_default="1"))
        if "parent_prediction_id" not in pred_cols:
            batch_op.add_column(sa.Column("parent_prediction_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key("fk_predictions_parent", "predictions", ["parent_prediction_id"], ["id"])
        if "analysis_as_of" not in pred_cols:
            batch_op.add_column(sa.Column("analysis_as_of", sa.DateTime(), nullable=True))
        if "input_fingerprint" not in pred_cols:
            batch_op.add_column(sa.Column("input_fingerprint", sa.String(length=64), nullable=True))

    # 2. Additive columns to `transactions` via batch_alter_table
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        if "received_at" not in tx_cols:
            batch_op.add_column(sa.Column("received_at", sa.DateTime(), nullable=True))
        if "source_system" not in tx_cols:
            batch_op.add_column(sa.Column("source_system", sa.String(length=100), nullable=True, server_default="HISTORICAL_LEGACY"))
        if "dedup_key" not in tx_cols:
            batch_op.add_column(sa.Column("dedup_key", sa.String(length=64), nullable=True))
        if "is_reversal" not in tx_cols:
            batch_op.add_column(sa.Column("is_reversal", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "correction_of_ref" not in tx_cols:
            batch_op.add_column(sa.Column("correction_of_ref", sa.String(length=100), nullable=True))
        if "analysis_status" not in tx_cols:
            batch_op.add_column(sa.Column("analysis_status", sa.String(length=50), nullable=True))
        if "prediction_id" not in tx_cols:
            batch_op.add_column(sa.Column("prediction_id", sa.Integer(), nullable=True))

    # 3. Deterministic backfill of version numbers per complaint
    # Ordered deterministically by created_at ASC, id ASC
    connection = bind
    res = connection.execute(sa.text("SELECT id, complaint_id, created_at FROM predictions ORDER BY complaint_id ASC, created_at ASC, id ASC"))
    rows = res.fetchall()
    complaint_preds = {}
    for row in rows:
        p_id, c_id, _ = row[0], row[1], row[2]
        complaint_preds.setdefault(c_id, []).append(p_id)

    for c_id, p_ids in complaint_preds.items():
        prev_id = None
        for ver_idx, p_id in enumerate(p_ids, start=1):
            connection.execute(
                sa.text("UPDATE predictions SET version_number = :ver, parent_prediction_id = :parent WHERE id = :pid"),
                {"ver": ver_idx, "parent": prev_id, "pid": p_id}
            )
            prev_id = p_id

    # 4. Indexes and Concurrency Constraints
    pred_indexes = get_existing_indexes("predictions")
    if "ix_predictions_comp_version" not in pred_indexes:
        op.create_index("ix_predictions_comp_version", "predictions", ["complaint_id", "version_number"], unique=True)

    if "ix_predictions_comp_input_fp" not in pred_indexes:
        op.create_index("ix_predictions_comp_input_fp", "predictions", ["complaint_id", "input_fingerprint"], unique=False)
    if "ix_predictions_analysis_as_of" not in pred_indexes:
        op.create_index("ix_predictions_analysis_as_of", "predictions", ["analysis_as_of"], unique=False)

    tx_indexes = get_existing_indexes("transactions")
    if "ix_transactions_received_at" not in tx_indexes:
        op.create_index("ix_transactions_received_at", "transactions", ["received_at"], unique=False)
    if "ix_transactions_source_ref" not in tx_indexes:
        op.create_index("ix_transactions_source_ref", "transactions", ["source_system", "transaction_ref"], unique=False)


def downgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)

    def get_existing_indexes(table_name):
        try:
            return {ix["name"] for ix in insp.get_indexes(table_name)}
        except Exception:
            return set()

    pred_indexes = get_existing_indexes("predictions")
    for ix in ["ix_predictions_analysis_as_of", "ix_predictions_comp_input_fp", "ix_predictions_comp_version"]:
        if ix in pred_indexes:
            try:
                op.drop_index(ix, table_name="predictions")
            except Exception:
                pass

    tx_indexes = get_existing_indexes("transactions")
    for ix in ["ix_transactions_source_ref", "ix_transactions_received_at"]:
        if ix in tx_indexes:
            try:
                op.drop_index(ix, table_name="transactions")
            except Exception:
                pass

    with op.batch_alter_table("predictions", schema=None) as batch_op:
        pred_cols = {c["name"] for c in insp.get_columns("predictions")}
        for col in ["input_fingerprint", "analysis_as_of", "parent_prediction_id", "version_number"]:
            if col in pred_cols:
                try:
                    batch_op.drop_column(col)
                except Exception:
                    pass

    with op.batch_alter_table("transactions", schema=None) as batch_op:
        tx_cols = {c["name"] for c in insp.get_columns("transactions")}
        for col in ["prediction_id", "analysis_status", "correction_of_ref", "is_reversal", "dedup_key", "source_system", "received_at"]:
            if col in tx_cols:
                try:
                    batch_op.drop_column(col)
                except Exception:
                    pass
