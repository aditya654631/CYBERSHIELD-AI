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


revision = "0018_phase9_outcome_observations"
down_revision = "0017_phase8_bank_adapter_and_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outcome_observations",
        sa.Column("id", sa.Integer(), nullable=False),

        # --- Identity & Linkage ---
        sa.Column("complaint_id", sa.Integer(), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True),
        # Linked prediction: last OPERATIONAL prediction created strictly before observed_event_time.
        # NULL if no eligible prediction existed before the event (policy-enforced; never cherry-picked after outcome).
        sa.Column("linked_prediction_id", sa.Integer(), sa.ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("linked_prediction_version", sa.Integer(), nullable=True),
        # Pre-event prediction selection policy recorded at creation time
        sa.Column("prediction_selection_policy", sa.String(100), nullable=False, server_default="LAST_OPERATIONAL_BEFORE_EVENT"),
        sa.Column("linked_alert_id", sa.Integer(), sa.ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("linked_bank_action_id", sa.Integer(), sa.ForeignKey("bank_actions.id", ondelete="SET NULL"), nullable=True, index=True),

        # --- Outcome Classification ---
        # CONFIRMED_CASHOUT: cash-out observed at specific location/time
        # MULTIPLE_CASHOUT: multiple withdrawals observed (use cashout_events JSON)
        # NO_OBSERVED_CASHOUT: monitored window passed with no observed cash-out
        # UNKNOWN: outcome not determined / monitoring inconclusive
        # DATA_EXCLUDED: explicitly excluded from metrics (reason in notes)
        sa.Column("outcome_type", sa.String(50), nullable=False, index=True),

        # --- Actual Event Fields (CONFIRMED_CASHOUT / MULTIPLE_CASHOUT) ---
        sa.Column("observed_event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_atm_id", sa.Integer(), sa.ForeignKey("atm_locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actual_cluster_id", sa.Integer(), sa.ForeignKey("location_clusters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actual_lat", sa.Float(), nullable=True),
        sa.Column("actual_lon", sa.Float(), nullable=True),
        sa.Column("actual_location_name", sa.String(255), nullable=True),
        sa.Column("actual_withdrawal_amount_inr", sa.Numeric(14, 2), nullable=True),
        # Multiple cashout events stored as JSON array: [{time, lat, lon, amount, atm_code, ...}]
        sa.Column("cashout_events", sa.JSON(), nullable=True),

        # --- Financial Intervention Fields ---
        # VERIFIED hold amount from bank_action.held_amount (copy at observation time for immutability)
        sa.Column("verified_held_amount_inr", sa.Numeric(14, 2), nullable=True),
        # VERIFIED released amount — funds unfrozen after investigation
        sa.Column("verified_released_amount_inr", sa.Numeric(14, 2), nullable=True),
        # ACTUAL recovered amount — funds returned to victim / legally seized
        # Must NOT be added to held_amount to avoid double-counting
        sa.Column("actual_recovered_amount_inr", sa.Numeric(14, 2), nullable=True),
        sa.Column("recovery_verified_by", sa.String(255), nullable=True),
        sa.Column("recovery_verified_at", sa.DateTime(timezone=True), nullable=True),

        # --- Derived Measurement Fields ---
        # Rank of the actual cashout cluster in the linked prediction's locations (1=top, NULL if not in Top-K)
        sa.Column("prediction_rank_matched", sa.Integer(), nullable=True),
        # Distance between linked prediction rank-1 cluster centroid and actual cashout (km)
        sa.Column("distance_error_km", sa.Float(), nullable=True),
        # Minutes from linked_prediction.created_at to observed_event_time (NULL if no prediction/event)
        sa.Column("prediction_lead_time_minutes", sa.Float(), nullable=True),
        # Minutes from linked alert.created_at to observed_event_time
        sa.Column("alert_lead_time_minutes", sa.Float(), nullable=True),
        # Minutes from alert.created_at to alert.acknowledged_at
        sa.Column("alert_acknowledgement_latency_minutes", sa.Float(), nullable=True),
        # Minutes from bank_action.requested_at to bank_action.held_at
        sa.Column("bank_response_latency_minutes", sa.Float(), nullable=True),

        # --- Cohort / Labelling ---
        # Synthetic/demo outcomes tracked separately; never mixed with real verified outcomes.
        # Matches complaint provenance_mode or explicitly set by ingesting officer.
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_excluded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        # Observational label: VERIFIED, UNVERIFIED, PENDING_VERIFICATION
        sa.Column("verification_status", sa.String(50), nullable=False, server_default="PENDING_VERIFICATION"),

        # --- Provenance & Attribution ---
        sa.Column("source", sa.String(100), nullable=False),  # OFFICER_MANUAL, CFCFRMS_IMPORT, BANK_REPORT, COURT_RECORD, AUTOMATED_MONITORING
        sa.Column("verifier_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("verifier_name", sa.String(255), nullable=True),
        sa.Column("verifier_role", sa.String(50), nullable=True),
        sa.Column("ingested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True),
        sa.Column("ingested_by_role", sa.String(50), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),  # UTC: when record was entered into the system

        # --- Correction Lineage (append-only with version chain) ---
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        # If this record corrects a prior version, points to the superseded record
        sa.Column("corrects_outcome_id", sa.Integer(), sa.ForeignKey("outcome_observations.id", ondelete="SET NULL"), nullable=True),
        # Status: ACTIVE (current) or SUPERSEDED (corrected by a newer version)
        sa.Column("record_status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("correction_reason", sa.Text(), nullable=True),

        # --- Notes / Timestamps ---
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for common access patterns
    op.create_index("ix_outcome_obs_complaint_id", "outcome_observations", ["complaint_id"])
    op.create_index("ix_outcome_obs_outcome_type", "outcome_observations", ["outcome_type"])
    op.create_index("ix_outcome_obs_record_status", "outcome_observations", ["record_status"])
    op.create_index("ix_outcome_obs_linked_prediction_id", "outcome_observations", ["linked_prediction_id"])
    op.create_index("ix_outcome_obs_is_synthetic", "outcome_observations", ["is_synthetic"])
    op.create_index("ix_outcome_obs_is_excluded", "outcome_observations", ["is_excluded"])
    op.create_index("ix_outcome_obs_received_at", "outcome_observations", ["received_at"])
    op.create_index("ix_outcome_obs_verification_status", "outcome_observations", ["verification_status"])
    op.create_index(
        "ix_outcome_obs_comp_status",
        "outcome_observations",
        ["complaint_id", "record_status", "outcome_type"]
    )


def downgrade():
    op.drop_index("ix_outcome_obs_comp_status", table_name="outcome_observations")
    op.drop_index("ix_outcome_obs_verification_status", table_name="outcome_observations")
    op.drop_index("ix_outcome_obs_received_at", table_name="outcome_observations")
    op.drop_index("ix_outcome_obs_is_excluded", table_name="outcome_observations")
    op.drop_index("ix_outcome_obs_is_synthetic", table_name="outcome_observations")
    op.drop_index("ix_outcome_obs_linked_prediction_id", table_name="outcome_observations")
    op.drop_index("ix_outcome_obs_record_status", table_name="outcome_observations")
    op.drop_index("ix_outcome_obs_outcome_type", table_name="outcome_observations")
    op.drop_index("ix_outcome_obs_complaint_id", table_name="outcome_observations")
    op.drop_table("outcome_observations")
