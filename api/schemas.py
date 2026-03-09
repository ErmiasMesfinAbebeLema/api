from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, date
from api.models import UserRole, Gender, EnrollmentStatus, DocumentType, CourseEnrollmentStatus, CertificateStatus, PaymentStatus, InvoiceStatus


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
    """Permission schema"""
    can_manage_users: bool = False
    can_manage_students: bool = False
    can_manage_courses: bool = False
    can_manage_certificates: bool = False
    can_view_reports: bool = False
    can_manage_instructors: bool = False


def get_permissions(role: UserRole) -> Permission:
    """Get permissions based on role"""
    if role == UserRole.ADMIN:
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
