"""Add attendance table

Revision ID: 41b2082fb3f8
Revises: add_admin_permissions
Create Date: 2026-03-23 12:21:56.103097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '41b2082fb3f8'
down_revision: Union[str, None] = 'add_admin_permissions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create attendance status enum
    attendance_status = postgresql.ENUM(
        'pending', 'approved', 'rejected', 'present', 'absent',
        name='attendancestatus',
        create_type=False
    )
    attendance_status.create(op.get_bind(), checkfirst=True)
    
    # Create attendances table
    op.create_table(
        'attendances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('instructor_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('time_slot', sa.Integer(), nullable=False),
        sa.Column('status', attendance_status, nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_attendances_id', 'attendances', ['id'])
    op.create_index('ix_attendances_student_id', 'attendances', ['student_id'])
    op.create_index('ix_attendances_course_id', 'attendances', ['course_id'])
    op.create_index('ix_attendances_instructor_id', 'attendances', ['instructor_id'])
    op.create_index('ix_attendances_date', 'attendances', ['date'])
    op.create_index('ix_attendances_status', 'attendances', ['status'])
    
    # Add foreign key constraints
    op.create_foreign_key(
        'fk_attendances_student_id',
        'attendances', 'students',
        ['student_id'], ['id']
    )
    op.create_foreign_key(
        'fk_attendances_course_id',
        'attendances', 'courses',
        ['course_id'], ['id']
    )
    op.create_foreign_key(
        'fk_attendances_instructor_id',
        'attendances', 'users',
        ['instructor_id'], ['id']
    )


def downgrade() -> None:
    # Drop foreign keys
    op.drop_constraint('fk_attendances_instructor_id', 'attendances', type_='foreignkey')
    op.drop_constraint('fk_attendances_course_id', 'attendances', type_='foreignkey')
    op.drop_constraint('fk_attendances_student_id', 'attendances', type_='foreignkey')
    
    # Drop indexes
    op.drop_index('ix_attendances_status', table_name='attendances')
    op.drop_index('ix_attendances_date', table_name='attendances')
    op.drop_index('ix_attendances_instructor_id', table_name='attendances')
    op.drop_index('ix_attendances_course_id', table_name='attendances')
    op.drop_index('ix_attendances_student_id', table_name='attendances')
    op.drop_index('ix_attendances_id', table_name='attendances')
    
    # Drop table
    op.drop_table('attendances')
    
    # Drop enum
    attendance_status = postgresql.ENUM(
        'pending', 'approved', 'rejected', 'present', 'absent',
        name='attendancestatus'
    )
    attendance_status.drop(op.get_bind(), checkfirst=True)
