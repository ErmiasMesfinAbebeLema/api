from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import date, datetime, timedelta
from collections import defaultdict

from api.database import get_db
from api.models import User, Payment, Student, Enrollment, Course, PaymentMethod, PaymentStatus, Attendance, AttendanceStatus
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
        "total_paid": float(total_paid),
        # Attendance stats
        "attendance": {
            "total_records": 0,
            "present": 0,
            "absent": 0,
            "pending": 0,
            "present_rate": 0
        },
        "attendance_this_month": {
            "total_records": 0,
            "present": 0,
            "absent": 0,
            "pending": 0,
            "present_rate": 0
        }
    }
    
    # Get attendance stats (all time) - using SQLAlchemy with explicit conditions
    from sqlalchemy import or_, and_
    
    # Count total
    total_stmt = select(func.count(Attendance.id))
    result = await db.execute(total_stmt)
    total_att = result.scalar() or 0
    
    # Count present (PRESENT + APPROVED) - using explicit OR
    present_stmt = select(func.count(Attendance.id)).where(
        or_(
            Attendance.status == AttendanceStatus.PRESENT,
            Attendance.status == AttendanceStatus.APPROVED
        )
    )
    result = await db.execute(present_stmt)
    present_att = result.scalar() or 0
    
    # Count absent (ABSENT + REJECTED) - using explicit OR
    absent_stmt = select(func.count(Attendance.id)).where(
        or_(
            Attendance.status == AttendanceStatus.ABSENT,
            Attendance.status == AttendanceStatus.REJECTED
        )
    )
    result = await db.execute(absent_stmt)
    absent_att = result.scalar() or 0
    
    # Count pending
    pending_stmt = select(func.count(Attendance.id)).where(
        Attendance.status == AttendanceStatus.PENDING
    )
    result = await db.execute(pending_stmt)
    pending_att = result.scalar() or 0
    
    print(f"DEBUG: Attendance - total: {total_att}, present: {present_att}, absent: {absent_att}, pending: {pending_att}")
    
    return_data = {
        "monthly_revenue": float(monthly_revenue),
        "last_month_revenue": float(last_month_revenue),
        "revenue_change": ((float(monthly_revenue) - float(last_month_revenue)) / float(last_month_revenue) * 100) if last_month_revenue > 0 else 0,
        "total_students": total_students,
        "active_enrollments": active_enrollments,
        "total_paid": float(total_paid),
        "attendance": {
            "total_records": total_att,
            "present": present_att,
            "absent": absent_att,
            "pending": pending_att,
            "present_rate": round(present_att / total_att * 100, 1) if total_att > 0 else 0
        },
        "attendance_this_month": {
            "total_records": total_att,
            "present": present_att,
            "absent": absent_att,
            "pending": pending_att,
            "present_rate": round(present_att / total_att * 100, 1) if total_att > 0 else 0
        }
    }
    
    return return_data


@router.get("/attendance")
async def get_attendance_report(
    course_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "super_admin"], required_permission="view_reports"))
):
    """Get attendance report - statistics per course"""
    # Default to current month if no dates provided
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()
    
    # Build base query
    from sqlalchemy import case
    query = select(
        Attendance.course_id,
        Course.name.label("course_name"),
        func.count(Attendance.id).label("total_records"),
        func.sum(case((Attendance.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present_count"),
        func.sum(case((Attendance.status == AttendanceStatus.ABSENT, 1), else_=0)).label("absent_count"),
        func.sum(case((Attendance.status == AttendanceStatus.PENDING, 1), else_=0)).label("pending_count")
    ).join(
        Course, Course.id == Attendance.course_id
    ).where(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    )
    
    if course_id:
        query = query.where(Attendance.course_id == course_id)
    
    query = query.group_by(Attendance.course_id, Course.name).order_by(Course.name)
    
    result = await db.execute(query)
    course_stats = []
    
    for row in result.all():
        total = row.total_records or 0
        present = row.present_count or 0
        absent = row.absent_count or 0
        pending = row.pending_count or 0
        
        present_rate = (present / total * 100) if total > 0 else 0
        absent_rate = (absent / total * 100) if total > 0 else 0
        
        course_stats.append({
            "course_id": row.course_id,
            "course_name": row.course_name,
            "total_records": total,
            "present": present,
            "absent": absent,
            "pending": pending,
            "present_rate": round(present_rate, 1),
            "absent_rate": round(absent_rate, 1)
        })
    
    # Overall stats
    from sqlalchemy import case
    overall_stmt = select(
        func.count(Attendance.id).label("total"),
        func.sum(case((Attendance.status == AttendanceStatus.PRESENT, 1), else_=0)).label("present"),
        func.sum(case((Attendance.status == AttendanceStatus.ABSENT, 1), else_=0)).label("absent"),
        func.sum(case((Attendance.status == AttendanceStatus.PENDING, 1), else_=0)).label("pending")
    ).where(
        Attendance.date >= start_date,
        Attendance.date <= end_date
    )
    
    if course_id:
        overall_stmt = overall_stmt.where(Attendance.course_id == course_id)
    
    result = await db.execute(overall_stmt)
    row = result.one()
    
    total = row.total or 0
    present = row.present or 0
    absent = row.absent or 0
    pending = row.pending or 0
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "overall": {
            "total": total,
            "present": present,
            "absent": absent,
            "pending": pending,
            "present_rate": round((present / total * 100) if total > 0 else 0, 1),
            "absent_rate": round((absent / total * 100) if total > 0 else 0, 1)
        },
        "by_course": course_stats
    }
