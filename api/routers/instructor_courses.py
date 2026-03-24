"""
Instructor Course Assignment API Router
Handles assigning instructors to courses (super_admin only)
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select, func

from api.database import get_db
from api.models import User, Course, InstructorCourse, UserRole
from api.schemas import (
    InstructorCourseCreate, 
    InstructorCourseResponse, 
    InstructorCourseList
)
from api.auth import get_current_active_user, require_role

router = APIRouter(prefix="/instructor-courses", tags=["instructor-courses"])


@router.post("/", response_model=InstructorCourseResponse)
async def create_instructor_course_assignment(
    assignment: InstructorCourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['super_admin', 'admin'], 'manage_instructors'))
):
    """Assign an instructor to a course (super_admin or admin with manage_instructors permission)"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can assign instructors to courses")
    
    # Verify instructor exists and is an instructor
    result = await db.execute(
        select(User).where(
            and_(User.id == assignment.instructor_id, User.role == UserRole.INSTRUCTOR)
        )
    )
    instructor = result.scalar_one_or_none()
    if not instructor:
        raise HTTPException(status_code=404, detail="Instructor not found")
    
    # Verify course exists
    result = await db.execute(select(Course).where(Course.id == assignment.course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Check if assignment already exists
    result = await db.execute(
        select(InstructorCourse).where(
            and_(
                InstructorCourse.instructor_id == assignment.instructor_id,
                InstructorCourse.course_id == assignment.course_id,
                InstructorCourse.is_active == True
            )
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Instructor is already assigned to this course")
    
    # Create assignment
    db_assignment = InstructorCourse(
        instructor_id=assignment.instructor_id,
        course_id=assignment.course_id,
        assigned_by=current_user.id,
        is_active=assignment.is_active
    )
    
    db.add(db_assignment)
    await db.commit()
    await db.refresh(db_assignment)
    
    return InstructorCourseResponse(
        id=db_assignment.id,
        instructor_id=db_assignment.instructor_id,
        course_id=db_assignment.course_id,
        assigned_by=db_assignment.assigned_by,
        assigned_at=db_assignment.assigned_at,
        is_active=db_assignment.is_active,
        instructor_name=instructor.full_name,
        course_name=course.name
    )


@router.get("/", response_model=InstructorCourseList)
async def list_instructor_course_assignments(
    instructor_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['super_admin', 'admin'], 'manage_instructors'))
):
    """List instructor-course assignments (admin with manage_instructors permission can view)"""
    
    # Build base query
    query = select(InstructorCourse)
    count_query = select(func.count(InstructorCourse.id))
    
    # Apply filters
    if instructor_id:
        query = query.where(InstructorCourse.instructor_id == instructor_id)
        count_query = count_query.where(InstructorCourse.instructor_id == instructor_id)
    if course_id:
        query = query.where(InstructorCourse.course_id == course_id)
        count_query = count_query.where(InstructorCourse.course_id == course_id)
    if is_active is not None:
        query = query.where(InstructorCourse.is_active == is_active)
        count_query = count_query.where(InstructorCourse.is_active == is_active)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get assignments
    query = query.order_by(InstructorCourse.assigned_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    assignments = result.scalars().all()
    
    results = []
    for a in assignments:
        # Get instructor
        result = await db.execute(select(User).where(User.id == a.instructor_id))
        instructor = result.scalar_one_or_none()
        
        # Get course
        result = await db.execute(select(Course).where(Course.id == a.course_id))
        course = result.scalar_one_or_none()
        
        # Get assigned by user
        assigned_by_user = None
        if a.assigned_by:
            result = await db.execute(select(User).where(User.id == a.assigned_by))
            assigned_by_user = result.scalar_one_or_none()
        
        results.append(InstructorCourseResponse(
            id=a.id,
            instructor_id=a.instructor_id,
            course_id=a.course_id,
            assigned_by=a.assigned_by,
            assigned_at=a.assigned_at,
            is_active=a.is_active,
            instructor_name=instructor.full_name if instructor else None,
            course_name=course.name if course else None
        ))
    
    return InstructorCourseList(assignments=results, total=total)


@router.get("/instructor/{instructor_id}", response_model=InstructorCourseList)
async def get_instructor_courses(
    instructor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all courses assigned to an instructor"""
    # Users can view their own assignments, admins can view any
    if current_user.id != instructor_id and current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="You can only view your own course assignments")
    
    result = await db.execute(
        select(InstructorCourse).where(
            and_(
                InstructorCourse.instructor_id == instructor_id,
                InstructorCourse.is_active == True
            )
        )
    )
    assignments = result.scalars().all()
    
    results = []
    for a in assignments:
        result = await db.execute(select(Course).where(Course.id == a.course_id))
        course = result.scalar_one_or_none()
        
        results.append(InstructorCourseResponse(
            id=a.id,
            instructor_id=a.instructor_id,
            course_id=a.course_id,
            assigned_by=a.assigned_by,
            assigned_at=a.assigned_at,
            is_active=a.is_active,
            instructor_name=None,
            course_name=course.name if course else None
        ))
    
    return InstructorCourseList(assignments=results, total=len(results))


@router.get("/course/{course_id}", response_model=InstructorCourseList)
async def get_course_instructors(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all instructors assigned to a course"""
    result = await db.execute(
        select(InstructorCourse).where(
            and_(
                InstructorCourse.course_id == course_id,
                InstructorCourse.is_active == True
            )
        )
    )
    assignments = result.scalars().all()
    
    results = []
    for a in assignments:
        result = await db.execute(select(User).where(User.id == a.instructor_id))
        instructor = result.scalar_one_or_none()
        
        results.append(InstructorCourseResponse(
            id=a.id,
            instructor_id=a.instructor_id,
            course_id=a.course_id,
            assigned_by=a.assigned_by,
            assigned_at=a.assigned_at,
            is_active=a.is_active,
            instructor_name=instructor.full_name if instructor else None,
            course_name=None
        ))
    
    return InstructorCourseList(assignments=results, total=len(results))


@router.delete("/{assignment_id}")
async def delete_instructor_course_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['super_admin', 'admin'], 'manage_instructors'))
):
    """Remove instructor from course (super_admin or admin with manage_instructors permission)"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can remove instructor assignments")
    
    result = await db.execute(select(InstructorCourse).where(InstructorCourse.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Soft delete - set is_active to False
    assignment.is_active = False
    await db.commit()
    
    return {"message": "Instructor assignment removed successfully"}


@router.patch("/{assignment_id}/reactivate", response_model=InstructorCourseResponse)
async def reactivate_instructor_course_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['super_admin', 'admin'], 'manage_instructors'))
):
    """Reactivate an instructor-course assignment (super_admin or admin with manage_instructors permission)"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can reactivate assignments")
    
    result = await db.execute(select(InstructorCourse).where(InstructorCourse.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    assignment.is_active = True
    await db.commit()
    await db.refresh(assignment)
    
    result = await db.execute(select(User).where(User.id == assignment.instructor_id))
    instructor = result.scalar_one_or_none()
    
    result = await db.execute(select(Course).where(Course.id == assignment.course_id))
    course = result.scalar_one_or_none()
    
    return InstructorCourseResponse(
        id=assignment.id,
        instructor_id=assignment.instructor_id,
        course_id=assignment.course_id,
        assigned_by=assignment.assigned_by,
        assigned_at=assignment.assigned_at,
        is_active=assignment.is_active,
        instructor_name=instructor.full_name if instructor else None,
        course_name=course.name if course else None
    )
