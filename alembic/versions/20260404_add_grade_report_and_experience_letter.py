"""Add grade_report and experience_letter document types

Revision ID: add_grade_report_and_exp_letter
Revises: add_user_new_fields
Create Date: 2026-04-04 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_grade_report_and_exp_letter'
down_revision: Union[str, None] = 'add_email_log_perms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new values to the documenttype enum (uppercase to match existing values)
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'GRADE_REPORT'")
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'EXPERIENCE_LETTER'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values easily
    pass
