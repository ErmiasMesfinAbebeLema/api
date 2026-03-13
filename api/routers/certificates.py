from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, date
import uuid
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from api.database import get_db
from api.models import User, Student, Course, Certificate, CertificateTemplate, CertificateStatus
from api.schemas import (
    CertificateTemplateCreate,
    CertificateTemplateUpdate,
    CertificateTemplateResponse,
    CertificateTemplateList,
    CertificateCreate,
    CertificateCreateBulk,
    CertificateUpdate,
    CertificateRevoke,
    CertificateResponse,
    CertificateResponseWithDetails,
    CertificateList,
    CertificateVerifyResponse,
    CertificateStats
)
from api.auth import require_role
from api.services.pdf_generator import generate_certificate_pdf, save_certificate_pdf

# Base URL for verification
VERIFICATION_BASE_URL = os.getenv("VERIFICATION_BASE_URL", "http://localhost:3000/verify")


def generate_certificate_number() -> str:
    """Generate a unique certificate number"""
    import random
    import string
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"CERT-{timestamp}-{random_part}"

router = APIRouter(prefix="", tags=["Certificates"])

# Certificate Templates Admin Router
templates_router = APIRouter(prefix="/admin/certificate-templates", tags=["Certificate Templates"])

# Certificates Admin Router
admin_certificates_router = APIRouter(prefix="/admin/certificates", tags=["Certificates - Admin"])

# Public Router
public_certificates_router = APIRouter(prefix="", tags=["Certificates - Public"])

# Student Router - for students to view their own certificates
student_certificates_router = APIRouter(prefix="/student/certificates", tags=["Certificates - Student"])


# ─────────────────────────────────────────────────────────
# Certificate Templates Endpoints
# ─────────────────────────────────────────────────────────

@templates_router.get("", response_model=CertificateTemplateList)
async def list_templates(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_certificate_templates"))
):
    """List all certificate templates"""
    result = await db.execute(
        select(CertificateTemplate)
        .order_by(CertificateTemplate.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    templates = result.scalars().all()
    
    count_result = await db.execute(select(CertificateTemplate))
    total = len(count_result.scalars().all())
    
    return {"templates": templates, "total": total}


@templates_router.get("/{template_id}", response_model=CertificateTemplateResponse)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_certificate_templates"))
):
    """Get a specific template"""
    result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    return template


@templates_router.post("", response_model=CertificateTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template: CertificateTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="create_certificate_templates"))
):
    """Create a new certificate template"""
    db_template = CertificateTemplate(
        name=template.name,
        html_content=template.html_content,
        css_styles=template.css_styles,
        background_image_url=template.background_image_url,
        is_active=True,
        created_by=current_user.id
    )
    
    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)
    
    return db_template


@templates_router.put("/{template_id}", response_model=CertificateTemplateResponse)
async def update_template(
    template_id: int,
    template_update: CertificateTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_certificate_templates"))
):
    """Update a certificate template"""
    result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    update_data = template_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    template.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(template)
    
    return template


@templates_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="delete_certificate_templates"))
):
    """Delete a certificate template"""
    result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    await db.delete(template)
    await db.commit()
    
    return None


# ─────────────────────────────────────────────────────────
# Certificate Endpoints (Admin)
# ─────────────────────────────────────────────────────────

def generate_certificate_number() -> str:
    """Generate a unique certificate number"""
    year = datetime.now().year
    random_part = str(uuid.uuid4().int)[:6]
    return f"CERT-{year}-{random_part}"


@admin_certificates_router.get("", response_model=CertificateList)
async def list_certificates(
    skip: int = 0,
    limit: int = 100,
    student_id: Optional[int] = None,
    course_id: Optional[int] = None,
    status: Optional[CertificateStatus] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="view_certificates"))
):
    """List all certificates with optional filters"""
    query = select(Certificate).order_by(Certificate.created_at.desc())
    
    if student_id:
        query = query.where(Certificate.student_id == student_id)
    if course_id:
        query = query.where(Certificate.course_id == course_id)
    if status:
        query = query.where(Certificate.status == status)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    certificates = result.scalars().all()
    
    # Get total count
    count_query = select(Certificate)
    if student_id:
        count_query = count_query.where(Certificate.student_id == student_id)
    if course_id:
        count_query = count_query.where(Certificate.course_id == course_id)
    if status:
        count_query = count_query.where(Certificate.status == status)
    
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    return {"certificates": certificates, "total": total}


# Stats endpoint - must be before wildcard routes
@admin_certificates_router.get("/stats", response_model=CertificateStats)
async def get_certificate_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="view_certificates"))
):
    """Get certificate statistics"""
    # Total certificates
    total_result = await db.execute(select(func.count(Certificate.id)))
    total_certificates = total_result.scalar() or 0
    
    # Active certificates
    active_result = await db.execute(
        select(func.count(Certificate.id)).where(Certificate.status == CertificateStatus.ACTIVE)
    )
    active_certificates = active_result.scalar() or 0
    
    # Revoked certificates
    revoked_result = await db.execute(
        select(func.count(Certificate.id)).where(Certificate.status == CertificateStatus.REVOKED)
    )
    revoked_certificates = revoked_result.scalar() or 0
    
    # Expired certificates
    expired_result = await db.execute(
        select(func.count(Certificate.id)).where(Certificate.status == CertificateStatus.EXPIRED)
    )
    expired_certificates = expired_result.scalar() or 0
    
    # This month
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    month_result = await db.execute(
        select(func.count(Certificate.id)).where(Certificate.created_at >= month_start)
    )
    certificates_this_month = month_result.scalar() or 0
    
    # By course
    course_result = await db.execute(
        select(
            Course.id,
            Course.name,
            func.count(Certificate.id).label("count")
        )
        .join(Certificate, Certificate.course_id == Course.id)
        .group_by(Course.id, Course.name)
        .order_by(func.count(Certificate.id).desc())
    )
    certificates_by_course = [
        {"course_id": row[0], "course_name": row[1], "count": row[2]}
        for row in course_result.fetchall()
    ]
    
    # Recent certificates
    recent_result = await db.execute(
        select(Certificate)
        .order_by(Certificate.created_at.desc())
        .limit(10)
    )
    recent_certificates = recent_result.scalars().all()
    
    return CertificateStats(
        total_certificates=total_certificates,
        active_certificates=active_certificates,
        revoked_certificates=revoked_certificates,
        expired_certificates=expired_certificates,
        certificates_this_month=certificates_this_month,
        certificates_by_course=certificates_by_course,
        recent_certificates=recent_certificates
    )


@admin_certificates_router.get("/{certificate_id}", response_model=CertificateResponseWithDetails)
async def get_certificate(
    certificate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="view_certificates"))
):
    """Get a specific certificate with details"""
    result = await db.execute(
        select(Certificate).where(Certificate.id == certificate_id)
    )
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found"
        )
    
    # Get related data
    student_result = await db.execute(
        select(Student).where(Student.id == certificate.student_id)
    )
    student = student_result.scalar_one_or_none()
    
    course_result = await db.execute(
        select(Course).where(Course.id == certificate.course_id)
    )
    course = course_result.scalar_one_or_none()
    
    template_result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == certificate.template_id)
    )
    template = template_result.scalar_one_or_none()
    
    return CertificateResponseWithDetails(
        id=certificate.id,
        certificate_number=certificate.certificate_number,
        student_id=certificate.student_id,
        template_id=certificate.template_id,
        course_id=certificate.course_id,
        issue_date=certificate.issue_date,
        expiry_date=certificate.expiry_date,
        cert_metadata=certificate.cert_metadata,
        pdf_url=certificate.pdf_url,
        status=certificate.status,
        revocation_reason=certificate.revocation_reason,
        revoked_by=certificate.revoked_by,
        revoked_at=certificate.revoked_at,
        issued_by=certificate.issued_by,
        created_at=certificate.created_at,
        updated_at=certificate.updated_at,
        student=None,
        course=course,
        template=template
    )


@admin_certificates_router.post("", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
async def create_certificate(
    cert_data: CertificateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="create_certificates"))
):
    """Issue a certificate to a student"""
    # Check if student exists
    student_result = await db.execute(
        select(Student).options(selectinload(Student.user)).where(Student.id == cert_data.student_id)
    )
    student = student_result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if course exists
    course_result = await db.execute(select(Course).where(Course.id == cert_data.course_id))
    course = course_result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if template exists
    template_result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == cert_data.template_id)
    )
    template = template_result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    # Generate certificate number
    certificate_number = generate_certificate_number()
    
    # Generate PDF certificate
    try:
        # Get student name
        student_name = "Unknown Student"
        if student.user:
            student_name = getattr(student.user, 'full_name', None) or getattr(student.user, 'email', f"Student #{student.id}")
        
        # Get verification URL
        verification_url = f"{VERIFICATION_BASE_URL}?cert={certificate_number}"
        
        # Generate PDF
        pdf_bytes = generate_certificate_pdf(
            html_template=template.html_content,
            certificate_number=certificate_number,
            student_name=student_name,
            course_name=course.name,
            issue_date=cert_data.issue_date,
            expiry_date=cert_data.expiry_date,
            template_name=template.name,
            background_image_url=template.background_image_url,
            verification_url=verification_url
        )
        
        # Save PDF to storage
        pdf_relative_path = save_certificate_pdf(
            pdf_bytes=pdf_bytes,
            certificate_number=certificate_number,
            issue_date=cert_data.issue_date
        )
        
        pdf_url = f"/uploads/certificates/{pdf_relative_path}"
    except Exception as e:
        # If PDF generation fails, continue without PDF
        logger.error(f"PDF generation failed: {str(e)}")
        pdf_url = None
    
    # Create certificate
    db_certificate = Certificate(
        certificate_number=certificate_number,
        student_id=cert_data.student_id,
        template_id=cert_data.template_id,
        course_id=cert_data.course_id,
        issue_date=cert_data.issue_date,
        expiry_date=cert_data.expiry_date,
        cert_metadata=cert_data.cert_metadata,
        pdf_url=pdf_url,
        status=CertificateStatus.ACTIVE,
        issued_by=current_user.id
    )
    
    db.add(db_certificate)
    await db.commit()
    await db.refresh(db_certificate)
    
    return db_certificate


@admin_certificates_router.post("/bulk", response_model=list[CertificateResponse], status_code=status.HTTP_201_CREATED)
async def create_bulk_certificates(
    cert_data: CertificateCreateBulk,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="create_certificates"))
):
    """Issue certificates to multiple students"""
    # Check if course exists
    course_result = await db.execute(select(Course).where(Course.id == cert_data.course_id))
    course = course_result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if template exists
    template_result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == cert_data.template_id)
    )
    template = template_result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    certificates = []
    
    for student_id in cert_data.student_ids:
        # Check if student exists
        student_result = await db.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalar_one_or_none()
        
        if not student:
            continue
        
        # Check if already has certificate for this course
        existing = await db.execute(
            select(Certificate).where(
                Certificate.student_id == student_id,
                Certificate.course_id == cert_data.course_id,
                Certificate.status == CertificateStatus.ACTIVE
            )
        )
        if existing.scalar_one_or_none():
            continue
        
        # Generate certificate number
        certificate_number = generate_certificate_number()
        
        db_certificate = Certificate(
            certificate_number=certificate_number,
            student_id=student_id,
            template_id=cert_data.template_id,
            course_id=cert_data.course_id,
            issue_date=cert_data.issue_date,
            expiry_date=cert_data.expiry_date,
            status=CertificateStatus.ACTIVE,
            issued_by=current_user.id
        )
        
        db.add(db_certificate)
        certificates.append(db_certificate)
    
    await db.commit()
    
    # Refresh all certificates
    for cert in certificates:
        await db.refresh(cert)
    
    return certificates


@admin_certificates_router.post("/{certificate_id}/revoke", response_model=CertificateResponse)
async def revoke_certificate(
    certificate_id: int,
    revoke_data: CertificateRevoke,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_certificates"))
):
    """Revoke a certificate"""
    result = await db.execute(
        select(Certificate).where(Certificate.id == certificate_id)
    )
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found"
        )
    
    if certificate.status != CertificateStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate is already revoked or expired"
        )
    
    certificate.status = CertificateStatus.REVOKED
    certificate.revocation_reason = revoke_data.reason
    certificate.revoked_by = current_user.id
    certificate.revoked_at = datetime.utcnow()
    certificate.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(certificate)
    
    return certificate


@admin_certificates_router.get("/{certificate_id}/download")
async def download_certificate(
    certificate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="view_certificates"))
):
    """Download certificate PDF"""
    result = await db.execute(
        select(Certificate).where(Certificate.id == certificate_id)
    )
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found"
        )
    
    if not certificate.pdf_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not generated yet"
        )
    
    # Return the file
    file_path = Path(certificate.pdf_url.lstrip("/"))
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found"
        )
    
    return FileResponse(
        path=str(file_path),
        filename=f"{certificate.certificate_number}.pdf",
        media_type="application/pdf"
    )


# ─────────────────────────────────────────────────────────
# Public Certificate Endpoints
# ─────────────────────────────────────────────────────────

@public_certificates_router.get("/certificates/verify/{certificate_number}", response_model=CertificateVerifyResponse)
async def verify_certificate(
    certificate_number: str,
    db: AsyncSession = Depends(get_db)
):
    """Public endpoint to verify a certificate"""
    result = await db.execute(
        select(Certificate).options(selectinload(Certificate.issuer)).where(Certificate.certificate_number == certificate_number)
    )
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        return CertificateVerifyResponse(
            valid=False,
            certificate=None,
            message="Certificate not found"
        )
    
    if certificate.status == CertificateStatus.REVOKED:
        return CertificateVerifyResponse(
            valid=False,
            certificate=certificate,
            message="This certificate has been revoked"
        )
    
    if certificate.status == CertificateStatus.EXPIRED:
        # Check if expired
        if certificate.expiry_date and certificate.expiry_date < date.today():
            return CertificateVerifyResponse(
                valid=False,
                certificate=certificate,
                message="This certificate has expired"
            )
    
    # Get related data for response
    student_result = await db.execute(
        select(Student).options(selectinload(Student.user)).where(Student.id == certificate.student_id)
    )
    student = student_result.scalar_one_or_none()
    
    course_result = await db.execute(
        select(Course).where(Course.id == certificate.course_id)
    )
    course = course_result.scalar_one_or_none()
    
    template_result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == certificate.template_id)
    )
    template = template_result.scalar_one_or_none()
    
    return CertificateVerifyResponse(
        valid=True,
        certificate=CertificateResponseWithDetails(
            id=certificate.id,
            certificate_number=certificate.certificate_number,
            student_id=certificate.student_id,
            template_id=certificate.template_id,
            course_id=certificate.course_id,
            issue_date=certificate.issue_date,
            expiry_date=certificate.expiry_date,
            cert_metadata=certificate.cert_metadata,
            pdf_url=certificate.pdf_url,
            status=certificate.status,
            revocation_reason=certificate.revocation_reason,
            revoked_by=certificate.revoked_by,
            revoked_at=certificate.revoked_at,
            issued_by=certificate.issued_by,
            created_at=certificate.created_at,
            updated_at=certificate.updated_at,
            student=student,
            course=course,
            template=template,
            issuer=certificate.issuer
        ),
        message="Certificate is valid"
    )


# ─────────────────────────────────────────────────────────
# Student Certificate Endpoints
# ─────────────────────────────────────────────────────────

@student_certificates_router.get("", response_model=CertificateList)
async def get_my_certificates(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    """Get current student's certificates"""
    # Get the student profile for the current user
    result = await db.execute(
        select(Student).where(Student.user_id == current_user.id)
    )
    student = result.scalar_one_or_none()
    
    if not student:
        return {"certificates": [], "total": 0}
    
    # Get certificates for this student
    query = (
        select(Certificate)
        .where(Certificate.student_id == student.id)
        .order_by(Certificate.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    result = await db.execute(query)
    certificates = result.scalars().all()
    
    # Get total count
    count_query = select(Certificate).where(Certificate.student_id == student.id)
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    return {"certificates": certificates, "total": total}


@student_certificates_router.get("/{certificate_id}", response_model=CertificateResponseWithDetails)
async def get_my_certificate(
    certificate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    """Get a specific certificate for the current student"""
    # Get the student profile for the current user
    result = await db.execute(
        select(Student).where(Student.user_id == current_user.id)
    )
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get the certificate
    result = await db.execute(
        select(Certificate)
        .options(
            selectinload(Certificate.student).selectinload(Student.user),
            selectinload(Certificate.course),
            selectinload(Certificate.template),
            selectinload(Certificate.issuer)
        )
        .where(Certificate.id == certificate_id)
    )
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found"
        )
    
    # Verify the certificate belongs to the current student
    if certificate.student_id != student.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this certificate"
        )
    
    return certificate


@student_certificates_router.get("/{certificate_id}/download")
async def download_my_certificate(
    certificate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    """Download a specific certificate PDF for the current student"""
    # Get the student profile for the current user
    result = await db.execute(
        select(Student).where(Student.user_id == current_user.id)
    )
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get the certificate
    result = await db.execute(
        select(Certificate).where(Certificate.id == certificate_id)
    )
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found"
        )
    
    # Verify the certificate belongs to the current student
    if certificate.student_id != student.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to download this certificate"
        )
    
    # Check if certificate is revoked or expired
    if certificate.status == CertificateStatus.REVOKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This certificate has been revoked and cannot be downloaded"
        )
    
    if certificate.expiry_date and certificate.expiry_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This certificate has expired and cannot be downloaded"
        )
    
    if not certificate.pdf_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not generated yet"
        )
    
    file_path = Path(certificate.pdf_url.lstrip("/"))
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found"
        )
    
    return FileResponse(
        path=str(file_path),
        filename=f"{certificate.certificate_number}.pdf",
        media_type="application/pdf"
    )
