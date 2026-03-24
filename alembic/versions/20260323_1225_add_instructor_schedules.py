"""Add instructor_schedules table

Revision ID: add_instructor_schedules
Revises: 41b2082fb3f8
Create Date: 2026-03-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_instructor_schedules'
down_revision: Union[str, None] = '41b2082fb3f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'instructor_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instructor_id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Integer(), nullable=False),
        sa.Column('end_time', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['instructor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_instructor_schedules_instructor_id', 'instructor_schedules', ['instructor_id'])
    op.create_index('ix_instructor_schedules_course_id', 'instructor_schedules', ['course_id'])
    op.create_index('ix_instructor_schedules_date', 'instructor_schedules', ['date'])


def downgrade() -> None:
    op.drop_index('ix_instructor_schedules_date', table_name='instructor_schedules')
    op.drop_index('ix_instructor_schedules_course_id', table_name='instructor_schedules')
    op.drop_index('ix_instructor_schedules_instructor_id', table_name='instructor_schedules')
    op.drop_table('instructor_schedules')
