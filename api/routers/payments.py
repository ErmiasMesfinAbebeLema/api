from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

from api.database import get_db
from api.models import User, Payment, Student, Enrollment, PaymentMethod, PaymentStatus, Invoice, InvoiceStatus, UserRole, InvoiceItem
from api.schemas import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse
)
from api.routers.auth import get_current_active_user
from api.auth import require_role
from api.services.pdf_generator import generate_invoice_pdf_bytes, save_invoice_pdf
from api.services.notifications import NotificationService
from api.services.email_service import email_service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("", response_model=List[PaymentResponse])
async def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    student_id: Optional[int] = None,
    enrollment_id: Optional[int] = None,
    payment_method_id: Optional[int] = None,
    status: Optional[PaymentStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_payments"))
):
    """List all payments with optional filters"""
    stmt = select(Payment).options(
        selectinload(Payment.student).selectinload(Student.user),
        selectinload(Payment.payment_method),
        selectinload(Payment.enrollment).selectinload(Enrollment.course),
        selectinload(Payment.invoice)
    )
    
    if student_id:
        stmt = stmt.where(Payment.student_id == student_id)
    if enrollment_id:
        stmt = stmt.where(Payment.enrollment_id == enrollment_id)
    if payment_method_id:
        stmt = stmt.where(Payment.payment_method_id == payment_method_id)
    if status:
        stmt = stmt.where(Payment.status == status)
    if start_date:
        stmt = stmt.where(Payment.payment_date >= start_date)
    if end_date:
        stmt = stmt.where(Payment.payment_date <= end_date)
    
    stmt = stmt.order_by(Payment.payment_date.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    payments = result.scalars().all()
    
    # Manually set invoice_number and student_name for each payment
    for payment in payments:
        if payment.invoice:
            payment.invoice_number = payment.invoice.invoice_number
        if payment.student and payment.student.user:
            payment.student_name = payment.student.user.full_name
    
    return payments


@router.get("/student/{student_id}", response_model=List[PaymentResponse])
async def get_student_payments(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all payments for a specific student (admin or the student themselves)"""
    # Check if user is admin
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        # Admin can view any student's payments
        pass
    elif current_user.role == UserRole.STUDENT:
        # Students can only view their own payments
        # First get the student's user_id
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
                detail="You can only view your own payments"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    stmt = select(Payment).where(Payment.student_id == student_id).options(
        selectinload(Payment.student).selectinload(Student.user),
        selectinload(Payment.payment_method),
        selectinload(Payment.enrollment).selectinload(Enrollment.course)
    ).order_by(Payment.payment_date.desc())
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/enrollment/{enrollment_id}", response_model=List[PaymentResponse])
async def get_enrollment_payments(
    enrollment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_payments"))
):
    """Get all payments for a specific enrollment"""
    stmt = select(Payment).where(Payment.enrollment_id == enrollment_id).options(
        selectinload(Payment.student).selectinload(Student.user),
        selectinload(Payment.payment_method)
    ).order_by(Payment.payment_date.desc())
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_payments"))
):
    """Get a specific payment"""
    stmt = select(Payment).where(Payment.id == payment_id).options(
        selectinload(Payment.student).selectinload(Student.user),
        selectinload(Payment.payment_method),
        selectinload(Payment.enrollment).selectinload(Enrollment.course)
    )
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    return payment


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="create_payments"))
):
    """Record a new payment (Admin only)"""
    # Verify student exists
    student_stmt = select(Student).where(Student.id == payment_data.student_id)
    result = await db.execute(student_stmt)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Verify payment method exists
    method_stmt = select(PaymentMethod).where(PaymentMethod.id == payment_data.payment_method_id)
    result = await db.execute(method_stmt)
    method = result.scalar_one_or_none()
    
    if not method:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    # If enrollment_id provided, verify it exists and belongs to the student
    if payment_data.enrollment_id:
        enrollment_stmt = select(Enrollment).where(
            Enrollment.id == payment_data.enrollment_id,
            Enrollment.student_id == payment_data.student_id
        )
        result = await db.execute(enrollment_stmt)
        enrollment = result.scalar_one_or_none()
        
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enrollment not found or doesn't belong to student"
            )
    
    # If invoice_id provided, verify it exists
    if payment_data.invoice_id:
        invoice_stmt = select(Invoice).where(Invoice.id == payment_data.invoice_id)
        result = await db.execute(invoice_stmt)
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found"
            )
        
        # Check if invoice is already paid
        if invoice.status == InvoiceStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invoice is already paid"
            )
    
    # Create payment
    payment = Payment(
        **payment_data.model_dump(),
        recorded_by=current_user.id
    )
    db.add(payment)
    await db.commit()
    
    # Reload with relationships for response
    payment_stmt = select(Payment).where(Payment.id == payment.id).options(
        selectinload(Payment.student).selectinload(Student.user),
        selectinload(Payment.payment_method),
        selectinload(Payment.enrollment).selectinload(Enrollment.course),
        selectinload(Payment.invoice)
    )
    result = await db.execute(payment_stmt)
    payment_with_relations = result.scalar_one()
    
    # Create a response dict with the needed data
    payment_data = {
        "id": payment_with_relations.id,
        "student_id": payment_with_relations.student_id,
        "student_name": payment_with_relations.student.user.full_name if payment_with_relations.student and payment_with_relations.student.user else None,
        "enrollment_id": payment_with_relations.enrollment_id,
        "invoice_id": payment_with_relations.invoice_id,
        "invoice_number": payment_with_relations.invoice.invoice_number if payment_with_relations.invoice else None,
        "amount": payment_with_relations.amount,
        "payment_date": payment_with_relations.payment_date,
        "payment_method_id": payment_with_relations.payment_method_id,
        "payment_method": {
            "id": payment_with_relations.payment_method.id, 
            "name": payment_with_relations.payment_method.name,
            "is_active": payment_with_relations.payment_method.is_active,
            "created_at": payment_with_relations.payment_method.created_at.isoformat() if payment_with_relations.payment_method.created_at else None,
            "updated_at": payment_with_relations.payment_method.updated_at.isoformat() if payment_with_relations.payment_method.updated_at else None
        } if payment_with_relations.payment_method else None,
        "transaction_reference": payment_with_relations.transaction_reference,
        "status": payment_with_relations.status,
        "notes": payment_with_relations.notes,
        "recorded_by": payment_with_relations.recorded_by,
        "created_at": payment_with_relations.created_at,
        "updated_at": payment_with_relations.updated_at,
    }
    
    # After payment is created, mark invoice as COMPLETED and regenerate PDF
    if payment_with_relations.invoice_id and payment_with_relations.status == PaymentStatus.COMPLETED:
        # Reload invoice
        invoice_stmt = select(Invoice).where(Invoice.id == payment_with_relations.invoice_id)
        result = await db.execute(invoice_stmt)
        invoice = result.scalar_one_or_none()
        
        if invoice:
            # Mark invoice as COMPLETED
            invoice.status = InvoiceStatus.COMPLETED.value
            
            # Regenerate PDF with PAID watermark
            try:
                # Load invoice with relationships
                invoice_stmt = select(Invoice).where(Invoice.id == payment_with_relations.invoice_id).options(
                    selectinload(Invoice.student).selectinload(Student.user),
                    selectinload(Invoice.items)
                )
                result = await db.execute(invoice_stmt)
                invoice_with_relations = result.scalar_one()
                
                # Prepare items for PDF
                items_data = [
                    {
                        "description": item.description,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "amount": item.amount
                    }
                    for item in invoice_with_relations.items
                ]
                
                # Format dates
                issue_date_str = invoice_with_relations.issue_date.strftime("%B %d, %Y") if invoice_with_relations.issue_date else ""
                due_date_str = invoice_with_relations.due_date.strftime("%B %d, %Y") if invoice_with_relations.due_date else ""
                
                # Get student info
                student = invoice_with_relations.student
                student_name = student.user.full_name if student and student.user else "N/A"
                student_email = student.user.email if student and student.user and student.user.email else ""
                student_phone = student.user.phone if student and student.user and student.user.phone else ""
                
                # Calculate tax rate
                tax_rate = 15
                if invoice_with_relations.total_amount > invoice_with_relations.discount_amount:
                    tax_rate = round((invoice_with_relations.tax_amount / (invoice_with_relations.total_amount - invoice_with_relations.discount_amount)) * 100, 2)
                
                # Generate PAID PDF
                pdf_bytes = generate_invoice_pdf_bytes(
                    invoice_number=invoice_with_relations.invoice_number,
                    issue_date=issue_date_str,
                    due_date=due_date_str,
                    student_name=student_name,
                    student_email=student_email,
                    student_phone=student_phone,
                    items=items_data,
                    subtotal=invoice_with_relations.total_amount,
                    discount=invoice_with_relations.discount_amount or 0,
                    tax=invoice_with_relations.tax_amount or 0,
                    grand_total=invoice_with_relations.grand_total,
                    tax_rate=tax_rate,
                    is_paid=True
                )
                
                # Save as paid invoice
                paid_pdf_path = save_invoice_pdf(pdf_bytes, f"{invoice_with_relations.invoice_number}_paid")
                invoice.pdf_url = paid_pdf_path
                
            except Exception as e:
                # Log error but don't fail the payment
                print(f"Error regenerating PDF: {str(e)}")
            
            await db.commit()
    
    # Create notification for payment received
    try:
        await NotificationService.notify_payment_received(
            db=db,
            payment_id=payment.id,
            created_by=current_user.id
        )
    except Exception as e:
        logger.error(f"Failed to create payment notification: {str(e)}")
    
    # Send payment receipt email with attachments
    if payment_with_relations.status == PaymentStatus.COMPLETED and payment_with_relations.student and payment_with_relations.student.user:
        try:
            student = payment_with_relations.student
            
            # Get invoice data for attachments
            invoice_pdf = None
            receipt_pdf = None
            invoice_number = None
            
            if payment_with_relations.invoice:
                invoice_number = payment_with_relations.invoice.invoice_number
                
                # Generate original invoice PDF
                invoice_stmt = select(Invoice).where(Invoice.id == payment_with_relations.invoice_id).options(
                    selectinload(Invoice.student).selectinload(Student.user),
                    selectinload(Invoice.items)
                )
                result = await db.execute(invoice_stmt)
                invoice_with_rels = result.scalar_one_or_none()
                
                if invoice_with_rels:
                    items_data = [
                        {
                            "description": item.description,
                            "quantity": item.quantity,
                            "unit_price": f"{item.unit_price:,.2f}",
                            "amount": f"{item.amount:,.2f}"
                        }
                        for item in invoice_with_rels.items
                    ]
                    
                    issue_date_str = invoice_with_rels.issue_date.strftime("%B %d, %Y") if invoice_with_rels.issue_date else ""
                    due_date_str = invoice_with_rels.due_date.strftime("%B %d, %Y") if invoice_with_rels.due_date else ""
                    
                    stu = invoice_with_rels.student
                    stu_name = stu.user.full_name if stu and stu.user else "N/A"
                    stu_email = stu.user.email if stu and stu.user and stu.user.email else ""
                    stu_phone = stu.user.phone if stu and stu.user and stu.user.phone else ""
                    
                    tax_rate = 15
                    if invoice_with_rels.total_amount > invoice_with_rels.discount_amount:
                        tax_rate = round((invoice_with_rels.tax_amount / (invoice_with_rels.total_amount - invoice_with_rels.discount_amount)) * 100, 2)
                    
                    # Generate unpaid invoice PDF
                    invoice_pdf = generate_invoice_pdf_bytes(
                        invoice_number=invoice_with_rels.invoice_number,
                        issue_date=issue_date_str,
                        due_date=due_date_str,
                        student_name=stu_name,
                        student_email=stu_email,
                        student_phone=stu_phone,
                        items=items_data,
                        subtotal=invoice_with_rels.total_amount,
                        discount=invoice_with_rels.discount_amount or 0,
                        tax=invoice_with_rels.tax_amount or 0,
                        grand_total=invoice_with_rels.grand_total,
                        tax_rate=tax_rate,
                        is_paid=False
                    )
                    
                    # Generate paid receipt PDF
                    receipt_pdf = generate_invoice_pdf_bytes(
                        invoice_number=invoice_with_rels.invoice_number,
                        issue_date=issue_date_str,
                        due_date=due_date_str,
                        student_name=stu_name,
                        student_email=stu_email,
                        student_phone=stu_phone,
                        items=items_data,
                        subtotal=invoice_with_rels.total_amount,
                        discount=invoice_with_rels.discount_amount or 0,
                        tax=invoice_with_rels.tax_amount or 0,
                        grand_total=invoice_with_rels.grand_total,
                        tax_rate=tax_rate,
                        is_paid=True
                    )
            
            # Send email with attachments
            course_name = ""
            if payment_with_relations.enrollment and payment_with_relations.enrollment.course:
                course_name = payment_with_relations.enrollment.course.name
            
            await email_service.send_payment_receipt_with_attachments(
                db=db,
                user=student.user,
                receipt_number=f"PAY-{payment.id:06d}",
                amount=f"{payment_with_relations.amount:,.2f}",
                payment_method=payment_with_relations.payment_method.name if payment_with_relations.payment_method else "Unknown",
                course_name=course_name,
                payment_id=payment.id,
                invoice_pdf_bytes=invoice_pdf,
                receipt_pdf_bytes=receipt_pdf,
                invoice_number=invoice_number
            )
            logger.info(f"Payment receipt email sent to {student.user.email} for payment {payment.id}")
        except Exception as e:
            logger.error(f"Failed to send payment receipt email: {str(e)}")
    
    return payment_data


@router.patch("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: int,
    payment_data: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_payments"))
):
    """Update a payment (Admin only)"""
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Get old invoice_id before update
    old_invoice_id = payment.invoice_id
    old_status = payment.status
    
    # Update payment
    update_data = payment_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(payment, field, value)
    
    await db.commit()
    await db.refresh(payment)
    
    # Handle invoice status update if invoice_id or status changed
    if old_invoice_id:
        invoice_stmt = select(Invoice).where(Invoice.id == old_invoice_id)
        result = await db.execute(invoice_stmt)
        invoice = result.scalar_one_or_none()
        
        if invoice:
            # If payment status changed to COMPLETED, check if invoice is already paid
            if payment.status == PaymentStatus.COMPLETED:
                # Check if invoice is already paid
                if invoice.status == InvoiceStatus.COMPLETED:
                    # Invoice already paid, just return without updating
                    pass
                else:
                    invoice.status = InvoiceStatus.COMPLETED.value
                    
                    # Regenerate PDF with PAID watermark
                try:
                    # Load invoice with relationships
                    invoice_stmt = select(Invoice).where(Invoice.id == old_invoice_id).options(
                        selectinload(Invoice.student).selectinload(Student.user),
                        selectinload(Invoice.items)
                    )
                    result = await db.execute(invoice_stmt)
                    invoice_with_relations = result.scalar_one()
                    
                    # Prepare items for PDF
                    items_data = [
                        {
                            "description": item.description,
                            "quantity": item.quantity,
                            "unit_price": item.unit_price,
                            "amount": item.amount
                        }
                        for item in invoice_with_relations.items
                    ]
                    
                    # Format dates
                    issue_date_str = invoice_with_relations.issue_date.strftime("%B %d, %Y") if invoice_with_relations.issue_date else ""
                    due_date_str = invoice_with_relations.due_date.strftime("%B %d, %Y") if invoice_with_relations.due_date else ""
                    
                    # Get student info
                    student = invoice_with_relations.student
                    student_name = student.user.full_name if student and student.user else "N/A"
                    student_email = student.user.email if student and student.user and student.user.email else ""
                    student_phone = student.user.phone if student and student.user and student.user.phone else ""
                    
                    # Calculate tax rate
                    tax_rate = 15
                    if invoice_with_relations.total_amount > invoice_with_relations.discount_amount:
                        tax_rate = round((invoice_with_relations.tax_amount / (invoice_with_relations.total_amount - invoice_with_relations.discount_amount)) * 100, 2)
                    
                    # Generate PAID PDF
                    pdf_bytes = generate_invoice_pdf_bytes(
                        invoice_number=invoice_with_relations.invoice_number,
                        issue_date=issue_date_str,
                        due_date=due_date_str,
                        student_name=student_name,
                        student_email=student_email,
                        student_phone=student_phone,
                        items=items_data,
                        subtotal=invoice_with_relations.total_amount,
                        discount=invoice_with_relations.discount_amount or 0,
                        tax=invoice_with_relations.tax_amount or 0,
                        grand_total=invoice_with_relations.grand_total,
                        tax_rate=tax_rate,
                        is_paid=True
                    )
                    
                    # Save as paid invoice
                    paid_pdf_path = save_invoice_pdf(pdf_bytes, f"{invoice_with_relations.invoice_number}_paid")
                    invoice.pdf_url = paid_pdf_path
                    
                except Exception as e:
                    # Log error but don't fail the payment update
                    print(f"Error regenerating PDF: {str(e)}")
                
            await db.commit()
    
    # Reload with relationships for response
    payment_stmt = select(Payment).where(Payment.id == payment.id).options(
        selectinload(Payment.student).selectinload(Student.user),
        selectinload(Payment.payment_method),
        selectinload(Payment.enrollment).selectinload(Enrollment.course),
        selectinload(Payment.invoice)
    )
    result = await db.execute(payment_stmt)
    payment = result.scalar_one()
    
    # Add invoice number if invoice exists
    if payment.invoice:
        payment.invoice_number = payment.invoice.invoice_number
    if payment.student and payment.student.user:
        payment.student_name = payment.student.user.full_name
    
    # Check if payment status changed
    new_status = payment.status
    if old_status != new_status:
        try:
            await NotificationService.notify_payment_updated(
                db=db,
                payment_id=payment.id,
                old_status=old_status,
                new_status=new_status,
                created_by=current_user.id
            )
        except Exception as e:
            logger.error(f"Failed to create payment update notification: {str(e)}")
    
    return payment


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="delete_payments"))
):
    """Delete a payment (Admin only)"""
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # Get invoice_id before deletion
    invoice_id = payment.invoice_id
    payment_amount = payment.amount
    
    # Get student and course info before deletion
    student_name = "Unknown"
    course_name = "the course"
    if payment.enrollment and payment.enrollment.student and payment.enrollment.student.user:
        student_name = payment.enrollment.student.user.full_name if payment.enrollment.student.user.full_name else f"{payment.enrollment.student.user.first_name} {payment.enrollment.student.user.last_name}"
    if payment.enrollment and payment.enrollment.course:
        course_name = payment.enrollment.course.name
    
    await db.delete(payment)
    await db.commit()
    
    # Create notification
    try:
        await NotificationService.notify_payment_deleted(db, payment_id, payment_amount, student_name, course_name, current_user.id)
    except Exception as e:
        logger.error(f"Failed to create payment delete notification: {str(e)}")
    
    return None
