"""0002_hardened_schema

Revision ID: 0002_hardened_schema
Revises: 0001_initial_baseline
Create Date: 2026-09-11 03:12:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_hardened_schema'
down_revision: Union[str, None] = '0001_initial_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create complaint_accounts association table
    op.create_table(
        'complaint_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('association_type', sa.String(length=50), nullable=True, server_default='SUSPECT'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('complaint_id', 'account_id', name='uq_complaint_account')
    )
    op.create_index(op.f('ix_complaint_accounts_id'), 'complaint_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_complaint_accounts_complaint_id'), 'complaint_accounts', ['complaint_id'], unique=False)
    op.create_index(op.f('ix_complaint_accounts_account_id'), 'complaint_accounts', ['account_id'], unique=False)

    # 2. Harden complaints table: add coordinates (nullable, no fake default), description, Numeric amount, and indexes
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.add_column(sa.Column('victim_lat', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('victim_lon', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.alter_column('amount',
                              existing_type=sa.Float(),
                              type_=sa.Numeric(14, 2),
                              existing_nullable=False)
        batch_op.create_index(batch_op.f('ix_complaints_case_status'), ['case_status'], unique=False)

    # 3. Harden accounts table: add state and district columns
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('state', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('district', sa.String(length=100), nullable=True))

    # 4. Harden transactions table: Numeric amount, indexes
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column('amount',
                              existing_type=sa.Float(),
                              type_=sa.Numeric(14, 2),
                              existing_nullable=False)
        batch_op.create_index(batch_op.f('ix_transactions_complaint_id'), ['complaint_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_transactions_sender_account_id'), ['sender_account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_transactions_receiver_account_id'), ['receiver_account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_transactions_timestamp'), ['timestamp'], unique=False)

    # 5. Harden withdrawals table: Numeric amount, indexes
    with op.batch_alter_table('withdrawals', schema=None) as batch_op:
        batch_op.alter_column('amount',
                              existing_type=sa.Float(),
                              type_=sa.Numeric(14, 2),
                              existing_nullable=False)
        batch_op.create_index(batch_op.f('ix_withdrawals_atm_id'), ['atm_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_withdrawals_account_id'), ['account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_withdrawals_timestamp'), ['timestamp'], unique=False)

    # 6. Harden predictions table: indexes
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_predictions_complaint_id'), ['complaint_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_predictions_created_at'), ['created_at'], unique=False)

    # 7. Harden prediction_locations table: UNIQUE(prediction_id, rank), indexes
    with op.batch_alter_table('prediction_locations', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_prediction_rank', ['prediction_id', 'rank'])
        batch_op.create_index(batch_op.f('ix_prediction_locations_prediction_id'), ['prediction_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_prediction_locations_cluster_id'), ['cluster_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_prediction_locations_rank'), ['rank'], unique=False)

    # 8. Harden alerts table: Numeric amount_at_risk, indexes
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.alter_column('amount_at_risk',
                              existing_type=sa.Float(),
                              type_=sa.Numeric(14, 2),
                              existing_nullable=True)
        batch_op.create_index(batch_op.f('ix_alerts_complaint_id'), ['complaint_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_alerts_prediction_id'), ['prediction_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_alerts_created_at'), ['created_at'], unique=False)

    # 9. Harden case_notes table: indexes
    with op.batch_alter_table('case_notes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_case_notes_complaint_id'), ['complaint_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_case_notes_user_id'), ['user_id'], unique=False)

    # 10. Harden audit_logs table: FK to users.id (nullable, ondelete SET NULL), indexes
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_audit_logs_user_id', 'users', ['user_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index(batch_op.f('ix_audit_logs_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_created_at'), ['created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_created_at'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_user_id'))
        batch_op.drop_constraint('fk_audit_logs_user_id', type_='foreignkey')

    with op.batch_alter_table('case_notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_case_notes_user_id'))
        batch_op.drop_index(batch_op.f('ix_case_notes_complaint_id'))

    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alerts_created_at'))
        batch_op.drop_index(batch_op.f('ix_alerts_prediction_id'))
        batch_op.drop_index(batch_op.f('ix_alerts_complaint_id'))
        batch_op.alter_column('amount_at_risk',
                              existing_type=sa.Numeric(14, 2),
                              type_=sa.Float(),
                              existing_nullable=True)

    with op.batch_alter_table('prediction_locations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_prediction_locations_rank'))
        batch_op.drop_index(batch_op.f('ix_prediction_locations_cluster_id'))
        batch_op.drop_index(batch_op.f('ix_prediction_locations_prediction_id'))
        batch_op.drop_constraint('uq_prediction_rank', type_='unique')

    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_predictions_created_at'))
        batch_op.drop_index(batch_op.f('ix_predictions_complaint_id'))

    with op.batch_alter_table('withdrawals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_withdrawals_timestamp'))
        batch_op.drop_index(batch_op.f('ix_withdrawals_account_id'))
        batch_op.drop_index(batch_op.f('ix_withdrawals_atm_id'))
        batch_op.alter_column('amount',
                              existing_type=sa.Numeric(14, 2),
                              type_=sa.Float(),
                              existing_nullable=False)

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_transactions_timestamp'))
        batch_op.drop_index(batch_op.f('ix_transactions_receiver_account_id'))
        batch_op.drop_index(batch_op.f('ix_transactions_sender_account_id'))
        batch_op.drop_index(batch_op.f('ix_transactions_complaint_id'))
        batch_op.alter_column('amount',
                              existing_type=sa.Numeric(14, 2),
                              type_=sa.Float(),
                              existing_nullable=False)

    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('district')
        batch_op.drop_column('state')

    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_complaints_case_status'))
        batch_op.alter_column('amount',
                              existing_type=sa.Numeric(14, 2),
                              type_=sa.Float(),
                              existing_nullable=False)
        batch_op.drop_column('description')
        batch_op.drop_column('victim_lon')
        batch_op.drop_column('victim_lat')

    op.drop_table('complaint_accounts')
