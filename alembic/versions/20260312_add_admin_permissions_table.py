"""Add admin_permissions table

Revision ID: add_admin_permissions
Revises: fix_invoice_status_case
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_admin_permissions'
down_revision = 'fix_invoice_status_case'  # Set this to your last migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add super_admin to userrole enum if not exists
    try:
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")
    except Exception:
        pass
    
    # Create admin_permissions table
    op.create_table(
        'admin_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        # User Management
        sa.Column('can_manage_users', sa.Boolean(), default=True),
        sa.Column('can_create_users', sa.Boolean(), default=True),
        sa.Column('can_edit_users', sa.Boolean(), default=True),
        sa.Column('can_delete_users', sa.Boolean(), default=True),
        # Student Management
        sa.Column('can_manage_students', sa.Boolean(), default=True),
        sa.Column('can_view_students', sa.Boolean(), default=True),
        sa.Column('can_create_students', sa.Boolean(), default=True),
        sa.Column('can_edit_students', sa.Boolean(), default=True),
        sa.Column('can_delete_students', sa.Boolean(), default=True),
        # Course Management
        sa.Column('can_manage_courses', sa.Boolean(), default=True),
        sa.Column('can_create_courses', sa.Boolean(), default=True),
        sa.Column('can_edit_courses', sa.Boolean(), default=True),
        sa.Column('can_delete_courses', sa.Boolean(), default=True),
        # Certificate Management
        sa.Column('can_manage_certificates', sa.Boolean(), default=True),
        sa.Column('can_create_certificates', sa.Boolean(), default=True),
        sa.Column('can_edit_certificates', sa.Boolean(), default=True),
        sa.Column('can_delete_certificates', sa.Boolean(), default=True),
        sa.Column('can_revoke_certificates', sa.Boolean(), default=True),
        # Enrollment Management
        sa.Column('can_manage_enrollments', sa.Boolean(), default=True),
        sa.Column('can_create_enrollments', sa.Boolean(), default=True),
        sa.Column('can_edit_enrollments', sa.Boolean(), default=True),
        sa.Column('can_delete_enrollments', sa.Boolean(), default=True),
        # Payment & Invoice Management
        sa.Column('can_manage_payments', sa.Boolean(), default=True),
        sa.Column('can_view_payments', sa.Boolean(), default=True),
        sa.Column('can_create_payments', sa.Boolean(), default=True),
        sa.Column('can_manage_invoices', sa.Boolean(), default=True),
        sa.Column('can_create_invoices', sa.Boolean(), default=True),
        sa.Column('can_edit_invoices', sa.Boolean(), default=True),
        sa.Column('can_delete_invoices', sa.Boolean(), default=True),
        # Document Management
        sa.Column('can_manage_documents', sa.Boolean(), default=True),
        sa.Column('can_view_documents', sa.Boolean(), default=True),
        sa.Column('can_upload_documents', sa.Boolean(), default=True),
        sa.Column('can_delete_documents', sa.Boolean(), default=True),
        # Reports
        sa.Column('can_view_reports', sa.Boolean(), default=True),
        sa.Column('can_export_reports', sa.Boolean(), default=True),
        # Instructor Management
        sa.Column('can_manage_instructors', sa.Boolean(), default=True),
        # Settings
        sa.Column('can_manage_settings', sa.Boolean(), default=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Add unique constraint on admin_id
    op.create_index('ix_admin_permissions_admin_id', 'admin_permissions', ['admin_id'], unique=True)
    
    # Add foreign key
    op.create_foreign_key(
        'fk_admin_permissions_admin_id',
        'admin_permissions', 'users',
        ['admin_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Add foreign key for updated_by
    op.create_foreign_key(
        'fk_admin_permissions_updated_by',
        'admin_permissions', 'users',
        ['updated_by'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_admin_permissions_updated_by', 'admin_permissions', type_='foreignkey')
    op.drop_constraint('fk_admin_permissions_admin_id', 'admin_permissions', type_='foreignkey')
    op.drop_index('ix_admin_permissions_admin_id', table_name='admin_permissions')
    op.drop_table('admin_permissions')
