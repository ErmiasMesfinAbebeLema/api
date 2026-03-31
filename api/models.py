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


class AttendanceStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PRESENT = "present"
    ABSENT = "absent"


class InstructorCourse(Base):
    """Instructor-Course assignment model"""
    __tablename__ = "instructor_courses"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instructor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    assigned_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    instructor: Mapped["User"] = relationship("User", foreign_keys=[instructor_id])
    course: Mapped["Course"] = relationship("Course")
    assigned_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_by])


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
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
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
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", 
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Notification.user_id"
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
    
    # Email Logs
    can_view_email_logs: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_email_logs: Mapped[bool] = mapped_column(Boolean, default=False)
    
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
# Attendance Model
# ─────────────────────────────────────────────────────────

class Attendance(Base):
    """Attendance tracking for students in courses"""
    __tablename__ = "attendances"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    instructor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    time_slot: Mapped[int] = mapped_column(Integer, nullable=False)  # Hour (2-23)
    status: Mapped[AttendanceStatus] = mapped_column(
        SQLEnum(AttendanceStatus),
        default=AttendanceStatus.PENDING,
        index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    student: Mapped["Student"] = relationship("Student")
    course: Mapped["Course"] = relationship("Course")
    instructor: Mapped[Optional["User"]] = relationship("User")


class InstructorSchedule(Base):
    """Instructor planned schedule for attendance"""
    __tablename__ = "instructor_schedules"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instructor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[int] = mapped_column(Integer, nullable=False)  # Hour (2-23)
    end_time: Mapped[int] = mapped_column(Integer, nullable=False)  # Hour (2-23)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    instructor: Mapped["User"] = relationship("User")
    course: Mapped[Optional["Course"]] = relationship("Course")


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


# ─────────────────────────────────────────────────────────
# Notification Models
# ─────────────────────────────────────────────────────────

class NotificationType(str, enum.Enum):
    """Notification type enum"""
    ENROLLMENT = "enrollment"
    PAYMENT = "payment"
    CERTIFICATE = "certificate"
    ATTENDANCE = "attendance"
    ANNOUNCEMENT = "announcement"
    SYSTEM = "system"
    MESSAGE = "message"
    INSTRUCTOR = "instructor"  # Instructor-related notifications


class Notification(Base):
    """Notification model for user notifications"""
    __tablename__ = "notifications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default=NotificationType.SYSTEM.value)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="notifications")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


class EmailLog(Base):
    """Log of all sent emails"""
    __tablename__ = "email_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Email Details
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Email Content
    email_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    template_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Context/Meta
    context_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    related_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Status Tracking
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[related_user_id])
