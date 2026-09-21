"""Add Phase 9 outcome_observations table for verified operational outcome tracking.

Revision ID: 0018_phase9_outcome_observations
Revises: 0017_phase8_bank_adapter_and_lifecycle

Phase 9: Verified Outcomes & Operational Measurements.
Adds append-only but correctable outcome observations linked to complaints,
predictions, alerts, and bank actions. Records actual cashout events, no-cashout
observations, unknown outcomes, confirmed holds, releases, and recoveries.
Implements strict prediction evaluation policy (last eligible pre-event prediction)
to prevent hindsight cherry-picking.

Denominator rules:
  - CONFIRMED_CASHOUT and NO_OBSERVED_CASHOUT contribute to success/failure denominators.
  - UNKNOWN outcomes are excluded from success/failure with denominator displayed.
  - Synthetic/demo outcomes tracked separately; never mixed with real verified outcomes.
  - Hold amounts and recovery amounts tracked separately; their sum is NOT presented
    as independently saved money.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0018_phase9_outcome_observations"
down_revision = "0017_phase8_bank_adapter_and_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)

    if not insp.has_table("outcome_observations"):
        op.create_table(
            "outcome_observations",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),

            # --- Identity & Linkage ---
            sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            # Linked prediction: last OPERATIONAL prediction created strictly before observed_event_time.
            # NULL if no eligible prediction existed before the event (policy-enforced; never cherry-picked after outcome).
            sa.Column("linked_prediction_id", sa.Integer(), sa.ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("linked_prediction_version", sa.Integer(), nullable=True),
            # Pre-event prediction selection policy recorded at creation time
            sa.Column("prediction_selection_policy", sa.String(100), nullable=False, server_default="LAST_OPERATIONAL_BEFORE_EVENT"),
            sa.Column("linked_alert_id", sa.Integer(), sa.ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("linked_bank_action_id", sa.Integer(), sa.ForeignKey("bank_actions.id", ondelete="SET NULL"), nullable=True),

            # --- Outcome Classification ---
            # CONFIRMED_CASHOUT: cash-out observed at specific location/time
            # MULTIPLE_CASHOUT: multiple withdrawals observed (use cashout_events JSON)
            # NO_OBSERVED_CASHOUT: monitored window passed with no observed cash-out
            # UNKNOWN: outcome not determined / monitoring inconclusive
            # DATA_EXCLUDED: explicitly excluded from metrics (reason in notes)
            sa.Column("outcome_type", sa.String(50), nullable=False),

            # --- Actual Event Fields (CONFIRMED_CASHOUT / MULTIPLE_CASHOUT) ---
            sa.Column("observed_event_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("actual_atm_id", sa.Integer(), sa.ForeignKey("atm_locations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("actual_cluster_id", sa.Integer(), sa.ForeignKey("location_clusters.id", ondelete="SET NULL"), nullable=True),
            sa.Column("actual_lat", sa.Float(), nullable=True),
            sa.Column("actual_lon", sa.Float(), nullable=True),
            sa.Column("actual_location_name", sa.String(255), nullable=True),
            sa.Column("actual_withdrawal_amount_inr", sa.Numeric(14, 2), nullable=True),

            # Multi-cashout structured event sequence
            # Format: [{"event_time": ISO, "atm_id": int, "cluster_id": int, "amount_inr": float, "lat": float, "lon": float}]
            sa.Column("cashout_events", sa.JSON(), nullable=True),

            # --- Financial Intervention Tracking (SEPARATED metrics — never summed as 'total saved') ---
            # Verified hold amount: amount frozen by bank prior to withdrawal attempt
            sa.Column("verified_held_amount_inr", sa.Numeric(14, 2), server_default="0.0", nullable=False),
            # Verified release amount: amount subsequently unfrozen (e.g. mistaken hold)
            sa.Column("verified_released_amount_inr", sa.Numeric(14, 2), server_default="0.0", nullable=False),
            # Actual recovered amount: funds physically recovered after withdrawal or via inter-bank recall
            sa.Column("actual_recovered_amount_inr", sa.Numeric(14, 2), server_default="0.0", nullable=False),
            sa.Column("recovery_verified_by", sa.String(255), nullable=True),
            sa.Column("recovery_verified_at", sa.DateTime(timezone=True), nullable=True),

            # --- Prediction Accuracy Evaluation (derived from linked prediction) ---
            # 1 = Rank-1 hit, 2 = Rank-2 hit, 3 = Rank-3 hit, 0 = outside top-3, NULL = no location prediction
            sa.Column("prediction_rank_matched", sa.Integer(), nullable=True),
            # Distance from actual withdrawal location to top-1 predicted cluster center (km)
            sa.Column("distance_error_km", sa.Float(), nullable=True),
            # Lead time: minutes between prediction creation and actual cashout event (negative = after event)
            sa.Column("prediction_lead_time_minutes", sa.Float(), nullable=True),
            # Alert lead time: minutes between alert creation and actual cashout event
            sa.Column("alert_lead_time_minutes", sa.Float(), nullable=True),
            # Bank action response latency: minutes between alert dispatch and bank response
            sa.Column("alert_acknowledgement_latency_minutes", sa.Float(), nullable=True),
            sa.Column("bank_response_latency_minutes", sa.Float(), nullable=True),

            # --- Provenance & Integrity ---
            # Flag for synthetic / simulated data; synthetic rows are excluded from operational metrics
            sa.Column("is_synthetic", sa.Boolean(), server_default=sa.false(), nullable=False),
            # Explicit exclusion from metrics computation (e.g., test case, corrupted external feed)
            sa.Column("is_excluded", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("exclusion_reason", sa.Text(), nullable=True),
            # Verification status: PROVISIONAL (automated intake), VERIFIED (officer confirmed), DISPUTED
            sa.Column("verification_status", sa.String(50), server_default="PROVISIONAL", nullable=False),
            sa.Column("source", sa.String(100), server_default="OPERATIONAL_MANUAL", nullable=False),
            sa.Column("verifier_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("verifier_name", sa.String(255), nullable=True),
            sa.Column("verifier_role", sa.String(50), nullable=True),
            sa.Column("ingested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("ingested_by_role", sa.String(50), nullable=True),
            sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

            # --- Versioning & Correction Lineage (Append-only audit) ---
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("corrects_outcome_id", sa.Integer(), sa.ForeignKey("outcome_observations.id", ondelete="SET NULL"), nullable=True),
            # Record status: ACTIVE (current authoritative observation), SUPERSEDED (replaced by correction)
            sa.Column("record_status", sa.String(50), server_default="ACTIVE", nullable=False),
            sa.Column("correction_reason", sa.Text(), nullable=True),

            # Free-text investigation notes
            sa.Column("notes", sa.Text(), nullable=True),

            # Timestamps
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

        with op.batch_alter_table("outcome_observations", schema=None) as batch_op:
            batch_op.create_index("ix_outcome_observations_id", ["id"])
            batch_op.create_index("ix_outcome_observations_complaint_id", ["complaint_id"])
            batch_op.create_index("ix_outcome_observations_linked_prediction_id", ["linked_prediction_id"])
            batch_op.create_index("ix_outcome_observations_linked_alert_id", ["linked_alert_id"])
            batch_op.create_index("ix_outcome_observations_linked_bank_action_id", ["linked_bank_action_id"])
            batch_op.create_index("ix_outcome_observations_outcome_type", ["outcome_type"])
            batch_op.create_index("ix_outcome_observations_verification_status", ["verification_status"])
            batch_op.create_index("ix_outcome_observations_record_status", ["record_status"])
            batch_op.create_index("ix_outcome_observations_is_synthetic", ["is_synthetic"])
            batch_op.create_index("ix_outcome_observations_is_excluded", ["is_excluded"])
            batch_op.create_index("ix_outcome_observations_observed_event_time", ["observed_event_time"])
            batch_op.create_index("ix_outcome_observations_created_at", ["created_at"])


def downgrade():
    op.drop_table("outcome_observations")
