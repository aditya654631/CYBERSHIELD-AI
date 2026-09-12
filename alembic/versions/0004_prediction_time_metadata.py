"""0004_prediction_time_metadata

Revision ID: 0004_prediction_time_metadata
Revises: 0003_intake_operational_fields
Create Date: 2026-09-12 03:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004_prediction_time_metadata'
down_revision: Union[str, None] = '0003_intake_operational_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('time_model_version', sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column('predicted_minutes_to_cashout', sa.Float(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.drop_column('predicted_minutes_to_cashout')
        batch_op.drop_column('time_model_version')