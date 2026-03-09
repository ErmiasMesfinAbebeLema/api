"""Seed default payment methods

Revision ID: seed_payment_methods
Revises: 7b2d8270ebe8
Create Date: 2026-03-07 17:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'seed_payment_methods'
down_revision = '7b2d8270ebe8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint on name column if not exists
    op.execute("""
        ALTER TABLE payment_methods ADD CONSTRAINT uq_payment_methods_name UNIQUE (name)
    """)
    
    # Insert default payment methods (will be skipped if already exists)
    op.execute("""
        INSERT INTO payment_methods (name, description, is_active, created_at, updated_at)
        VALUES 
            ('Cash', 'Cash payment', true, NOW(), NOW()),
            ('Bank Transfer', 'Direct bank transfer', true, NOW(), NOW()),
            ('Mobile Money', 'Mobile money transfer (M-Pesa, etc.)', true, NOW(), NOW()),
            ('Cheque', 'Cheque payment', true, NOW(), NOW()),
            ('Credit Card', 'Credit/Debit card payment', true, NOW(), NOW())
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    """Remove default payment methods"""
    op.execute("""
        DELETE FROM payment_methods 
        WHERE name IN ('Cash', 'Bank Transfer', 'Mobile Money', 'Cheque', 'Credit Card')
    """)
    
    # Remove unique constraint
    op.execute("""
        ALTER TABLE payment_methods DROP CONSTRAINT uq_payment_methods_name
    """)
