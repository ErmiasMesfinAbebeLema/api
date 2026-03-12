from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import date, datetime, timedelta
from collections import defaultdict

from api.database import get_db
from api.models import User, Payment, Student, Enrollment, Course, PaymentMethod, PaymentStatus
from api.routers.auth import get_current_active_user
from api.auth import require_role

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/revenue")
async def get_revenue_report(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_reports"))
):
    """Get revenue report - total revenue within date range"""
    # Default to current month if no dates provided
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()
    
    # Get total revenue
    stmt = select(
        func.coalesce(func.sum(Payment.amount), 0)
    ).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date
    )
    result = await db.execute(stmt)
    total_revenue = result.scalar() or 0
    
    # Get payment count
    count_stmt = select(
        func.count(Payment.id)
    ).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date
    )
    result = await db.execute(count_stmt)
    payment_count = result.scalar() or 0
    
    # Get average payment
    avg_stmt = select(
        func.coalesce(func.avg(Payment.amount), 0)
    ).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date
    )
    result = await db.execute(avg_stmt)
    avg_payment = result.scalar() or 0
    
    # Get daily revenue for the period
    daily_stmt = select(
        Payment.payment_date,
        func.sum(Payment.amount)
    ).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date
    ).group_by(Payment.payment_date).order_by(Payment.payment_date)
    
    result = await db.execute(daily_stmt)
    daily_revenue = [{"date": row[0], "amount": float(row[1])} for row in result.all()]
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_revenue": float(total_revenue),
        "payment_count": payment_count,
        "average_payment": float(avg_payment),
        "daily_revenue": daily_revenue
    }


@router.get("/payments-by-method")
async def get_payments_by_method(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_reports"))
):
    """Get payments grouped by payment method"""
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()
    
    stmt = select(
        PaymentMethod.name,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total")
    ).join(
        Payment, Payment.payment_method_id == PaymentMethod.id
    ).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date
    ).group_by(PaymentMethod.id, PaymentMethod.name)
    
    result = await db.execute(stmt)
    
    return [
        {
            "method": row[0],
            "count": row[1],
            "total": float(row[2]) if row[2] else 0
        }
        for row in result.all()
    ]


@router.get("/payments-by-course")
async def get_payments_by_course(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_reports"))
):
    """Get payments grouped by course"""
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()
    
    stmt = select(
        Course.name,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total")
    ).join(
        Enrollment, Enrollment.id == Payment.enrollment_id
    ).join(
        Course, Course.id == Enrollment.course_id
    ).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date,
        Payment.enrollment_id.isnot(None)
    ).group_by(Course.id, Course.name)
    
    result = await db.execute(stmt)
    
    return [
        {
            "course": row[0],
            "count": row[1],
            "total": float(row[2]) if row[2] else 0
        }
        for row in result.all()
    ]


@router.get("/dashboard-summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_reports"))
):
    """Get summary data for dashboard"""
    today = date.today()
    first_of_month = today.replace(day=1)
    
    # Revenue this month
    monthly_stmt = select(
        func.coalesce(func.sum(Payment.amount), 0)
    ).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= first_of_month,
        Payment.payment_date <= today
    )
    result = await db.execute(monthly_stmt)
    monthly_revenue = result.scalar() or 0
    
    # Revenue last month
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    last_month_stmt = select(
        func.coalesce(func.sum(Payment.amount), 0)
    ).where(
        Payment.status == PaymentStatus.COMPLETED,
        Payment.payment_date >= last_month_start,
        Payment.payment_date <= last_month_end
    )
    result = await db.execute(last_month_stmt)
    last_month_revenue = result.scalar() or 0
    
    # Total students
    student_count_stmt = select(func.count(Student.id))
    result = await db.execute(student_count_stmt)
    total_students = result.scalar() or 0
    
    # Active enrollments
    enrollment_stmt = select(func.count(Enrollment.id)).where(
        Enrollment.status == "active"
    )
    result = await db.execute(enrollment_stmt)
    active_enrollments = result.scalar() or 0
    
    # Total paid
    paid_stmt = select(
        func.coalesce(func.sum(Payment.amount), 0)
    ).where(
        Payment.status == PaymentStatus.COMPLETED
    )
    result = await db.execute(paid_stmt)
    total_paid = result.scalar() or 0
    
    return {
        "monthly_revenue": float(monthly_revenue),
        "last_month_revenue": float(last_month_revenue),
        "revenue_change": ((float(monthly_revenue) - float(last_month_revenue)) / float(last_month_revenue) * 100) if last_month_revenue > 0 else 0,
        "total_students": total_students,
        "active_enrollments": active_enrollments,
        "total_paid": float(total_paid)
    }
