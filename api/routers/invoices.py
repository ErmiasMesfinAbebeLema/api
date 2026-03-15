from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, datetime
from pathlib import Path
import uuid
import logging

logger = logging.getLogger(__name__)

from api.database import get_db
from api.models import User, Invoice, InvoiceItem, Student, Enrollment, InvoiceStatus, UserRole
from api.schemas import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceWithItems,
    InvoiceItemCreate
)
from api.routers.auth import get_current_active_user
from api.auth import require_role
from api.services.pdf_generator import generate_invoice_pdf_bytes, save_invoice_pdf

router = APIRouter(prefix="/invoices", tags=["Invoices"])

# Invoice PDF storage directory
INVOICES_DIR = Path("uploads/invoices")
INVOICES_DIR.mkdir(parents=True, exist_ok=True)


def generate_invoice_number() -> str:
    """Generate unique invoice number in format INV-YYYY-XXXXXX"""
    year = datetime.now().year
    random_part = str(uuid.uuid4())[:6].upper()
    return f"INV-{year}-{random_part}"


async def generate_invoice_pdf(invoice: Invoice, items: List[InvoiceItem], student: Student, is_paid: bool = False) -> str:
    """Generate PDF for invoice and return the file path"""
    # Prepare items for template
    items_data = [
        {
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": f"{item.unit_price:,.2f}",
            "amount": f"{item.amount:,.2f}"
        }
        for item in items
    ]
    
    # Format dates
    issue_date_str = invoice.issue_date.strftime("%B %d, %Y") if invoice.issue_date else ""
    due_date_str = invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else "N/A"
    
    # Get student info
    student_name = student.user.full_name if student.user else "N/A"
    student_email = student.user.email if student.user and student.user.email else "N/A"
    student_phone = student.user.phone if student.user and student.user.phone else "N/A"
    
    # Calculate tax rate from tax amount
    tax_rate = 15
    if invoice.total_amount > invoice.discount_amount:
        tax_rate = round((invoice.tax_amount / (invoice.total_amount - invoice.discount_amount)) * 100, 2)
    
    # Determine PDF filename - use different name for paid invoices
    pdf_filename = f"{invoice.invoice_number}_paid.pdf" if is_paid else f"{invoice.invoice_number}.pdf"
    
    # Generate PDF bytes
    pdf_bytes = generate_invoice_pdf_bytes(
        invoice_number=invoice.invoice_number,
        issue_date=issue_date_str,
        due_date=due_date_str,
        student_name=student_name,
        student_email=student_email,
        student_phone=student_phone,
        items=items_data,
        subtotal=f"{invoice.total_amount:,.2f}",
        discount=f"{invoice.discount_amount:,.2f}",
        tax=f"{invoice.tax_amount:,.2f}",
        grand_total=f"{invoice.grand_total:,.2f}",
        tax_rate=tax_rate,
        is_paid=is_paid
    )
    
    # Save PDF to storage
    pdf_path = save_invoice_pdf(pdf_bytes, f"{invoice.invoice_number}_paid" if is_paid else invoice.invoice_number)
    
    return pdf_path


@router.get("")
async def list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    student_id: Optional[int] = None,
    status_filter: Optional[InvoiceStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_invoices"))
):
    """List all invoices with optional filters"""
    stmt = select(Invoice).options(
        selectinload(Invoice.student).selectinload(Student.user)
    )
    
    if student_id:
        stmt = stmt.where(Invoice.student_id == student_id)
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    if start_date:
        stmt = stmt.where(Invoice.issue_date >= start_date)
    if end_date:
        stmt = stmt.where(Invoice.issue_date <= end_date)
    
    stmt = stmt.order_by(Invoice.issue_date.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    invoices = result.scalars().all()
    
    # Add student name to each invoice
    for invoice in invoices:
        if invoice.student and invoice.student.user:
            invoice.student_name = invoice.student.user.full_name
        else:
            invoice.student_name = f"Student #{invoice.student_id}"
    
    # Get total count
    count_stmt = select(func.count(Invoice.id))
    if student_id:
        count_stmt = count_stmt.where(Invoice.student_id == student_id)
    if status_filter:
        count_stmt = count_stmt.where(Invoice.status == status_filter)
    if start_date:
        count_stmt = count_stmt.where(Invoice.issue_date >= start_date)
    if end_date:
        count_stmt = count_stmt.where(Invoice.issue_date <= end_date)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0
    
    return {"invoices": invoices, "total": total}


@router.get("/student/{student_id}", response_model=List[InvoiceResponse])
async def get_student_invoices(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all invoices for a specific student (admin or the student themselves)"""
    # Check if user is admin
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        # Admin can view any student's invoices
        pass
    elif current_user.role == UserRole.STUDENT:
        # Students can only view their own invoices
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
                detail="You can only view your own invoices"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    stmt = select(Invoice).where(Invoice.student_id == student_id).options(
        selectinload(Invoice.student).selectinload(Student.user)
    ).order_by(Invoice.issue_date.desc())
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{invoice_id}", response_model=InvoiceWithItems)
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_invoices"))
):
    """Get a specific invoice with items"""
    stmt = select(Invoice).where(Invoice.id == invoice_id).options(
        selectinload(Invoice.student).selectinload(Student.user),
        selectinload(Invoice.items).selectinload(InvoiceItem.enrollment).selectinload(Enrollment.course)
    )
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return invoice


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="create_invoices"))
):
    """Create a new invoice (Admin only)"""
    # Verify student exists
    student_stmt = select(Student).where(Student.id == invoice_data.student_id)
    result = await db.execute(student_stmt)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Calculate totals
    subtotal = sum(item.quantity * item.unit_price for item in invoice_data.items)
    discount = invoice_data.discount_amount or 0
    tax = invoice_data.tax_amount or 0
    grand_total = subtotal - discount + tax
    
    # Create invoice
    invoice = Invoice(
        invoice_number=generate_invoice_number(),
        student_id=invoice_data.student_id,
        issue_date=invoice_data.issue_date,
        due_date=invoice_data.due_date,
        total_amount=subtotal,
        discount_amount=discount,
        tax_amount=tax,
        grand_total=grand_total,
        notes=invoice_data.notes,
        status=InvoiceStatus.DRAFT,
        created_by=current_user.id
    )
    db.add(invoice)
    await db.flush()  # Get the invoice ID
    
    # Create invoice items
    for item_data in invoice_data.items:
        item = InvoiceItem(
            invoice_id=invoice.id,
            enrollment_id=item_data.enrollment_id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            amount=item_data.quantity * item_data.unit_price
        )
        db.add(item)
    
    await db.commit()
    await db.refresh(invoice)
    
    # Auto-generate PDF
    try:
        logger.info(f"Starting PDF generation for invoice ID: {invoice.id}")
        
        # Reload with relationships for PDF generation
        stmt = select(Invoice).where(Invoice.id == invoice.id).options(
            selectinload(Invoice.student).selectinload(Student.user),
            selectinload(Invoice.items)
        )
        result = await db.execute(stmt)
        invoice_with_relations = result.scalar_one()
        
        logger.info(f"Loaded invoice: {invoice_with_relations.invoice_number}")
        
        # Get student user info
        student_user = invoice_with_relations.student.user
        student_name = student_user.full_name if student_user else f"Student #{invoice_with_relations.student.id}"
        student_email = student_user.email if student_user else ""
        student_phone = student_user.phone if student_user and student_user.phone else ""
        
        logger.info(f"Student: {student_name}, {student_email}")
        
        # Format dates
        issue_date_str = invoice_with_relations.issue_date.strftime("%B %d, %Y") if invoice_with_relations.issue_date else ""
        due_date_str = invoice_with_relations.due_date.strftime("%B %d, %Y") if invoice_with_relations.due_date else ""
        
        # Prepare items for PDF
        items_data = []
        for item in invoice_with_relations.items:
            items_data.append({
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "amount": item.amount
            })
        
        logger.info(f"Generating PDF with {len(items_data)} items")
        
        # Generate PDF bytes
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
            grand_total=invoice_with_relations.grand_total
        )
        
        logger.info(f"PDF generated, size: {len(pdf_bytes)} bytes")
        
        # Save PDF to file
        pdf_url = save_invoice_pdf(pdf_bytes, invoice_with_relations.invoice_number)
        
        logger.info(f"PDF saved to: {pdf_url}")
        
        # Update invoice with PDF URL
        invoice.pdf_url = pdf_url
        await db.commit()
        
        logger.info(f"Invoice updated with PDF URL")
    except Exception as e:
        # Log error but don't fail invoice creation
        logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
    
    return invoice


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_invoices"))
):
    """Update an invoice (Admin only)"""
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # If status is being changed, recalculate grand total if needed
    update_data = invoice_data.model_dump(exclude_unset=True)
    
    if 'discount_amount' in update_data or 'tax_amount' in update_data:
        invoice.grand_total = invoice.total_amount - invoice.discount_amount + invoice.tax_amount
    
    for field, value in update_data.items():
        setattr(invoice, field, value)
    
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="delete_invoices"))
):
    """Delete an invoice (Admin only)"""
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    await db.delete(invoice)
    await db.commit()
    
    return None


@router.post("/{invoice_id}/generate-pdf")
async def generate_invoice_pdf_endpoint(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_invoices"))
):
    """Generate PDF for an invoice (Admin only)"""
    stmt = select(Invoice).where(Invoice.id == invoice_id).options(
        selectinload(Invoice.student).selectinload(Student.user),
        selectinload(Invoice.items)
    )
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Generate PDF
    pdf_path = await generate_invoice_pdf(invoice, invoice.items, invoice.student)
    
    # Update invoice with PDF URL
    invoice.pdf_url = f"/uploads/invoices/{invoice.invoice_number}.pdf"
    await db.commit()
    
    return {
        "message": "PDF generated successfully",
        "pdf_url": invoice.pdf_url
    }


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_invoices"))
):
    """Download invoice PDF"""
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    if not invoice.pdf_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not generated yet"
        )
    
    pdf_path = Path("uploads") / "invoices" / f"{invoice.invoice_number}.pdf"
    
    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found"
        )
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{invoice.invoice_number}.pdf"
    )


@router.get("/{invoice_id}/receipt-pdf")
async def download_receipt_pdf(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_invoices"))
):
    """Download receipt PDF (paid version of invoice)"""
    stmt = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Check if paid PDF exists
    paid_pdf_path = Path("uploads") / "invoices" / f"{invoice.invoice_number}_paid.pdf"
    
    if not paid_pdf_path.exists():
        # Fall back to original PDF if paid version doesn't exist
        original_pdf_path = Path("uploads") / "invoices" / f"{invoice.invoice_number}.pdf"
        if not original_pdf_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF not generated yet"
            )
        return FileResponse(
            original_pdf_path,
            media_type="application/pdf",
            filename=f"{invoice.invoice_number}.pdf"
        )
    
    return FileResponse(
        paid_pdf_path,
        media_type="application/pdf",
        filename=f"{invoice.invoice_number}_paid.pdf"
    )
