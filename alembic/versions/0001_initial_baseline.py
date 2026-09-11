"""0001_initial_baseline

Revision ID: 0001_initial_baseline
Revises: 
Create Date: 2026-09-11 03:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_initial_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('org_type', sa.String(length=50), nullable=True, server_default='LEA'),
        sa.Column('state', sa.String(length=100), nullable=True, server_default='Madhya Pradesh'),
        sa.Column('district', sa.String(length=100), nullable=True, server_default='Bhopal'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organizations_id'), 'organizations', ['id'], unique=False)

    # 2. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True, server_default='ANALYST'),
        sa.Column('badge_number', sa.String(length=50), nullable=True, server_default='CS-7701'),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 3. location_clusters
    op.create_table(
        'location_clusters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_name', sa.String(length=255), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('district', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=True, server_default='Madhya Pradesh'),
        sa.Column('center_lat', sa.Float(), nullable=False),
        sa.Column('center_lon', sa.Float(), nullable=False),
        sa.Column('radius_km', sa.Float(), nullable=True, server_default='2.5'),
        sa.Column('historical_fraud_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('atm_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('risk_score', sa.Float(), nullable=True, server_default='0.5'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_location_clusters_id'), 'location_clusters', ['id'], unique=False)

    # 4. atm_locations
    op.create_table(
        'atm_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('atm_code', sa.String(length=50), nullable=True),
        sa.Column('bank_name', sa.String(length=100), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('district', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=True, server_default='Madhya Pradesh'),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('cash_available', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('risk_rating', sa.String(length=20), nullable=True, server_default='MEDIUM'),
        sa.Column('cluster_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['cluster_id'], ['location_clusters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_atm_locations_id'), 'atm_locations', ['id'], unique=False)
    op.create_index(op.f('ix_atm_locations_atm_code'), 'atm_locations', ['atm_code'], unique=True)

    # 5. complaints
    op.create_table(
        'complaints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_number', sa.String(length=50), nullable=False),
        sa.Column('fraud_type', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('victim_name', sa.String(length=255), nullable=True),
        sa.Column('victim_phone', sa.String(length=50), nullable=True),
        sa.Column('victim_location', sa.String(length=255), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=True, server_default='Madhya Pradesh'),
        sa.Column('district', sa.String(length=100), nullable=True, server_default='Bhopal'),
        sa.Column('payment_channel', sa.String(length=50), nullable=True, server_default='UPI'),
        sa.Column('reported_at', sa.DateTime(), nullable=True),
        sa.Column('incident_time', sa.DateTime(), nullable=True),
        sa.Column('risk_level', sa.String(length=20), nullable=True, server_default='MEDIUM'),
        sa.Column('risk_score', sa.Float(), nullable=True, server_default='0.5'),
        sa.Column('prediction_status', sa.String(length=50), nullable=True, server_default='PENDING'),
        sa.Column('case_status', sa.String(length=50), nullable=True, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_complaints_id'), 'complaints', ['id'], unique=False)
    op.create_index(op.f('ix_complaints_complaint_number'), 'complaints', ['complaint_number'], unique=True)

    # 6. accounts
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_number', sa.String(length=100), nullable=False),
        sa.Column('masked_account', sa.String(length=50), nullable=False),
        sa.Column('bank_name', sa.String(length=100), nullable=False),
        sa.Column('branch', sa.String(length=100), nullable=True),
        sa.Column('ifsc', sa.String(length=50), nullable=True),
        sa.Column('holder_name', sa.String(length=255), nullable=False),
        sa.Column('account_type', sa.String(length=50), nullable=True, server_default='SAVINGS'),
        sa.Column('risk_score', sa.Float(), nullable=True, server_default='0.1'),
        sa.Column('is_mule', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('flag_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_accounts_id'), 'accounts', ['id'], unique=False)
    op.create_index(op.f('ix_accounts_account_number'), 'accounts', ['account_number'], unique=True)

    # 7. transactions
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_ref', sa.String(length=100), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('sender_account_id', sa.Integer(), nullable=False),
        sa.Column('receiver_account_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('payment_channel', sa.String(length=50), nullable=True, server_default='UPI'),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('hop_number', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='COMPLETED'),
        sa.Column('suspicious_flag', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id']),
        sa.ForeignKeyConstraint(['receiver_account_id'], ['accounts.id']),
        sa.ForeignKeyConstraint(['sender_account_id'], ['accounts.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_id'), 'transactions', ['id'], unique=False)
    op.create_index(op.f('ix_transactions_transaction_ref'), 'transactions', ['transaction_ref'], unique=True)

    # 8. withdrawals
    op.create_table(
        'withdrawals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('atm_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('camera_flagged', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id']),
        sa.ForeignKeyConstraint(['atm_id'], ['atm_locations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_withdrawals_id'), 'withdrawals', ['id'], unique=False)

    # 9. predictions
    op.create_table(
        'predictions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('prediction_mode', sa.String(length=50), nullable=True, server_default='deterministic_demo'),
        sa.Column('model_version', sa.String(length=50), nullable=True, server_default='demo-provider-v1'),
        sa.Column('predicted_window_start', sa.DateTime(), nullable=False),
        sa.Column('predicted_window_end', sa.DateTime(), nullable=False),
        sa.Column('window_label', sa.String(length=100), nullable=True, server_default='Next 2–4 Hours'),
        sa.Column('primary_cluster_id', sa.Integer(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True, server_default='0.85'),
        sa.Column('risk_level', sa.String(length=50), nullable=True, server_default='CRITICAL'),
        sa.Column('confidence_score', sa.Float(), nullable=True, server_default='0.92'),
        sa.Column('ml_score', sa.Float(), nullable=True, server_default='0.88'),
        sa.Column('graph_score', sa.Float(), nullable=True, server_default='0.85'),
        sa.Column('geo_score', sa.Float(), nullable=True, server_default='0.84'),
        sa.Column('temporal_score', sa.Float(), nullable=True, server_default='0.80'),
        sa.Column('intervention_priority', sa.Integer(), nullable=True, server_default='94'),
        sa.Column('why_explanation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id']),
        sa.ForeignKeyConstraint(['primary_cluster_id'], ['location_clusters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_predictions_id'), 'predictions', ['id'], unique=False)

    # 10. prediction_locations
    op.create_table(
        'prediction_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prediction_id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=True),
        sa.Column('location_name', sa.String(length=255), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('probability', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String(length=50), nullable=True, server_default='CRITICAL'),
        sa.Column('distance_km', sa.Float(), nullable=True, server_default='185.0'),
        sa.Column('reasoning', sa.String(length=255), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['cluster_id'], ['location_clusters.id']),
        sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prediction_locations_id'), 'prediction_locations', ['id'], unique=False)

    # 11. alerts
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('prediction_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=True, server_default='CRITICAL'),
        sa.Column('location_name', sa.String(length=255), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=True, server_default='0.87'),
        sa.Column('expected_window', sa.String(length=100), nullable=True, server_default='Next 2–4 Hours'),
        sa.Column('amount_at_risk', sa.Float(), nullable=True, server_default='125000.0'),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='NEW'),
        sa.Column('acknowledged_by', sa.String(length=255), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('action_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id']),
        sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_id'), 'alerts', ['id'], unique=False)

    # 12. case_notes
    op.create_table(
        'case_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_case_notes_id'), 'case_notes', ['id'], unique=False)

    # 13. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('officer_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('case_number', sa.String(length=100), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True, server_default='127.0.0.1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('case_notes')
    op.drop_table('alerts')
    op.drop_table('prediction_locations')
    op.drop_table('predictions')
    op.drop_table('withdrawals')
    op.drop_table('transactions')
    op.drop_table('accounts')
    op.drop_table('complaints')
    op.drop_table('atm_locations')
    op.drop_table('location_clusters')
    op.drop_table('users')
    op.drop_table('organizations')
