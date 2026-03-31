from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from api.database import get_db
from api.models import User, Course
from api.schemas import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CourseList
)
from api.auth import require_role
from api.services.notifications import NotificationService

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.get("", response_model=CourseList)
async def list_courses(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="view_courses"))
):
    """List all active courses"""
    # Get active courses
    result = await db.execute(
        select(Course)
        .where(Course.is_active == True)
        .order_by(Course.name)
        .offset(skip)
        .limit(limit)
    )
    courses = result.scalars().all()
    
    # Get total count
    count_result = await db.execute(
        select(Course).where(Course.is_active == True)
    )
    total = len(count_result.scalars().all())
    
    return {"courses": courses, "total": total}


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="view_courses"))
):
    """Get a specific course"""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    return course


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    course: CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="create_courses"))
):
    """Create a new course (admin only)"""
    db_course = Course(
        name=course.name,
        description=course.description,
        duration_hours=course.duration_hours,
        duration_text=course.duration_text,
        level=course.level,
        is_active=True
    )
    
    db.add(db_course)
    await db.commit()
    await db.refresh(db_course)
    
    # Create notification
    try:
        await NotificationService.notify_course_created(db, db_course.id, current_user.id)
    except Exception as e:
        logger.error(f"Failed to create course notification: {str(e)}")
    
    return db_course


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    course_update: CourseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_courses"))
):
    """Update a course (admin only)"""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Update fields
    update_data = course_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)
    
    course.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(course)
    
    # Create notification
    try:
        await NotificationService.notify_course_updated(db, course.id, list(update_data.keys()), current_user.id)
    except Exception as e:
        logger.error(f"Failed to create course notification: {str(e)}")
    
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="delete_courses"))
):
    """Delete a course (soft delete - just set inactive)"""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Soft delete - just set inactive
    course_name = course.name
    course.is_active = False
    course.updated_at = datetime.utcnow()
    
    await db.commit()
    
    # Create notification
    try:
        await NotificationService.notify_course_deleted(db, course.id, course_name, current_user.id)
    except Exception as e:
        logger.error(f"Failed to create course notification: {str(e)}")
    
    return None
