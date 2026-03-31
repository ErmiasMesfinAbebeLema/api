"""Add email_logs table

Revision ID: add_email_logs_table
Revises: notification_system
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_email_logs_table'
down_revision: Union[str, None] = 'notification_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        # Email Details
        sa.Column('recipient_email', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        # Email Content
        sa.Column('email_type', sa.String(50), nullable=False),
        sa.Column('template_name', sa.String(100), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        # Context/Meta
        sa.Column('context_data', sa.JSON(), nullable=True),
        sa.Column('related_user_id', sa.Integer(), nullable=True),
        sa.Column('related_entity_type', sa.String(50), nullable=True),
        sa.Column('related_entity_id', sa.Integer(), nullable=True),
        # Status Tracking
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_retry_at', sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
    )
    
    # Create indexes
    op.create_index('ix_email_logs_id', 'email_logs', ['id'])
    op.create_index('ix_email_logs_recipient_email', 'email_logs', ['recipient_email'])
    op.create_index('ix_email_logs_email_type', 'email_logs', ['email_type'])
    op.create_index('ix_email_logs_status', 'email_logs', ['status'])
    
    # Foreign key to users
    op.create_foreign_key(
        'fk_email_logs_user',
        'email_logs', 'users',
        ['related_user_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_email_logs_user', 'email_logs', type_='foreignkey')
    op.drop_index('ix_email_logs_status', table_name='email_logs')
    op.drop_index('ix_email_logs_email_type', table_name='email_logs')
    op.drop_index('ix_email_logs_recipient_email', table_name='email_logs')
    op.drop_index('ix_email_logs_id', table_name='email_logs')
    op.drop_table('email_logs')