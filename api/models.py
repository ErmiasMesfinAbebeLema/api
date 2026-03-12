from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime, Text, Enum as SQLEnum, ForeignKey, Date, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models"""
    pass


# ─────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    INSTRUCTOR = "instructor"
    STUDENT = "student"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class EnrollmentStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    GRADUATED = "graduated"
    SUSPENDED = "suspended"
    WITHDRAWN = "withdrawn"


class CourseEnrollmentStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"


class CertificateStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    REFUNDED = "refunded"
    FAILED = "failed"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    PAID = "PAID"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DocumentType(str, enum.Enum):
    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    CONTRACT = "contract"
    PROFILE_PHOTO = "profile_photo"
    GRADE_8_CERTIFICATE = "grade_8_certificate"
    GRADE_10_CERTIFICATE = "grade_10_certificate"
    GRADE_12_CERTIFICATE = "grade_12_certificate"
    ETHIOPIAN_HIGHER_EDUCATION_ENTRANCE = "ethiopian_higher_education_entrance"


# ─────────────────────────────────────────────────────────
# User Model
# ─────────────────────────────────────────────────────────

class User(Base):
    """User model for authentication and authorization"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    profile_photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        default=UserRole.STUDENT,
        index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationship
    student: Mapped[Optional["Student"]] = relationship("Student", back_populates="user", uselist=False)
    admin_permissions: Mapped[Optional["AdminPermission"]] = relationship(
        "AdminPermission", 
        back_populates="admin", 
        uselist=False, 
        cascade="all, delete-orphan",
        foreign_keys="AdminPermission.admin_id"
    )


# ─────────────────────────────────────────────────────────
# Admin Permission Model
# ─────────────────────────────────────────────────────────

class AdminPermission(Base):
    """Admin permission model - stores custom permissions for each admin"""
    __tablename__ = "admin_permissions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    admin_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id"), 
        unique=True, 
        nullable=False, 
        index=True
    )
    
    # User Management
    can_manage_users: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_users: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_users: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delete_users: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Student Management
    can_manage_students: Mapped[bool] = mapped_column(Boolean, default=True)
    can_view_students: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_students: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_students: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delete_students: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Course Management
    can_manage_courses: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_courses: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_courses: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delete_courses: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Certificate Management
    can_manage_certificates: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_certificates: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_certificates: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delete_certificates: Mapped[bool] = mapped_column(Boolean, default=True)
    can_revoke_certificates: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Enrollment Management
    can_manage_enrollments: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_enrollments: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_enrollments: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delete_enrollments: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Payment & Invoice Management
    can_manage_payments: Mapped[bool] = mapped_column(Boolean, default=True)
    can_view_payments: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_payments: Mapped[bool] = mapped_column(Boolean, default=True)
    can_manage_invoices: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_invoices: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_invoices: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delete_invoices: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Document Management
    can_manage_documents: Mapped[bool] = mapped_column(Boolean, default=True)
    can_view_documents: Mapped[bool] = mapped_column(Boolean, default=True)
    can_upload_documents: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delete_documents: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Reports
    can_view_reports: Mapped[bool] = mapped_column(Boolean, default=True)
    can_export_reports: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Instructor Management
    can_manage_instructors: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Settings
    can_manage_settings: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationship
    admin: Mapped["User"] = relationship("User", back_populates="admin_permissions", foreign_keys=[admin_id])
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])


# ─────────────────────────────────────────────────────────
# Student Model
# ─────────────────────────────────────────────────────────

class Student(Base):
    """Student model with extended profile information"""
    __tablename__ = "students"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    # Personal Information
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[Gender]] = mapped_column(SQLEnum(Gender), nullable=True)
    
    # Emergency Contact
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    emergency_contact_relation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Enrollment Information
    enrollment_status: Mapped[EnrollmentStatus] = mapped_column(
        SQLEnum(EnrollmentStatus),
        default=EnrollmentStatus.PENDING,
        index=True
    )
    enrollment_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    graduation_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    program_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    referral_source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="student")
    documents: Mapped[list["StudentDocument"]] = relationship("StudentDocument", back_populates="student", cascade="all, delete-orphan")
    enrollments: Mapped[list["Enrollment"]] = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    certificates: Mapped[list["Certificate"]] = relationship("Certificate", back_populates="student", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="student", cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="student", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────
# Student Document Model
# ─────────────────────────────────────────────────────────

class StudentDocument(Base):
    """Student document model for storing uploaded documents"""
    __tablename__ = "student_documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    document_type: Mapped[DocumentType] = mapped_column(SQLEnum(DocumentType), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer)  # Size in bytes
    mime_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationship
    student: Mapped["Student"] = relationship("Student", back_populates="documents")
    uploader: Mapped[Optional["User"]] = relationship("User")


# ─────────────────────────────────────────────────────────
# Course Model
# ─────────────────────────────────────────────────────────

class Course(Base):
    """Training course model"""
    __tablename__ = "courses"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_hours: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    duration_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    enrollments: Mapped[list["Enrollment"]] = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
    certificates: Mapped[list["Certificate"]] = relationship("Certificate", back_populates="course")


# ─────────────────────────────────────────────────────────
# Enrollment Model
# ─────────────────────────────────────────────────────────

class Enrollment(Base):
    """Student course enrollment"""
    __tablename__ = "enrollments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    fee: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[CourseEnrollmentStatus] = mapped_column(
        SQLEnum(CourseEnrollmentStatus),
        default=CourseEnrollmentStatus.PENDING,
        index=True
    )
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    start_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    completion_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    grade: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    attendance_percentage: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="enrollments")
    course: Mapped["Course"] = relationship("Course", back_populates="enrollments")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="enrollment")


# ─────────────────────────────────────────────────────────
# Certificate Template Model
# ─────────────────────────────────────────────────────────

class CertificateTemplate(Base):
    """Certificate template model"""
    __tablename__ = "certificate_templates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    css_styles: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    background_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    certificates: Mapped[list["Certificate"]] = relationship("Certificate", back_populates="template")
    creator: Mapped[Optional["User"]] = relationship("User")


# ─────────────────────────────────────────────────────────
# Certificate Model
# ─────────────────────────────────────────────────────────

class Certificate(Base):
    """Issued certificate model"""
    __tablename__ = "certificates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    certificate_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("certificate_templates.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False)
    issue_date: Mapped[Date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    cert_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[CertificateStatus] = mapped_column(
        SQLEnum(CertificateStatus),
        default=CertificateStatus.ACTIVE,
        index=True
    )
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revoked_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    issued_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="certificates")
    template: Mapped["CertificateTemplate"] = relationship("CertificateTemplate", back_populates="certificates")
    course: Mapped["Course"] = relationship("Course", back_populates="certificates")
    issuer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[issued_by])
    revoker: Mapped[Optional["User"]] = relationship("User", foreign_keys=[revoked_by])


# ─────────────────────────────────────────────────────────
# Payment Method Model
# ─────────────────────────────────────────────────────────

class PaymentMethod(Base):
    """Payment method lookup table"""
    __tablename__ = "payment_methods"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )


# ─────────────────────────────────────────────────────────
# Payment Model
# ─────────────────────────────────────────────────────────

class Payment(Base):
    """Payment transactions"""
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    enrollment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("enrollments.id"), nullable=True, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    payment_date: Mapped[Date] = mapped_column(Date, nullable=False)
    payment_method_id: Mapped[int] = mapped_column(Integer, ForeignKey("payment_methods.id"), nullable=False)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus),
        default=PaymentStatus.COMPLETED,
        index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="payments")
    enrollment: Mapped[Optional["Enrollment"]] = relationship("Enrollment", back_populates="payments")
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice", back_populates="payments")
    payment_method: Mapped["PaymentMethod"] = relationship("PaymentMethod")
    recorder: Mapped[Optional["User"]] = relationship("User", foreign_keys=[recorded_by])


# ─────────────────────────────────────────────────────────
# Invoice Model
# ─────────────────────────────────────────────────────────

class Invoice(Base):
    """Invoice for student payments"""
    __tablename__ = "invoices"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    issue_date: Mapped[Date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    grand_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    status: Mapped[InvoiceStatus] = mapped_column(
        SQLEnum(InvoiceStatus, values_callable=lambda x: [e.value for e in x]),
        default=InvoiceStatus.DRAFT,
        index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship("InvoiceItem", back_populates="invoice")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="invoice")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


# ─────────────────────────────────────────────────────────
# Invoice Item Model
# ─────────────────────────────────────────────────────────

class InvoiceItem(Base):
    """Invoice line items"""
    __tablename__ = "invoice_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    enrollment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("enrollments.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")
    enrollment: Mapped[Optional["Enrollment"]] = relationship("Enrollment")
