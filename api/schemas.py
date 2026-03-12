from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, date
from api.models import UserRole, Gender, EnrollmentStatus, DocumentType, CourseEnrollmentStatus, CertificateStatus, PaymentStatus, InvoiceStatus, AdminPermission


# ─────────────────────────────────────────────────────────
# User Schemas
# ─────────────────────────────────────────────────────────

class UserBase(BaseModel):
    """Base user schema"""
    email: Optional[EmailStr] = None
    full_name: str = Field(..., min_length=2, max_length=200)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    role: UserRole = UserRole.STUDENT


class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=6)
    profile_photo_url: Optional[str] = None
    bio: Optional[str] = None


class UserUpdate(BaseModel):
    """Schema for updating user"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=200)
    phone: Optional[str] = None
    profile_photo_url: Optional[str] = None
    bio: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    profile_photo_url: Optional[str] = None
    bio: Optional[str] = None
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────
# Auth Schemas
# ─────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Login request schema - accepts either email or phone"""
    identifier: str = Field(..., description="Email or phone number")
    password: str


class LoginResponse(BaseModel):
    """Login response schema"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RegisterRequest(UserCreate):
    """Registration request schema"""
    pass


# ─────────────────────────────────────────────────────────
# Permission Schemas
# ─────────────────────────────────────────────────────────

class Permission(BaseModel):
    """Permission schema - for backward compatibility"""
    can_manage_users: bool = False
    can_manage_students: bool = False
    can_manage_courses: bool = False
    can_manage_certificates: bool = False
    can_view_reports: bool = False
    can_manage_instructors: bool = False


class AdminPermissionSchema(BaseModel):
    """Admin permission schema - detailed permissions for each admin"""
    # User Management
    can_manage_users: bool = True
    can_create_users: bool = True
    can_edit_users: bool = True
    can_delete_users: bool = True
    
    # Student Management
    can_manage_students: bool = True
    can_view_students: bool = True
    can_create_students: bool = True
    can_edit_students: bool = True
    can_delete_students: bool = True
    
    # Course Management
    can_manage_courses: bool = True
    can_create_courses: bool = True
    can_edit_courses: bool = True
    can_delete_courses: bool = True
    
    # Certificate Management
    can_manage_certificates: bool = True
    can_create_certificates: bool = True
    can_edit_certificates: bool = True
    can_delete_certificates: bool = True
    can_revoke_certificates: bool = True
    
    # Enrollment Management
    can_manage_enrollments: bool = True
    can_create_enrollments: bool = True
    can_edit_enrollments: bool = True
    can_delete_enrollments: bool = True
    
    # Payment & Invoice Management
    can_manage_payments: bool = True
    can_view_payments: bool = True
    can_create_payments: bool = True
    can_manage_invoices: bool = True
    can_create_invoices: bool = True
    can_edit_invoices: bool = True
    can_delete_invoices: bool = True
    
    # Document Management
    can_manage_documents: bool = True
    can_view_documents: bool = True
    can_upload_documents: bool = True
    can_delete_documents: bool = True
    
    # Reports
    can_view_reports: bool = True
    can_export_reports: bool = True
    
    # Instructor Management
    can_manage_instructors: bool = True
    
    # Settings
    can_manage_settings: bool = True


class AdminPermissionUpdate(BaseModel):
    """Schema for updating admin permissions"""
    # User Management
    can_manage_users: Optional[bool] = None
    can_create_users: Optional[bool] = None
    can_edit_users: Optional[bool] = None
    can_delete_users: Optional[bool] = None
    
    # Student Management
    can_manage_students: Optional[bool] = None
    can_view_students: Optional[bool] = None
    can_create_students: Optional[bool] = None
    can_edit_students: Optional[bool] = None
    can_delete_students: Optional[bool] = None
    
    # Course Management
    can_manage_courses: Optional[bool] = None
    can_create_courses: Optional[bool] = None
    can_edit_courses: Optional[bool] = None
    can_delete_courses: Optional[bool] = None
    
    # Certificate Management
    can_manage_certificates: Optional[bool] = None
    can_create_certificates: Optional[bool] = None
    can_edit_certificates: Optional[bool] = None
    can_delete_certificates: Optional[bool] = None
    can_revoke_certificates: Optional[bool] = None
    
    # Enrollment Management
    can_manage_enrollments: Optional[bool] = None
    can_create_enrollments: Optional[bool] = None
    can_edit_enrollments: Optional[bool] = None
    can_delete_enrollments: Optional[bool] = None
    
    # Payment & Invoice Management
    can_manage_payments: Optional[bool] = None
    can_view_payments: Optional[bool] = None
    can_create_payments: Optional[bool] = None
    can_manage_invoices: Optional[bool] = None
    can_create_invoices: Optional[bool] = None
    can_edit_invoices: Optional[bool] = None
    can_delete_invoices: Optional[bool] = None
    
    # Document Management
    can_manage_documents: Optional[bool] = None
    can_view_documents: Optional[bool] = None
    can_upload_documents: Optional[bool] = None
    can_delete_documents: Optional[bool] = None
    
    # Reports
    can_view_reports: Optional[bool] = None
    can_export_reports: Optional[bool] = None
    
    # Instructor Management
    can_manage_instructors: Optional[bool] = None
    
    # Settings
    can_manage_settings: Optional[bool] = None


class AdminPermissionResponse(AdminPermissionSchema):
    """Schema for admin permission response"""
    id: int
    admin_id: int
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True


def get_permissions(role: UserRole, admin_permission: Optional[AdminPermission] = None) -> Permission:
    """Get permissions based on role - backward compatible"""
    if role == UserRole.SUPER_ADMIN:
        # Super admin has all permissions
        return Permission(
            can_manage_users=True,
            can_manage_students=True,
            can_manage_courses=True,
            can_manage_certificates=True,
            can_view_reports=True,
            can_manage_instructors=True,
        )
    elif role == UserRole.ADMIN:
        # Check if there's custom permission set for this admin
        if admin_permission:
            # Return custom permissions
            return Permission(
                can_manage_users=admin_permission.can_manage_users,
                can_manage_students=admin_permission.can_manage_students,
                can_manage_courses=admin_permission.can_manage_courses,
                can_manage_certificates=admin_permission.can_manage_certificates,
                can_view_reports=admin_permission.can_view_reports,
                can_manage_instructors=admin_permission.can_manage_instructors,
            )
        # Default admin permissions
        return Permission(
            can_manage_users=True,
            can_manage_students=True,
            can_manage_courses=True,
            can_manage_certificates=True,
            can_view_reports=True,
            can_manage_instructors=True,
        )
    elif role == UserRole.INSTRUCTOR:
        return Permission(
            can_manage_students=True,
            can_manage_courses=True,
            can_manage_certificates=True,
            can_view_reports=True,
            can_manage_instructors=False,
        )
    else:  # STUDENT
        return Permission()


def get_detailed_permissions(role: UserRole, admin_permission: Optional[AdminPermission] = None) -> AdminPermissionSchema:
    """Get detailed permissions based on role"""
    if role == UserRole.SUPER_ADMIN:
        # Super admin has all permissions
        return AdminPermissionSchema()
    elif role == UserRole.ADMIN:
        # Check if there's custom permission set for this admin
        if admin_permission:
            return AdminPermissionSchema(
                can_manage_users=admin_permission.can_manage_users,
                can_create_users=admin_permission.can_create_users,
                can_edit_users=admin_permission.can_edit_users,
                can_delete_users=admin_permission.can_delete_users,
                can_manage_students=admin_permission.can_manage_students,
                can_view_students=admin_permission.can_view_students,
                can_create_students=admin_permission.can_create_students,
                can_edit_students=admin_permission.can_edit_students,
                can_delete_students=admin_permission.can_delete_students,
                can_manage_courses=admin_permission.can_manage_courses,
                can_create_courses=admin_permission.can_create_courses,
                can_edit_courses=admin_permission.can_edit_courses,
                can_delete_courses=admin_permission.can_delete_courses,
                can_manage_certificates=admin_permission.can_manage_certificates,
                can_create_certificates=admin_permission.can_create_certificates,
                can_edit_certificates=admin_permission.can_edit_certificates,
                can_delete_certificates=admin_permission.can_delete_certificates,
                can_revoke_certificates=admin_permission.can_revoke_certificates,
                can_manage_enrollments=admin_permission.can_manage_enrollments,
                can_create_enrollments=admin_permission.can_create_enrollments,
                can_edit_enrollments=admin_permission.can_edit_enrollments,
                can_delete_enrollments=admin_permission.can_delete_enrollments,
                can_manage_payments=admin_permission.can_manage_payments,
                can_view_payments=admin_permission.can_view_payments,
                can_create_payments=admin_permission.can_create_payments,
                can_manage_invoices=admin_permission.can_manage_invoices,
                can_create_invoices=admin_permission.can_create_invoices,
                can_edit_invoices=admin_permission.can_edit_invoices,
                can_delete_invoices=admin_permission.can_delete_invoices,
                can_manage_documents=admin_permission.can_manage_documents,
                can_view_documents=admin_permission.can_view_documents,
                can_upload_documents=admin_permission.can_upload_documents,
                can_delete_documents=admin_permission.can_delete_documents,
                can_view_reports=admin_permission.can_view_reports,
                can_export_reports=admin_permission.can_export_reports,
                can_manage_instructors=admin_permission.can_manage_instructors,
                can_manage_settings=admin_permission.can_manage_settings,
            )
        # Default admin permissions (all true)
        return AdminPermissionSchema()
    elif role == UserRole.INSTRUCTOR:
        return AdminPermissionSchema(
            can_manage_students=True,
            can_view_students=True,
            can_create_students=False,
            can_edit_students=True,
            can_delete_students=False,
            can_manage_courses=True,
            can_create_courses=False,
            can_edit_courses=True,
            can_delete_courses=False,
            can_manage_certificates=True,
            can_create_certificates=True,
            can_edit_certificates=False,
            can_delete_certificates=False,
            can_revoke_certificates=False,
            can_manage_enrollments=True,
            can_create_enrollments=True,
            can_edit_enrollments=True,
            can_delete_enrollments=False,
            can_manage_payments=False,
            can_view_payments=False,
            can_create_payments=False,
            can_manage_invoices=False,
            can_create_invoices=False,
            can_edit_invoices=False,
            can_delete_invoices=False,
            can_manage_documents=False,
            can_view_documents=True,
            can_upload_documents=False,
            can_delete_documents=False,
            can_view_reports=True,
            can_export_reports=False,
            can_manage_instructors=False,
            can_manage_settings=False,
        )
    else:  # STUDENT
        return AdminPermissionSchema(
            can_manage_users=False,
            can_create_users=False,
            can_edit_users=False,
            can_delete_users=False,
            can_manage_students=False,
            can_view_students=False,
            can_create_students=False,
            can_edit_students=False,
            can_delete_students=False,
            can_manage_courses=False,
            can_create_courses=False,
            can_edit_courses=False,
            can_delete_courses=False,
            can_manage_certificates=False,
            can_create_certificates=False,
            can_edit_certificates=False,
            can_delete_certificates=False,
            can_revoke_certificates=False,
            can_manage_enrollments=False,
            can_create_enrollments=False,
            can_edit_enrollments=False,
            can_delete_enrollments=False,
            can_manage_payments=False,
            can_view_payments=False,
            can_create_payments=False,
            can_manage_invoices=False,
            can_create_invoices=False,
            can_edit_invoices=False,
            can_delete_invoices=False,
            can_manage_documents=False,
            can_view_documents=False,
            can_upload_documents=False,
            can_delete_documents=False,
            can_view_reports=False,
            can_export_reports=False,
            can_manage_instructors=False,
            can_manage_settings=False,
        )


# ─────────────────────────────────────────────────────────
# Student Schemas
# ─────────────────────────────────────────────────────────

class StudentBase(BaseModel):
    """Base student schema"""
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    enrollment_status: EnrollmentStatus = EnrollmentStatus.PENDING
    enrollment_date: Optional[date] = None
    graduation_date: Optional[date] = None
    program_type: Optional[str] = None
    referral_source: Optional[str] = None
    notes: Optional[str] = None


class StudentCreate(StudentBase):
    """Schema for creating a student"""
    user_id: int


class StudentUpdate(BaseModel):
    """Schema for updating a student (Admin only)"""
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    enrollment_status: Optional[EnrollmentStatus] = None
    enrollment_date: Optional[date] = None
    graduation_date: Optional[date] = None
    program_type: Optional[str] = None
    referral_source: Optional[str] = None
    notes: Optional[str] = None


class StudentUpdateWithUser(BaseModel):
    """Schema for updating a student with user fields (Admin only)"""
    # User fields
    full_name: Optional[str] = Field(None, min_length=2, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    
    # Student fields
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    enrollment_status: Optional[EnrollmentStatus] = None
    enrollment_date: Optional[date] = None
    graduation_date: Optional[date] = None
    program_type: Optional[str] = None
    referral_source: Optional[str] = None
    notes: Optional[str] = None

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # Convert empty strings to None for optional fields
        for field in ['full_name', 'phone', 'email', 'date_of_birth', 'gender', 'emergency_contact_name', 
                      'emergency_contact_phone', 'emergency_contact_relation', 'address_line1',
                      'address_line2', 'city', 'state', 'postal_code', 'country', 
                      'enrollment_date', 'graduation_date', 'program_type', 'referral_source', 'notes']:
            if field in data and data[field] == '':
                data[field] = None
        return data


class StudentResponse(StudentBase):
    """Schema for student response"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StudentResponseWithUser(StudentResponse):
    """Schema for student response with user info"""
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────
# Student with User Creation Schema
# ─────────────────────────────────────────────────────────

class UserCreateSimple(BaseModel):
    """Simple user creation schema for student enrollment"""
    full_name: str = Field(..., min_length=2, max_length=200)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=6)


class StudentWithUserCreate(BaseModel):
    """Schema for creating a student with user in one request"""
    # User fields
    full_name: str = Field(..., min_length=2, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=6)
    
    # Student fields
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    enrollment_status: EnrollmentStatus = EnrollmentStatus.PENDING
    enrollment_date: Optional[date] = None
    graduation_date: Optional[date] = None
    program_type: Optional[str] = None
    referral_source: Optional[str] = None
    notes: Optional[str] = None

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # Convert empty strings to None for optional fields
        for field in ['phone', 'email', 'date_of_birth', 'gender', 'emergency_contact_name', 
                      'emergency_contact_phone', 'emergency_contact_relation', 'address_line1',
                      'address_line2', 'city', 'state', 'postal_code', 'country', 
                      'enrollment_date', 'graduation_date', 'program_type', 'referral_source', 'notes']:
            if field in data and data[field] == '':
                data[field] = None
        return data


# ─────────────────────────────────────────────────────────
# Student Document Schemas
# ─────────────────────────────────────────────────────────

class StudentDocumentBase(BaseModel):
    """Base schema for student document"""
    document_type: DocumentType
    description: Optional[str] = None


class StudentDocumentCreate(StudentDocumentBase):
    """Schema for creating a student document"""
    pass


class StudentDocumentUpdate(BaseModel):
    """Schema for updating a student document"""
    description: Optional[str] = None
    is_active: Optional[bool] = None


class StudentDocumentResponse(StudentDocumentBase):
    """Schema for student document response"""
    id: int
    student_id: int
    file_name: str
    file_path: str
    file_size: int
    mime_type: str
    uploaded_by: Optional[int] = None
    uploaded_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class StudentDocumentList(BaseModel):
    """Schema for listing student documents"""
    documents: list[StudentDocumentResponse]
    total: int


# ─────────────────────────────────────────────────────────
# Course Schemas
# ─────────────────────────────────────────────────────────

class CourseBase(BaseModel):
    """Base course schema"""
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    duration_hours: Optional[float] = None
    duration_text: Optional[str] = None
    level: Optional[str] = None


class CourseCreate(CourseBase):
    """Schema for creating a course"""
    pass


class CourseUpdate(BaseModel):
    """Schema for updating a course"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    duration_hours: Optional[float] = None
    duration_text: Optional[str] = None
    level: Optional[str] = None
    is_active: Optional[bool] = None


class CourseResponse(CourseBase):
    """Schema for course response"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CourseList(BaseModel):
    """Schema for listing courses"""
    courses: list[CourseResponse]
    total: int


# ─────────────────────────────────────────────────────────
# Enrollment Schemas
# ─────────────────────────────────────────────────────────

class EnrollmentBase(BaseModel):
    """Base enrollment schema"""
    course_id: int
    fee: Optional[float] = Field(None, ge=0)
    status: CourseEnrollmentStatus = CourseEnrollmentStatus.PENDING
    start_date: Optional[date] = None
    completion_date: Optional[date] = None
    grade: Optional[str] = None
    attendance_percentage: Optional[float] = None
    notes: Optional[str] = None


class EnrollmentCreate(EnrollmentBase):
    """Schema for creating an enrollment"""
    student_id: int
    create_invoice: bool = False  # If true, auto-create invoice items


class EnrollmentUpdate(BaseModel):
    """Schema for updating an enrollment"""
    status: Optional[CourseEnrollmentStatus] = None
    start_date: Optional[date] = None
    completion_date: Optional[date] = None
    grade: Optional[str] = None
    attendance_percentage: Optional[float] = None
    notes: Optional[str] = None


class EnrollmentResponse(EnrollmentBase):
    """Schema for enrollment response"""
    id: int
    student_id: int
    enrolled_at: datetime
    created_at: datetime
    updated_at: datetime
    total_paid: float = 0  # Total amount paid for this enrollment

    class Config:
        from_attributes = True


class EnrollmentResponseWithDetails(EnrollmentResponse):
    """Schema for enrollment with student and course details"""
    student: Optional[StudentResponseWithUser] = None
    course: Optional[CourseResponse] = None
    
    class Config:
        from_attributes = True


class EnrollmentList(BaseModel):
    """Schema for listing enrollments"""
    enrollments: list[EnrollmentResponse]
    total: int


class EnrollmentItemResponse(BaseModel):
    """Schema for enrollment in invoice items - lightweight version"""
    id: int
    course: Optional[CourseResponse] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────
# Certificate Template Schemas
# ─────────────────────────────────────────────────────────

class CertificateTemplateBase(BaseModel):
    """Base certificate template schema"""
    name: str = Field(..., min_length=2, max_length=255)
    html_content: str
    css_styles: Optional[str] = None
    background_image_url: Optional[str] = None


class CertificateTemplateCreate(CertificateTemplateBase):
    """Schema for creating a certificate template"""
    pass


class CertificateTemplateUpdate(BaseModel):
    """Schema for updating a certificate template"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    html_content: Optional[str] = None
    css_styles: Optional[str] = None
    background_image_url: Optional[str] = None
    is_active: Optional[bool] = None


class CertificateTemplateResponse(CertificateTemplateBase):
    """Schema for certificate template response"""
    id: int
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CertificateTemplateList(BaseModel):
    """Schema for listing certificate templates"""
    templates: list[CertificateTemplateResponse]
    total: int


# ─────────────────────────────────────────────────────────
# Certificate Schemas
# ─────────────────────────────────────────────────────────

class CertificateBase(BaseModel):
    """Base certificate schema"""
    template_id: int
    course_id: int
    issue_date: date
    expiry_date: Optional[date] = None
    cert_metadata: Optional[dict] = None


class CertificateCreate(CertificateBase):
    """Schema for creating a certificate"""
    student_id: int


class CertificateCreateBulk(BaseModel):
    """Schema for bulk creating certificates"""
    template_id: int
    course_id: int
    student_ids: list[int]
    issue_date: date = Field(default_factory=date.today)
    expiry_date: Optional[date] = None


class CertificateUpdate(BaseModel):
    """Schema for updating a certificate"""
    cert_metadata: Optional[dict] = None


class CertificateRevoke(BaseModel):
    """Schema for revoking a certificate"""
    reason: str = Field(..., min_length=5)


class CertificateResponse(CertificateBase):
    """Schema for certificate response"""
    id: int
    certificate_number: str
    student_id: int
    pdf_url: Optional[str] = None
    status: CertificateStatus
    revocation_reason: Optional[str] = None
    revoked_by: Optional[int] = None
    revoked_at: Optional[datetime] = None
    issued_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CertificateResponseWithDetails(CertificateResponse):
    """Schema for certificate with student, course, and template details"""
    student: Optional[StudentResponseWithUser] = None
    course: Optional[CourseResponse] = None
    template: Optional[CertificateTemplateResponse] = None
    issuer: Optional[UserResponse] = None

    class Config:
        from_attributes = True


class CertificateList(BaseModel):
    """Schema for listing certificates"""
    certificates: list[CertificateResponse]
    total: int


# ─────────────────────────────────────────────────────────
# Certificate Verification Schema
# ─────────────────────────────────────────────────────────

class CertificateVerifyResponse(BaseModel):
    """Schema for certificate verification response"""
    valid: bool
    certificate: Optional[CertificateResponseWithDetails] = None
    message: str


# ─────────────────────────────────────────────────────────
# Certificate Statistics Schema
# ─────────────────────────────────────────────────────────

class CertificateStats(BaseModel):
    """Schema for certificate statistics"""
    total_certificates: int
    active_certificates: int
    revoked_certificates: int
    expired_certificates: int
    certificates_this_month: int
    certificates_by_course: list[dict]
    recent_certificates: list[CertificateResponse]


# ─────────────────────────────────────────────────────────
# Payment Method Schemas
# ─────────────────────────────────────────────────────────

class PaymentMethodBase(BaseModel):
    """Base payment method schema"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class PaymentMethodCreate(PaymentMethodBase):
    """Schema for creating a payment method"""
    pass


class PaymentMethodUpdate(BaseModel):
    """Schema for updating a payment method"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PaymentMethodResponse(PaymentMethodBase):
    """Schema for payment method response"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────
# Payment Schemas
# ─────────────────────────────────────────────────────────

class PaymentBase(BaseModel):
    """Base payment schema"""
    student_id: int
    enrollment_id: Optional[int] = None
    invoice_id: Optional[int] = None
    amount: float = Field(..., gt=0)
    payment_date: date
    payment_method_id: int
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreate(PaymentBase):
    """Schema for creating a payment"""
    status: PaymentStatus = PaymentStatus.COMPLETED


class PaymentUpdate(BaseModel):
    """Schema for updating a payment"""
    amount: Optional[float] = Field(None, gt=0)
    payment_date: Optional[date] = None
    payment_method_id: Optional[int] = None
    transaction_reference: Optional[str] = None
    status: Optional[PaymentStatus] = None
    notes: Optional[str] = None


class PaymentResponse(PaymentBase):
    """Schema for payment response"""
    id: int
    status: PaymentStatus
    recorded_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    invoice_number: Optional[str] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────
# Invoice Item Schemas
# ─────────────────────────────────────────────────────────

class InvoiceItemBase(BaseModel):
    """Base invoice item schema"""
    enrollment_id: Optional[int] = None
    description: str
    quantity: int = Field(1, ge=1)
    unit_price: float = Field(..., gt=0)


class InvoiceItemCreate(InvoiceItemBase):
    """Schema for creating an invoice item"""
    pass


class InvoiceItemUpdate(BaseModel):
    """Schema for updating an invoice item"""
    description: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=1)
    unit_price: Optional[float] = Field(None, gt=0)


class InvoiceItemResponse(InvoiceItemBase):
    """Schema for invoice item response"""
    id: int
    amount: float
    created_at: datetime
    updated_at: datetime
    enrollment: Optional["EnrollmentItemResponse"] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────
# Invoice Schemas
# ─────────────────────────────────────────────────────────

class InvoiceBase(BaseModel):
    """Base invoice schema"""
    student_id: int
    issue_date: date
    due_date: Optional[date] = None
    discount_amount: float = 0
    tax_amount: float = 0
    notes: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    """Schema for creating an invoice"""
    items: list[InvoiceItemCreate]


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice"""
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    discount_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    status: Optional[InvoiceStatus] = None
    notes: Optional[str] = None


class InvoiceResponse(InvoiceBase):
    """Schema for invoice response"""
    id: int
    invoice_number: str
    total_amount: float
    grand_total: float
    status: InvoiceStatus
    pdf_url: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    student_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class InvoiceWithItems(InvoiceResponse):
    """Invoice with items"""
    items: list[InvoiceItemResponse] = []
