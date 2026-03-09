"""Create all remaining tables

Revision ID: create_all_tables
Revises: 001_initial
Create Date: 2026-03-09

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import ForeignKey, Integer, String, Text, Boolean, DateTime, Date, Numeric, JSON, Enum as SQLEnum
import enum


# Revision identifiers
revision: str = 'create_all_tables'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enums (matching models.py)
class DocumentType(str, enum.Enum):
    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    BIRTH_CERTIFICATE = "birth_certificate"
    PHOTO = "photo"
    CONTRACT = "contract"
    OTHER = "other"


class CourseEnrollmentStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CertificateStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    PAID = "PAID"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


def upgrade() -> None:
    # Create enum types - use create_type=True to ensure they're created
    document_type = SQLEnum(DocumentType, name='documenttype', create_type=True)
    course_enrollment_status = SQLEnum(CourseEnrollmentStatus, name='courseenrollmentstatus', create_type=True)
    certificate_status = SQLEnum(CertificateStatus, name='certificatestatus', create_type=True)
    payment_status = SQLEnum(PaymentStatus, name='paymentstatus', create_type=True)
    invoice_status = SQLEnum(InvoiceStatus, name='invoicestatus', create_type=True)
    op.create_table(
        'student_documents',
        sa.Column('id', Integer, primary_key=True, index=True),
        sa.Column('student_id', Integer, ForeignKey('students.id'), nullable=False, index=True),
        sa.Column('document_type', document_type, nullable=False, index=True),
        sa.Column('file_name', String(255)),
        sa.Column('file_path', String(500)),
        sa.Column('file_size', Integer),
        sa.Column('mime_type', String(100)),
        sa.Column('description', Text, nullable=True),
        sa.Column('uploaded_by', Integer, ForeignKey('users.id'), nullable=True),
        sa.Column('uploaded_at', DateTime, nullable=False),
        sa.Column('is_active', Boolean, default=True),
    )
    op.create_index(op.f('ix_student_documents_id'), 'student_documents', ['id'])
    op.create_index(op.f('ix_student_documents_student_id'), 'student_documents', ['student_id'])
    op.create_index(op.f('ix_student_documents_document_type'), 'student_documents', ['document_type'])

    # === Courses Table ===
    op.create_table(
        'courses',
        sa.Column('id', Integer, primary_key=True, index=True),
        sa.Column('name', String(255), nullable=False),
        sa.Column('description', Text, nullable=True),
        sa.Column('duration_hours', Numeric(10, 2), nullable=True),
        sa.Column('duration_text', String(100), nullable=True),
        sa.Column('level', String(50), nullable=True),
        sa.Column('is_active', Boolean, default=True),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    op.create_index(op.f('ix_courses_id'), 'courses', ['id'])
    op.create_index(op.f('ix_courses_name'), 'courses', ['name'])

    # === Enrollments Table ===
    course_enrollment_status = SQLEnum(CourseEnrollmentStatus, name='courseenrollmentstatus', create_type=True)
    op.create_table(
        'enrollments',
        sa.Column('id', Integer, primary_key=True, index=True),
        sa.Column('student_id', Integer, ForeignKey('students.id'), nullable=False, index=True),
        sa.Column('course_id', Integer, ForeignKey('courses.id'), nullable=False, index=True),
        sa.Column('fee', Numeric(10, 2), nullable=True),
        sa.Column('status', course_enrollment_status, default=CourseEnrollmentStatus.PENDING, index=True),
        sa.Column('enrolled_at', DateTime, nullable=False),
        sa.Column('start_date', Date, nullable=True),
        sa.Column('completion_date', Date, nullable=True),
        sa.Column('grade', String(10), nullable=True),
        sa.Column('attendance_percentage', Numeric(5, 2), nullable=True),
        sa.Column('notes', Text, nullable=True),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    op.create_index(op.f('ix_enrollments_id'), 'enrollments', ['id'])
    op.create_index(op.f('ix_enrollments_student_id'), 'enrollments', ['student_id'])
    op.create_index(op.f('ix_enrollments_course_id'), 'enrollments', ['course_id'])
    op.create_index(op.f('ix_enrollments_status'), 'enrollments', ['status'])

    # === Certificate Templates Table ===
    op.create_table(
        'certificate_templates',
        sa.Column('id', Integer, primary_key=True, index=True),
        sa.Column('name', String(255), nullable=False),
        sa.Column('html_content', Text, nullable=False),
        sa.Column('css_styles', Text, nullable=True),
        sa.Column('background_image_url', String(500), nullable=True),
        sa.Column('is_active', Boolean, default=True),
        sa.Column('created_by', Integer, ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    op.create_index(op.f('ix_certificate_templates_id'), 'certificate_templates', ['id'])
    op.create_index(op.f('ix_certificate_templates_name'), 'certificate_templates', ['name'])

    # === Certificates Table ===
    certificate_status = SQLEnum(CertificateStatus, name='certificatestatus', create_type=True)
    op.create_table(
        'certificates',
        sa.Column('id', Integer, primary_key=True, index=True),
        sa.Column('certificate_number', String(50), unique=True, nullable=False, index=True),
        sa.Column('student_id', Integer, ForeignKey('students.id'), nullable=False, index=True),
        sa.Column('template_id', Integer, ForeignKey('certificate_templates.id'), nullable=False),
        sa.Column('course_id', Integer, ForeignKey('courses.id'), nullable=False),
        sa.Column('issue_date', Date, nullable=False),
        sa.Column('expiry_date', Date, nullable=True),
        sa.Column('cert_metadata', JSON, nullable=True),
        sa.Column('pdf_url', String(500), nullable=True),
        sa.Column('status', certificate_status, default=CertificateStatus.ACTIVE, index=True),
        sa.Column('revocation_reason', Text, nullable=True),
        sa.Column('revoked_by', Integer, ForeignKey('users.id'), nullable=True),
        sa.Column('revoked_at', DateTime, nullable=True),
        sa.Column('issued_by', Integer, ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    op.create_index(op.f('ix_certificates_id'), 'certificates', ['id'])
    op.create_index(op.f('ix_certificates_certificate_number'), 'certificates', ['certificate_number'], unique=True)
    op.create_index(op.f('ix_certificates_student_id'), 'certificates', ['student_id'])
    op.create_index(op.f('ix_certificates_status'), 'certificates', ['status'])

    # === Payment Methods Table ===
    op.create_table(
        'payment_methods',
        sa.Column('id', Integer, primary_key=True, index=True),
        sa.Column('name', String(100), nullable=False),
        sa.Column('description', Text, nullable=True),
        sa.Column('is_active', Boolean, default=True),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    op.create_index(op.f('ix_payment_methods_id'), 'payment_methods', ['id'])
    op.create_index(op.f('ix_payment_methods_name'), 'payment_methods', ['name'])

    # === Payments Table ===
    payment_status = SQLEnum(PaymentStatus, name='paymentstatus', create_type=True)
    op.create_table(
        'payments',
        sa.Column('id', Integer, primary_key=True, index=True),
        sa.Column('student_id', Integer, ForeignKey('students.id'), nullable=False, index=True),
        sa.Column('enrollment_id', Integer, ForeignKey('enrollments.id'), nullable=True, index=True),
        sa.Column('invoice_id', Integer, ForeignKey('invoices.id'), nullable=True, index=True),
        sa.Column('amount', Numeric(10, 2), nullable=False),
        sa.Column('payment_date', Date, nullable=False),
        sa.Column('payment_method_id', Integer, ForeignKey('payment_methods.id'), nullable=False),
        sa.Column('transaction_reference', String(255), nullable=True),
        sa.Column('status', payment_status, default=PaymentStatus.COMPLETED, index=True),
        sa.Column('notes', Text, nullable=True),
        sa.Column('recorded_by', Integer, ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'])
    op.create_index(op.f('ix_payments_student_id'), 'payments', ['student_id'])
    op.create_index(op.f('ix_payments_enrollment_id'), 'payments', ['enrollment_id'])
    op.create_index(op.f('ix_payments_invoice_id'), 'payments', ['invoice_id'])
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'])

    # === Invoices Table ===
    invoice_status = SQLEnum(InvoiceStatus, name='invoicestatus', create_type=True)
    op.create_table(
        'invoices',
        sa.Column('id', Integer, primary_key=True, index=True),
        sa.Column('invoice_number', String(50), unique=True, nullable=False, index=True),
        sa.Column('student_id', Integer, ForeignKey('students.id'), nullable=False, index=True),
        sa.Column('issue_date', Date, nullable=False),
        sa.Column('due_date', Date, nullable=True),
        sa.Column('total_amount', Numeric(10, 2), nullable=False, default=0),
        sa.Column('discount_amount', Numeric(10, 2), nullable=False, default=0),
        sa.Column('tax_amount', Numeric(10, 2), nullable=False, default=0),
        sa.Column('grand_total', Numeric(10, 2), nullable=False, default=0),
        sa.Column('status', invoice_status, default=InvoiceStatus.DRAFT, index=True),
        sa.Column('notes', Text, nullable=True),
        sa.Column('pdf_url', String(500), nullable=True),
        sa.Column('created_by', Integer, ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    op.create_index(op.f('ix_invoices_id'), 'invoices', ['id'])
    op.create_index(op.f('ix_invoices_invoice_number'), 'invoices', ['invoice_number'], unique=True)
    op.create_index(op.f('ix_invoices_student_id'), 'invoices', ['student_id'])
    op.create_index(op.f('ix_invoices_status'), 'invoices', ['status'])

    # === Invoice Items Table ===
    op.create_table(
        'invoice_items',
        sa.Column('id', Integer, primary_key=True, index=True),
        sa.Column('invoice_id', Integer, ForeignKey('invoices.id'), nullable=False, index=True),
        sa.Column('enrollment_id', Integer, ForeignKey('enrollments.id'), nullable=True),
        sa.Column('description', Text, nullable=False),
        sa.Column('quantity', Integer, nullable=False, default=1),
        sa.Column('unit_price', Numeric(10, 2), nullable=False),
        sa.Column('amount', Numeric(10, 2), nullable=False),
        sa.Column('created_at', DateTime, nullable=False),
        sa.Column('updated_at', DateTime, nullable=False),
    )
    op.create_index(op.f('ix_invoice_items_id'), 'invoice_items', ['id'])
    op.create_index(op.f('ix_invoice_items_invoice_id'), 'invoice_items', ['invoice_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('invoice_items')
    op.drop_table('invoices')
    op.drop_table('payments')
    op.drop_table('payment_methods')
    op.drop_table('certificates')
    op.drop_table('certificate_templates')
    op.drop_table('enrollments')
    op.drop_table('courses')
    op.drop_table('student_documents')
