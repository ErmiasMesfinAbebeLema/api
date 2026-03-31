"""Add new fields to users table

Revision ID: add_user_new_fields
Revises: add_email_logs_table
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_new_fields'
down_revision: Union[str, None] = 'add_email_logs_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new fields to users table
    op.add_column(
        'users',
        sa.Column('is_email_verified', sa.Boolean(), server_default='false', nullable=False)
    )
    op.add_column(
        'users',
        sa.Column('email_verified_at', sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'is_email_verified')