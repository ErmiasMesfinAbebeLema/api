"""Fix invoice status enum case to uppercase

Revision ID: fix_invoice_status_case
Revises: seed_payment_methods
Create Date: 2026-03-08 13:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fix_invoice_status_case'
down_revision: Union[str, None] = 'seed_payment_methods'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, update existing data to uppercase (cast to text first, then back to enum)
    # Note: This assumes the enum values already exist in uppercase or will be added
    op.execute("UPDATE invoices SET status = status::text::invoicestatus WHERE status IS NOT NULL")
    
    # Add uppercase enum values if they don't exist
    # These are PostgreSQL-specific ALTER TYPE commands
    # Using separate statements to avoid asyncpg issues with DO blocks
    for value in ['DRAFT', 'SENT', 'PAID', 'COMPLETED', 'CANCELLED']:
        try:
            op.execute(f"ALTER TYPE invoicestatus ADD VALUE IF NOT EXISTS '{value}'")
        except Exception:
            # Ignore if value already exists
            pass


def downgrade() -> None:
    # Convert back to lowercase (for rollback)
    op.execute("UPDATE invoices SET status = LOWER(status::text)::invoicestatus WHERE status IS NOT NULL")
