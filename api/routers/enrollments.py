from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

from api.database import get_db
from api.models import User, Student, Course, Enrollment, CourseEnrollmentStatus, Invoice, InvoiceItem, Payment, PaymentStatus, InvoiceStatus, UserRole
from api.schemas import (
    EnrollmentCreate,
    EnrollmentUpdate,
    EnrollmentResponse,
    EnrollmentResponseWithDetails,
    EnrollmentList
)
from api.auth import require_role, get_current_active_user
from api.routers.invoices import generate_invoice_number
from api.services.pdf_generator import generate_invoice_pdf_bytes, save_invoice_pdf

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


@router.get("", response_model=EnrollmentList)
async def list_enrollments(
    skip: int = 0,
    limit: int = 100,
    student_id: Optional[int] = None,
    course_id: Optional[int] = None,
    status: Optional[CourseEnrollmentStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="view_enrollments"))
):
    """List all enrollments with optional filters"""
    query = select(Enrollment)
    
    if student_id:
        query = query.where(Enrollment.student_id == student_id)
    if course_id:
        query = query.where(Enrollment.course_id == course_id)
    if status:
        query = query.where(Enrollment.status == status)
    
    query = query.order_by(Enrollment.enrolled_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    enrollments = result.scalars().all()
    
    # Get total count
    count_query = select(Enrollment)
    if student_id:
        count_query = count_query.where(Enrollment.student_id == student_id)
    if course_id:
        count_query = count_query.where(Enrollment.course_id == course_id)
    if status:
        count_query = count_query.where(Enrollment.status == status)
    
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Build enrollment responses with total_paid calculated from payments
    enrollment_responses = []
    for enrollment in enrollments:
        # Calculate total_paid from completed payments for this enrollment
        paid_stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.enrollment_id == enrollment.id,
            Payment.status == PaymentStatus.COMPLETED
        )
        paid_result = await db.execute(paid_stmt)
        total_paid = float(paid_result.scalar() or 0)
        
        enrollment_responses.append(EnrollmentResponse(
            id=enrollment.id,
            student_id=enrollment.student_id,
            course_id=enrollment.course_id,
            fee=enrollment.fee,
            status=enrollment.status,
            enrolled_at=enrollment.enrolled_at,
            start_date=enrollment.start_date,
            completion_date=enrollment.completion_date,
            grade=enrollment.grade,
            attendance_percentage=enrollment.attendance_percentage,
            notes=enrollment.notes,
            created_at=enrollment.created_at,
            updated_at=enrollment.updated_at,
            total_paid=total_paid
        ))
    
    return {"enrollments": enrollment_responses, "total": total}


@router.get("/{enrollment_id}", response_model=EnrollmentResponseWithDetails)
async def get_enrollment(
    enrollment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="view_enrollments"))
):
    """Get a specific enrollment with details"""
    result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )
    
    # Get student details
    student_result = await db.execute(
        select(Student).where(Student.id == enrollment.student_id)
    )
    student = student_result.scalar_one_or_none()
    
    # Get course details
    course_result = await db.execute(
        select(Course).where(Course.id == enrollment.course_id)
    )
    course = course_result.scalar_one_or_none()
    
    # Calculate total_paid from completed payments for this enrollment
    paid_stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.enrollment_id == enrollment.id,
        Payment.status == PaymentStatus.COMPLETED
    )
    paid_result = await db.execute(paid_stmt)
    total_paid = float(paid_result.scalar() or 0)
    
    # Build response with details
    response = EnrollmentResponseWithDetails(
        id=enrollment.id,
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
        fee=enrollment.fee,
        status=enrollment.status,
        enrolled_at=enrollment.enrolled_at,
        start_date=enrollment.start_date,
        completion_date=enrollment.completion_date,
        grade=enrollment.grade,
        attendance_percentage=enrollment.attendance_percentage,
        notes=enrollment.notes,
        created_at=enrollment.created_at,
        updated_at=enrollment.updated_at,
        total_paid=total_paid,
        student=None,
        course=course
    )
    
    return response


@router.post("", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    enrollment: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="create_enrollments"))
):
    """Create a new enrollment"""
    # Check if student exists
    student_result = await db.execute(select(Student).where(Student.id == enrollment.student_id))
    student = student_result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if course exists
    course_result = await db.execute(select(Course).where(Course.id == enrollment.course_id))
    course = course_result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if already enrolled
    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == enrollment.student_id,
            Enrollment.course_id == enrollment.course_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is already enrolled in this course"
        )
    
    # Create enrollment
    db_enrollment = Enrollment(
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
        fee=enrollment.fee,  # Include fee
        status=enrollment.status,
        start_date=enrollment.start_date,
        completion_date=enrollment.completion_date,
        grade=enrollment.grade,
        attendance_percentage=enrollment.attendance_percentage,
        notes=enrollment.notes
    )
    
    db.add(db_enrollment)
    await db.commit()
    await db.refresh(db_enrollment)
    
    # If create_invoice is true and fee is specified, create an invoice with item
    if enrollment.create_invoice and enrollment.fee and enrollment.fee > 0:
        # Create invoice for this enrollment
        invoice = Invoice(
            invoice_number=generate_invoice_number(),
            student_id=enrollment.student_id,
            issue_date=date.today(),
            due_date=None,
            total_amount=enrollment.fee,
            discount_amount=0,
            tax_amount=0,
            grand_total=enrollment.fee,
            status=InvoiceStatus.DRAFT,
            created_by=current_user.id
        )
        db.add(invoice)
        await db.flush()  # Get the invoice ID
        
        # Create invoice item for the enrollment
        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            enrollment_id=db_enrollment.id,
            description=f"Course: {course.name}",
            quantity=1,
            unit_price=enrollment.fee,
            amount=enrollment.fee  # quantity * unit_price
        )
        db.add(invoice_item)
        await db.commit()
        await db.refresh(invoice)
        
        # Auto-generate PDF for the invoice
        try:
            logger.info(f"Starting PDF generation for invoice: {invoice.invoice_number}")
            
            # Get student info with user relationship
            student_stmt = select(Student).options(selectinload(Student.user)).where(Student.id == enrollment.student_id)
            student_result = await db.execute(student_stmt)
            student = student_result.scalar_one()
            
            logger.info(f"Got student: {student.id}")
            
            # Get student name from user
            student_name = student.user.full_name if student.user else f"Student #{student.id}"
            student_email = student.user.email if student.user else ""
            student_phone = student.user.phone if student.user and student.user.phone else ""
            
            logger.info(f"Student name: {student_name}, email: {student_email}")
            
            # Format dates
            issue_date_str = date.today().strftime("%B %d, %Y")
            due_date_str = "N/A" if not invoice.due_date else invoice.due_date.strftime("%B %d, %Y")
            
            # Prepare items for PDF
            items_data = [{
                "description": invoice_item.description,
                "quantity": invoice_item.quantity,
                "unit_price": invoice_item.unit_price,
                "amount": invoice_item.amount
            }]
            
            logger.info(f"Generating PDF with {len(items_data)} items, total: {invoice.grand_total}")
            
            # Generate PDF bytes
            pdf_bytes = generate_invoice_pdf_bytes(
                invoice_number=invoice.invoice_number,
                issue_date=issue_date_str,
                due_date=due_date_str,
                student_name=student_name,
                student_email=student_email,
                student_phone=student_phone,
                items=items_data,
                subtotal=invoice.total_amount,
                discount=invoice.discount_amount or 0,
                tax=invoice.tax_amount or 0,
                grand_total=invoice.grand_total
            )
            
            logger.info(f"PDF generated, size: {len(pdf_bytes)} bytes")
            
            # Save PDF to file
            pdf_url = save_invoice_pdf(pdf_bytes, invoice.invoice_number)
            
            logger.info(f"PDF saved to: {pdf_url}")
            
            # Update invoice with PDF URL
            invoice.pdf_url = pdf_url
            await db.commit()
            
            logger.info(f"Invoice updated with PDF URL: {pdf_url}")
        except Exception as e:
            # Log error but don't fail enrollment creation
            logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
    
    # Return enrollment response
    return EnrollmentResponse(
        id=db_enrollment.id,
        student_id=db_enrollment.student_id,
        course_id=db_enrollment.course_id,
        fee=db_enrollment.fee,
        status=db_enrollment.status,
        enrolled_at=db_enrollment.enrolled_at,
        start_date=db_enrollment.start_date,
        completion_date=db_enrollment.completion_date,
        grade=db_enrollment.grade,
        attendance_percentage=db_enrollment.attendance_percentage,
        notes=db_enrollment.notes,
        created_at=db_enrollment.created_at,
        updated_at=db_enrollment.updated_at
    )


@router.put("/{enrollment_id}", response_model=EnrollmentResponse)
async def update_enrollment(
    enrollment_id: int,
    enrollment_update: EnrollmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="edit_enrollments"))
):
    """Update an enrollment"""
    result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )
    
    # Update fields
    update_data = enrollment_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(enrollment, field, value)
    
    enrollment.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(enrollment)
    
    return enrollment


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_enrollment(
    enrollment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="delete_enrollments"))
):
    """Delete an enrollment"""
    result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
    enrollment = result.scalar_one_or_none()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )
    
    # Delete related invoice items first
    invoice_items_result = await db.execute(
        select(InvoiceItem).where(InvoiceItem.enrollment_id == enrollment_id)
    )
    invoice_items = invoice_items_result.scalars().all()
    for item in invoice_items:
        await db.delete(item)
    
    await db.delete(enrollment)
    await db.commit()
    
    return None


# Student-specific endpoints
@router.get("/students/{student_id}", response_model=EnrollmentList)
async def get_student_enrollments(
    student_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all enrollments for a specific student (admin, instructor, or the student themselves)"""
    # Check if user is admin or instructor
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.INSTRUCTOR]:
        # Admin/Instructor can view any student's enrollments
        pass
    elif current_user.role == UserRole.STUDENT:
        # Students can only view their own enrollments
        stmt = select(Student).where(Student.id == student_id)
        result = await db.execute(stmt)
        student = result.scalar_one_or_none()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        # Check if this is the student's own record
        if student.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own enrollments"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get enrollments
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .order_by(Enrollment.enrolled_at.desc())
        .offset(skip)
        .limit(limit)
    )
    enrollments = result.scalars().all()
    
    # Get total count
    count_result = await db.execute(
        select(Enrollment).where(Enrollment.student_id == student_id)
    )
    total = len(count_result.scalars().all())
    
    # Build enrollment responses with total_paid calculated from payments
    enrollment_responses = []
    for enrollment in enrollments:
        # Calculate total_paid from completed payments for this enrollment
        paid_stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.enrollment_id == enrollment.id,
            Payment.status == PaymentStatus.COMPLETED
        )
        paid_result = await db.execute(paid_stmt)
        total_paid = float(paid_result.scalar() or 0)
        
        enrollment_responses.append(EnrollmentResponse(
            id=enrollment.id,
            student_id=enrollment.student_id,
            course_id=enrollment.course_id,
            fee=enrollment.fee,
            status=enrollment.status,
            enrolled_at=enrollment.enrolled_at,
            start_date=enrollment.start_date,
            completion_date=enrollment.completion_date,
            grade=enrollment.grade,
            attendance_percentage=enrollment.attendance_percentage,
            notes=enrollment.notes,
            created_at=enrollment.created_at,
            updated_at=enrollment.updated_at,
            total_paid=total_paid
        ))
    
    return {"enrollments": enrollment_responses, "total": total}
