"""Add email log permissions to admin_permissions table

Revision ID: add_email_log_permissions_to_admin_perms
Revises: add_admin_permissions
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_email_log_perms'
down_revision: Union[str, None] = 'add_user_new_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email log permissions columns
    op.add_column(
        'admin_permissions',
        sa.Column('can_view_email_logs', sa.Boolean(), server_default='true', nullable=False)
    )
    op.add_column(
        'admin_permissions',
        sa.Column('can_edit_email_logs', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('admin_permissions', 'can_edit_email_logs')
    op.drop_column('admin_permissions', 'can_view_email_logs')