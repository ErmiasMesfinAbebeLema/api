"""Add notifications table

Revision ID: notification_system
Revises: add_instructor_schedules
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'notification_system'
down_revision: Union[str, None] = 'add_instructor_schedules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notification types enum
    notification_type_enum = sa.Enum(
        'enrollment', 'payment', 'certificate', 'attendance', 
        'announcement', 'system', 'message',
        name='notificationtype'
    )
    notification_type_enum.create(op.get_bind())
    
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(50), nullable=False, server_default='system'),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('link', sa.String(255), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_notifications_user'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_notifications_created_by'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])


def downgrade() -> None:
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_table('notifications')
    
    # Drop enum
    notification_type_enum = sa.Enum(
        'enrollment', 'payment', 'certificate', 'attendance', 
        'announcement', 'system', 'message',
        name='notificationtype'
    )
    notification_type_enum.drop(op.get_bind())
