"""0003_intake_operational_fields

Revision ID: 0003_intake_operational_fields
Revises: 0002_hardened_schema
Create Date: 2026-09-11 13:08:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_intake_operational_fields'
down_revision: Union[str, None] = '0002_hardened_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add locality and provenance_mode to complaints table
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.add_column(sa.Column('locality', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('provenance_mode', sa.String(length=50), nullable=True, server_default='DIRECT_OFFICER_INPUT'))


def downgrade() -> None:
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.drop_column('provenance_mode')
        batch_op.drop_column('locality')
