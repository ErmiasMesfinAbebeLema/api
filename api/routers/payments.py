from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, datetime

from api.database import get_db
from api.models import User, Payment, Student, Enrollment, PaymentMethod, PaymentStatus, Invoice, InvoiceStatus
from api.schemas import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse
)
from api.routers.auth import get_current_active_user
from api.auth import require_role

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
    
    # Manually set invoice_number for each payment
    for payment in payments:
        if payment.invoice:
            payment.invoice_number = payment.invoice.invoice_number
    
    return payments


@router.get("/student/{student_id}", response_model=List[PaymentResponse])
async def get_student_payments(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_payments"))
):
    """Get all payments for a specific student"""
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
    
    # Create payment
    payment = Payment(
        **payment_data.model_dump(),
        recorded_by=current_user.id
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    
    # After payment is created, mark invoice as COMPLETED
    if payment_data.invoice_id and payment.status == PaymentStatus.COMPLETED:
        # Reload invoice
        invoice_stmt = select(Invoice).where(Invoice.id == payment_data.invoice_id)
        result = await db.execute(invoice_stmt)
        invoice = result.scalar_one_or_none()
        
        if invoice:
            # Mark invoice as COMPLETED
            invoice.status = InvoiceStatus.COMPLETED.value
            await db.commit()
    
    return payment


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
            # If payment status changed to COMPLETED, mark invoice as COMPLETED
            if payment.status == PaymentStatus.COMPLETED:
                invoice.status = InvoiceStatus.COMPLETED.value
            await db.commit()
    
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
    
    await db.delete(payment)
    await db.commit()
    
    # Could add logic here to revert invoice status if needed
    # For now, we'll leave the invoice as-is
    
    return None
