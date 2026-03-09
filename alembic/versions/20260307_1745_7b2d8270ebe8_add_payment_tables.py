"""add_payment_tables

Revision ID: 7b2d8270ebe8
Revises: 17a4e103a30c
Create Date: 2026-03-07 17:45:36.557267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b2d8270ebe8'
down_revision: Union[str, None] = '17a4e103a30c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The fee column is now created in create_all_tables migration
    # This migration is kept for historical purposes
    pass


def downgrade() -> None:
    # The fee column is now created in create_all_tables migration
    pass
