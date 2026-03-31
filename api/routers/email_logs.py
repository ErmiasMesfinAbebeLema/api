"""
Email Logs Router - Admin endpoints for viewing email logs
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)

from api.database import get_db
from api.models import User, EmailLog, UserRole
from api.schemas import (
    EmailLogResponse,
    EmailLogStats,
    EmailLogList
)
from api.routers.auth import get_current_active_user
from api.auth import require_role
from api.services.email_service import email_service

router = APIRouter(prefix="/email-logs", tags=["Email Logs"])


@router.get("", response_model=EmailLogList)
async def list_email_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    status_filter: Optional[str] = None,
    email_type: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_email_logs"))
):
    """
    List all email logs with optional filters (Admin only)
    """
    stmt = select(EmailLog).options(
        selectinload(EmailLog.user)
    )
    
    if status_filter:
        stmt = stmt.where(EmailLog.status == status_filter)
    if email_type:
        stmt = stmt.where(EmailLog.email_type == email_type)
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            (EmailLog.recipient_email.ilike(search_pattern)) |
            (EmailLog.subject.ilike(search_pattern))
        )
    if start_date:
        stmt = stmt.where(EmailLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(EmailLog.created_at <= end_date + timedelta(days=1))
    
    # Get total count
    count_stmt = select(func.count(EmailLog.id))
    if status_filter:
        count_stmt = count_stmt.where(EmailLog.status == status_filter)
    if email_type:
        count_stmt = count_stmt.where(EmailLog.email_type == email_type)
    if search:
        search_pattern = f"%{search}%"
        count_stmt = count_stmt.where(
            (EmailLog.recipient_email.ilike(search_pattern)) |
            (EmailLog.subject.ilike(search_pattern))
        )
    if start_date:
        count_stmt = count_stmt.where(EmailLog.created_at >= start_date)
    if end_date:
        count_stmt = count_stmt.where(EmailLog.created_at <= end_date + timedelta(days=1))
    
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0
    
    # Get paginated results
    stmt = stmt.order_by(EmailLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    return {"logs": logs, "total": total}


@router.get("/stats", response_model=EmailLogStats)
async def get_email_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_email_logs"))
):
    """
    Get email statistics (Admin only)
    """
    # Get total counts by status
    status_counts = await db.execute(
        select(EmailLog.status, func.count(EmailLog.id))
        .group_by(EmailLog.status)
    )
    
    total = 0
    sent = 0
    failed = 0
    pending = 0
    debug = 0
    skipped = 0
    
    for status_val, count in status_counts.all():
        total += count
        if status_val == "sent":
            sent = count
        elif status_val == "failed":
            failed = count
        elif status_val == "pending":
            pending = count
        elif status_val == "debug":
            debug = count
        elif status_val == "skipped":
            skipped = count
    
    # Get today's sent count
    today = datetime.utcnow().date()
    sent_today_result = await db.execute(
        select(func.count(EmailLog.id)).where(
            EmailLog.status == "sent",
            func.date(EmailLog.sent_at) == today
        )
    )
    sent_today = sent_today_result.scalar() or 0
    
    # Get failed by type
    failed_by_type_result = await db.execute(
        select(EmailLog.email_type, func.count(EmailLog.id))
        .where(EmailLog.status == "failed")
        .group_by(EmailLog.email_type)
    )
    failed_by_type = {row[0]: row[1] for row in failed_by_type_result.all()}
    
    # Get recent failures
    recent_failures_stmt = select(EmailLog).where(
        EmailLog.status == "failed"
    ).order_by(EmailLog.created_at.desc()).limit(10)
    result = await db.execute(recent_failures_stmt)
    recent_failures = result.scalars().all()
    
    return EmailLogStats(
        total=total,
        sent=sent,
        failed=failed,
        pending=pending,
        debug=debug,
        skipped=skipped,
        sent_today=sent_today,
        failed_by_type=failed_by_type,
        recent_failures=recent_failures
    )


@router.get("/types")
async def get_email_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_email_logs"))
):
    """
    Get list of email types (Admin only)
    """
    types_result = await db.execute(
        select(EmailLog.email_type).distinct().where(EmailLog.email_type.isnot(None))
    )
    types = [row[0] for row in types_result.all()]
    return {"email_types": types}


@router.get("/{log_id}", response_model=EmailLogResponse)
async def get_email_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_email_logs"))
):
    """
    Get a specific email log entry (Admin only)
    """
    stmt = select(EmailLog).options(
        selectinload(EmailLog.user)
    ).where(EmailLog.id == log_id)
    
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email log not found"
        )
    
    return log


@router.post("/{log_id}/retry")
async def retry_email(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_email_logs"))
):
    """
    Retry sending a failed email (Admin only)
    """
    try:
        email_log = await email_service.retry_failed_email(db, log_id)
        return {
            "message": "Email retry initiated",
            "new_status": email_log.status,
            "retry_count": email_log.retry_count
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to retry email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry email"
        )