"""
Attendance API Router
Handles attendance tracking for students
"""
from typing import Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from api.database import get_db
from api.models import User, Attendance, Student, Course, UserRole, AttendanceStatus, InstructorSchedule, Enrollment, CourseEnrollmentStatus, InstructorCourse
from api.schemas import (
    AttendanceCreate, 
    AttendanceUpdate, 
    AttendanceResponse, 
    AttendanceList,
    AttendanceCalendarResponse,
    InstructorScheduleCreate,
    InstructorScheduleBulkCreate,
    InstructorScheduleUpdate,
    InstructorScheduleResponse,
    InstructorScheduleList
)
from api.auth import get_current_active_user

router = APIRouter(prefix="/attendances", tags=["attendances"])


async def get_student_name(student: Student, db: AsyncSession = None) -> str:
    """Get student's full name from user relationship"""
    if not student:
        return ""
    if student.user_id:
        result = await db.execute(select(User).filter(User.id == student.user_id))
        user = result.scalar_one_or_none()
        if user:
            return user.full_name
    return "Unknown"


async def get_course_name(course: Course) -> str:
    """Get course name"""
    return course.name if course else ""


# ==============================================================================
# ATTENDANCE ROUTES - Specific paths FIRST (no path parameters)
# ==============================================================================

@router.post("/", response_model=AttendanceResponse)
async def create_attendance(
    attendance: AttendanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new attendance record"""
    result = await db.execute(select(Student).filter(Student.id == attendance.student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    result = await db.execute(select(Course).filter(Course.id == attendance.course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Verify student is enrolled in this course
    result = await db.execute(select(Enrollment).filter(
        and_(
            Enrollment.student_id == attendance.student_id,
            Enrollment.course_id == attendance.course_id,
            Enrollment.status == CourseEnrollmentStatus.ACTIVE
        )
    ))
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=403, detail="You are not enrolled in this course")
    
    result = await db.execute(select(Attendance).filter(
        and_(
            Attendance.student_id == attendance.student_id,
            Attendance.course_id == attendance.course_id,
            Attendance.date == attendance.date,
            Attendance.time_slot == attendance.time_slot
        )
    ))
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Attendance record already exists")
    
    db_attendance = Attendance(
        student_id=attendance.student_id,
        course_id=attendance.course_id,
        instructor_id=current_user.id if current_user.role in [UserRole.INSTRUCTOR, UserRole.ADMIN, UserRole.SUPER_ADMIN] else None,
        date=attendance.date,
        time_slot=attendance.time_slot,
        status=attendance.status,
        notes=attendance.notes
    )
    
    db.add(db_attendance)
    await db.commit()
    await db.refresh(db_attendance)
    
    response = AttendanceResponse(
        id=db_attendance.id,
        student_id=db_attendance.student_id,
        course_id=db_attendance.course_id,
        instructor_id=db_attendance.instructor_id,
        date=db_attendance.date,
        time_slot=db_attendance.time_slot,
        status=db_attendance.status,
        notes=db_attendance.notes,
        student_name=await get_student_name(student, db),
        course_name=await get_course_name(course),
        instructor_name=current_user.full_name if current_user else None,
        created_at=db_attendance.created_at,
        updated_at=db_attendance.updated_at
    )
    
    return response


@router.get("/", response_model=AttendanceList)
async def list_attendances(
    student_id: Optional[int] = Query(None),
    course_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    status: Optional[AttendanceStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List attendance records with filters"""
    # Filter by instructor's assigned courses if user is an instructor
    if current_user.role == UserRole.INSTRUCTOR:
        # Get instructor's assigned courses
        result = await db.execute(
            select(InstructorCourse).where(
                and_(
                    InstructorCourse.instructor_id == current_user.id,
                    InstructorCourse.is_active == True
                )
            )
        )
        assignments = result.scalars().all()
        instructor_course_ids = [a.course_id for a in assignments]
        
        if instructor_course_ids:
            query = select(Attendance).filter(
                Attendance.course_id.in_(instructor_course_ids)
            )
        else:
            return AttendanceList(attendances=[], total=0)
    else:
        query = select(Attendance)
    
    if student_id:
        query = query.filter(Attendance.student_id == student_id)
    if course_id:
        query = query.filter(Attendance.course_id == course_id)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    if status:
        query = query.filter(Attendance.status == status)
    
    count_query = query.with_only_columns(Attendance.id)
    result = await db.execute(count_query)
    total = len(result.scalars().all())
    
    query = query.order_by(Attendance.date.desc(), Attendance.time_slot.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    attendances = result.scalars().all()
    
    results = []
    for att in attendances:
        result = await db.execute(select(Student).filter(Student.id == att.student_id))
        student = result.scalar_one_or_none()
        result = await db.execute(select(Course).filter(Course.id == att.course_id))
        course = result.scalar_one_or_none()
        result = await db.execute(select(User).filter(User.id == att.instructor_id)) if att.instructor_id else None
        instructor = result.scalar_one_or_none() if result else None
        
        results.append(AttendanceResponse(
            id=att.id,
            student_id=att.student_id,
            course_id=att.course_id,
            instructor_id=att.instructor_id,
            date=att.date,
            time_slot=att.time_slot,
            status=att.status,
            notes=att.notes,
            student_name=await get_student_name(student, db) if student else None,
            course_name=await get_course_name(course) if course else None,
            instructor_name=instructor.full_name if instructor else None,
            created_at=att.created_at,
            updated_at=att.updated_at
        ))
    
    return AttendanceList(attendances=results, total=total)


@router.get("/calendar", response_model=list[AttendanceCalendarResponse])
async def get_attendance_calendar(
    start_date: date = Query(...),
    end_date: date = Query(...),
    course_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get attendance records grouped by date and time slot for calendar view"""
    # Filter by instructor's assigned courses if user is an instructor
    if current_user.role == UserRole.INSTRUCTOR:
        # Get instructor's assigned courses
        result = await db.execute(
            select(InstructorCourse).where(
                and_(
                    InstructorCourse.instructor_id == current_user.id,
                    InstructorCourse.is_active == True
                )
            )
        )
        assignments = result.scalars().all()
        instructor_course_ids = [a.course_id for a in assignments]
        
        if instructor_course_ids:
            query = select(Attendance).filter(
                and_(
                    Attendance.date >= start_date,
                    Attendance.date <= end_date,
                    Attendance.course_id.in_(instructor_course_ids)
                )
            )
        else:
            return []
    else:
        query = select(Attendance).filter(
            and_(
                Attendance.date >= start_date,
                Attendance.date <= end_date
            )
        )
    
    if course_id:
        query = query.filter(Attendance.course_id == course_id)
    
    query = query.order_by(Attendance.date, Attendance.time_slot)
    result = await db.execute(query)
    attendances = result.scalars().all()
    
    calendar_data = {}
    for att in attendances:
        key = (att.date, att.time_slot)
        if key not in calendar_data:
            calendar_data[key] = []
        
        result = await db.execute(select(Student).filter(Student.id == att.student_id))
        student = result.scalar_one_or_none()
        result = await db.execute(select(Course).filter(Course.id == att.course_id))
        course = result.scalar_one_or_none()
        result = await db.execute(select(User).filter(User.id == att.instructor_id)) if att.instructor_id else None
        instructor = result.scalar_one_or_none() if result else None
        
        calendar_data[key].append(AttendanceResponse(
            id=att.id,
            student_id=att.student_id,
            course_id=att.course_id,
            instructor_id=att.instructor_id,
            date=att.date,
            time_slot=att.time_slot,
            status=att.status,
            notes=att.notes,
            student_name=await get_student_name(student, db) if student else None,
            course_name=await get_course_name(course) if course else None,
            instructor_name=instructor.full_name if instructor else None,
            created_at=att.created_at,
            updated_at=att.updated_at
        ))
    
    result_list = []
    for (d, t), records in sorted(calendar_data.items()):
        result_list.append(AttendanceCalendarResponse(date=d, time_slot=t, records=records))
    
    return result_list


@router.get("/pending", response_model=AttendanceList)
async def get_pending_attendances(
    course_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get pending attendance requests"""
    # Filter by instructor's assigned courses if user is an instructor
    if current_user.role == UserRole.INSTRUCTOR:
        # Get instructor's assigned courses
        result = await db.execute(
            select(InstructorCourse).where(
                and_(
                    InstructorCourse.instructor_id == current_user.id,
                    InstructorCourse.is_active == True
                )
            )
        )
        assignments = result.scalars().all()
        instructor_course_ids = [a.course_id for a in assignments]
        
        if instructor_course_ids:
            query = select(Attendance).filter(
                and_(
                    Attendance.status == AttendanceStatus.PENDING,
                    Attendance.course_id.in_(instructor_course_ids)
                )
            )
        else:
            return AttendanceList(attendances=[], total=0)
    else:
        query = select(Attendance).filter(Attendance.status == AttendanceStatus.PENDING)
    
    if course_id:
        query = query.filter(Attendance.course_id == course_id)
    
    count_query = query.with_only_columns(Attendance.id)
    result = await db.execute(count_query)
    total = len(result.scalars().all())
    
    query = query.order_by(Attendance.date.desc(), Attendance.time_slot.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    attendances = result.scalars().all()
    
    results = []
    for att in attendances:
        result = await db.execute(select(Student).filter(Student.id == att.student_id))
        student = result.scalar_one_or_none()
        result = await db.execute(select(Course).filter(Course.id == att.course_id))
        course = result.scalar_one_or_none()
        result = await db.execute(select(User).filter(User.id == att.instructor_id)) if att.instructor_id else None
        instructor = result.scalar_one_or_none() if result else None
        
        results.append(AttendanceResponse(
            id=att.id,
            student_id=att.student_id,
            course_id=att.course_id,
            instructor_id=att.instructor_id,
            date=att.date,
            time_slot=att.time_slot,
            status=att.status,
            notes=att.notes,
            student_name=await get_student_name(student, db) if student else None,
            course_name=await get_course_name(course) if course else None,
            instructor_name=instructor.full_name if instructor else None,
            created_at=att.created_at,
            updated_at=att.updated_at
        ))
    
    return AttendanceList(attendances=results, total=total)


# Bulk approve/reject endpoints
@router.post("/bulk/approve", response_model=AttendanceList)
async def bulk_approve_attendances(
    attendance_ids: list[int],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Approve multiple attendance records at once"""
    if not attendance_ids:
        raise HTTPException(status_code=400, detail="No attendance IDs provided")
    
    # Get all attendances
    result = await db.execute(
        select(Attendance).filter(Attendance.id.in_(attendance_ids))
    )
    attendances = result.scalars().all()
    
    if not attendances:
        raise HTTPException(status_code=404, detail="No attendances found")
    
    # Verify permission for all records
    if current_user.role == UserRole.INSTRUCTOR:
        result = await db.execute(
            select(InstructorCourse).where(
                and_(
                    InstructorCourse.instructor_id == current_user.id,
                    InstructorCourse.is_active == True
                )
            )
        )
        assignments = result.scalars().all()
        instructor_course_ids = [a.course_id for a in assignments]
        
        for att in attendances:
            if att.course_id not in instructor_course_ids:
                raise HTTPException(status_code=403, detail="You can only manage attendance for your assigned courses")
    
    # Update all to approved
    results = []
    for att in attendances:
        if att.status == AttendanceStatus.PENDING:
            att.status = AttendanceStatus.PRESENT
            if not att.instructor_id:
                att.instructor_id = current_user.id
            att.updated_at = datetime.utcnow()
            
            # Build response
            result = await db.execute(select(Student).filter(Student.id == att.student_id))
            student = result.scalar_one_or_none()
            result = await db.execute(select(Course).filter(Course.id == att.course_id))
            course = result.scalar_one_or_none()
            result = await db.execute(select(User).filter(User.id == att.instructor_id)) if att.instructor_id else None
            instructor = result.scalar_one_or_none() if result else None
            
            results.append(AttendanceResponse(
                id=att.id,
                student_id=att.student_id,
                course_id=att.course_id,
                instructor_id=att.instructor_id,
                date=att.date,
                time_slot=att.time_slot,
                status=att.status,
                notes=att.notes,
                student_name=await get_student_name(student, db) if student else None,
                course_name=await get_course_name(course) if course else None,
                instructor_name=instructor.full_name if instructor else None,
                created_at=att.created_at,
                updated_at=att.updated_at
            ))
    
    await db.commit()
    
    return AttendanceList(attendances=results, total=len(results))


@router.post("/bulk/reject", response_model=AttendanceList)
async def bulk_reject_attendances(
    attendance_ids: list[int],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Reject multiple attendance records at once"""
    if not attendance_ids:
        raise HTTPException(status_code=400, detail="No attendance IDs provided")
    
    # Get all attendances
    result = await db.execute(
        select(Attendance).filter(Attendance.id.in_(attendance_ids))
    )
    attendances = result.scalars().all()
    
    if not attendances:
        raise HTTPException(status_code=404, detail="No attendances found")
    
    # Verify permission for all records
    if current_user.role == UserRole.INSTRUCTOR:
        result = await db.execute(
            select(InstructorCourse).where(
                and_(
                    InstructorCourse.instructor_id == current_user.id,
                    InstructorCourse.is_active == True
                )
            )
        )
        assignments = result.scalars().all()
        instructor_course_ids = [a.course_id for a in assignments]
        
        for att in attendances:
            if att.course_id not in instructor_course_ids:
                raise HTTPException(status_code=403, detail="You can only manage attendance for your assigned courses")
    
    # Update all to rejected/absent
    results = []
    for att in attendances:
        if att.status == AttendanceStatus.PENDING:
            att.status = AttendanceStatus.ABSENT
            if not att.instructor_id:
                att.instructor_id = current_user.id
            att.updated_at = datetime.utcnow()
            
            # Build response
            result = await db.execute(select(Student).filter(Student.id == att.student_id))
            student = result.scalar_one_or_none()
            result = await db.execute(select(Course).filter(Course.id == att.course_id))
            course = result.scalar_one_or_none()
            result = await db.execute(select(User).filter(User.id == att.instructor_id)) if att.instructor_id else None
            instructor = result.scalar_one_or_none() if result else None
            
            results.append(AttendanceResponse(
                id=att.id,
                student_id=att.student_id,
                course_id=att.course_id,
                instructor_id=att.instructor_id,
                date=att.date,
                time_slot=att.time_slot,
                status=att.status,
                notes=att.notes,
                student_name=await get_student_name(student, db) if student else None,
                course_name=await get_course_name(course) if course else None,
                instructor_name=instructor.full_name if instructor else None,
                created_at=att.created_at,
                updated_at=att.updated_at
            ))
    
    await db.commit()
    
    return AttendanceList(attendances=results, total=len(results))


# ==============================================================================
# INSTRUCTOR SCHEDULE ROUTES - Specific paths FIRST (no path parameters)
# ==============================================================================

@router.post("/schedules", response_model=InstructorScheduleResponse)
async def create_schedule(
    schedule: InstructorScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new instructor schedule"""
    # Verify the instructor is assigned to this course
    if schedule.course_id:
        result = await db.execute(
            select(InstructorCourse).where(
                and_(
                    InstructorCourse.instructor_id == current_user.id,
                    InstructorCourse.course_id == schedule.course_id,
                    InstructorCourse.is_active == True
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=403, detail="You are not assigned to this course")
        
        result = await db.execute(select(Course).filter(Course.id == schedule.course_id))
        course = result.scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
    else:
        raise HTTPException(status_code=400, detail="Course ID is required")
    
    # Check for schedule conflicts
    conflict_stmt = select(InstructorSchedule).where(
        and_(
            InstructorSchedule.date == schedule.date,
            InstructorSchedule.is_active == True,
            or_(
                and_(InstructorSchedule.start_time < schedule.end_time, InstructorSchedule.end_time > schedule.start_time)
            )
        )
    )
    
    # For admins/super_admins, check any instructor; for instructors, check only their schedules
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        conflict_stmt = conflict_stmt.where(InstructorSchedule.instructor_id == current_user.id)
    
    result = await db.execute(conflict_stmt)
    conflicts = result.scalars().all()
    
    if conflicts:
        conflict_details = []
        for c in conflicts:
            result = await db.execute(select(Course).filter(Course.id == c.course_id))
            course = result.scalar_one_or_none()
            course_name = course.name if course else 'Unknown course'
            conflict_details.append(f"{c.start_time}:00-{c.end_time}:00 ({course_name})")
        
        raise HTTPException(
            status_code=409,
            detail=f"Schedule conflict detected: {', '.join(conflict_details)}"
        )
    
    db_schedule = InstructorSchedule(
        instructor_id=current_user.id,
        course_id=schedule.course_id,
        date=schedule.date,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        notes=schedule.notes
    )
    
    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)
    
    result = await db.execute(select(Course).filter(Course.id == schedule.course_id)) if schedule.course_id else None
    course = result.scalar_one_or_none() if result else None
    
    return InstructorScheduleResponse(
        id=db_schedule.id,
        instructor_id=db_schedule.instructor_id,
        course_id=db_schedule.course_id,
        date=db_schedule.date,
        start_time=db_schedule.start_time,
        end_time=db_schedule.end_time,
        notes=db_schedule.notes,
        is_active=db_schedule.is_active,
        created_at=db_schedule.created_at,
        updated_at=db_schedule.updated_at,
        course_name=course.name if course else None,
        instructor_name=current_user.full_name
    )


@router.post("/schedules/bulk", response_model=InstructorScheduleList)
async def create_bulk_schedules(
    schedule_bulk: InstructorScheduleBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create multiple instructor schedules for a date range"""
    # Verify the instructor is assigned to this course
    if schedule_bulk.course_id:
        result = await db.execute(
            select(InstructorCourse).where(
                and_(
                    InstructorCourse.instructor_id == current_user.id,
                    InstructorCourse.course_id == schedule_bulk.course_id,
                    InstructorCourse.is_active == True
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=403, detail="You are not assigned to this course")
        
        result = await db.execute(select(Course).filter(Course.id == schedule_bulk.course_id))
        course = result.scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
    else:
        raise HTTPException(status_code=400, detail="Course ID is required")
    
    # Check for conflicts in each scheduled date
    conflict_warnings = []
    current_date = schedule_bulk.start_date
    while current_date <= schedule_bulk.end_date:
        if current_date.weekday() in schedule_bulk.days_of_week:
            # Check for schedule conflicts
            conflict_stmt = select(InstructorSchedule).where(
                and_(
                    InstructorSchedule.date == current_date,
                    InstructorSchedule.is_active == True,
                    or_(
                        and_(InstructorSchedule.start_time < schedule_bulk.end_time, InstructorSchedule.end_time > schedule_bulk.start_time)
                    )
                )
            )
            
            if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
                conflict_stmt = conflict_stmt.where(InstructorSchedule.instructor_id == current_user.id)
            
            result = await db.execute(conflict_stmt)
            conflicts = result.scalars().all()
            
            if conflicts:
                for c in conflicts:
                    conflict_warnings.append(f"{current_date} {c.start_time}:00-{c.end_time}:00")
            
            # Create the schedule
            db_schedule = InstructorSchedule(
                instructor_id=current_user.id,
                course_id=schedule_bulk.course_id,
                date=current_date,
                start_time=schedule_bulk.start_time,
                end_time=schedule_bulk.end_time,
                notes=schedule_bulk.notes
            )
            db.add(db_schedule)
            schedules.append(db_schedule)
        
        current_date += timedelta(days=1)
    
    await db.commit()
    
    # If there were conflicts, return warning in response
    if conflict_warnings:
        return InstructorScheduleList(
            schedules=[],
            total=0,
            message=f"Schedule conflicts detected: {', '.join(conflict_warnings)}. No schedules were created."
        )
    
    for schedule in schedules:
        await db.refresh(schedule)
    
    result = await db.execute(select(Course).filter(Course.id == schedule_bulk.course_id)) if schedule_bulk.course_id else None
    course = result.scalar_one_or_none() if result else None
    
    results = []
    for schedule in schedules:
        results.append(InstructorScheduleResponse(
            id=schedule.id,
            instructor_id=schedule.instructor_id,
            course_id=schedule.course_id,
            date=schedule.date,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            notes=schedule.notes,
            is_active=schedule.is_active,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            course_name=course.name if course else None,
            instructor_name=current_user.full_name
        ))
    
    return InstructorScheduleList(schedules=results, total=len(results))


@router.get("/schedules", response_model=InstructorScheduleList)
async def list_schedules(
    course_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    skip: int = Query(0),
    limit: int = Query(100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List instructor schedules"""
    query = select(InstructorSchedule).filter(InstructorSchedule.instructor_id == current_user.id)
    
    if course_id:
        query = query.filter(InstructorSchedule.course_id == course_id)
    if start_date:
        try:
            parsed_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(InstructorSchedule.date >= parsed_date)
        except ValueError:
            pass
    if end_date:
        try:
            parsed_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(InstructorSchedule.date <= parsed_date)
        except ValueError:
            pass
    
    count_query = query.with_only_columns(InstructorSchedule.id)
    result = await db.execute(count_query)
    total = len(result.scalars().all())
    
    schedules_query = query.order_by(InstructorSchedule.date, InstructorSchedule.start_time).offset(skip).limit(limit)
    result = await db.execute(schedules_query)
    schedules = result.scalars().all()
    
    results = []
    for schedule in schedules:
        result = await db.execute(select(Course).filter(Course.id == schedule.course_id)) if schedule.course_id else None
        course = result.scalar_one_or_none() if result else None
        result = await db.execute(select(User).filter(User.id == schedule.instructor_id))
        instructor = result.scalar_one_or_none()
        
        results.append(InstructorScheduleResponse(
            id=schedule.id,
            instructor_id=schedule.instructor_id,
            course_id=schedule.course_id,
            date=schedule.date,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            notes=schedule.notes,
            is_active=schedule.is_active,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            course_name=course.name if course else None,
            instructor_name=instructor.full_name if instructor else None
        ))
    
    return InstructorScheduleList(schedules=results, total=total)


# Auto-mark absent for enrolled students who didn't request
@router.post("/auto-absent", response_model=AttendanceList)
async def auto_mark_absent(
    course_id: int = Query(...),
    date: date = Query(...),
    time_slot: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Auto-mark absent for students who didn't request attendance for a scheduled slot"""
    # Only instructors and admins can do this
    if current_user.role not in [UserRole.INSTRUCTOR, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Only instructors can auto-mark absent")
    
    # Verify instructor is assigned to this course
    if current_user.role == UserRole.INSTRUCTOR:
        result = await db.execute(
            select(InstructorCourse).where(
                and_(
                    InstructorCourse.instructor_id == current_user.id,
                    InstructorCourse.course_id == course_id,
                    InstructorCourse.is_active == True
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=403, detail="You are not assigned to this course")
    
    # Get all active enrollments for this course
    result = await db.execute(
        select(Enrollment).where(
            and_(
                Enrollment.course_id == course_id,
                Enrollment.status == CourseEnrollmentStatus.ACTIVE
            )
        )
    )
    enrollments = result.scalars().all()
    
    if not enrollments:
        return AttendanceList(attendances=[], total=0)
    
    # Get existing attendance records for this slot
    result = await db.execute(
        select(Attendance).where(
            and_(
                Attendance.course_id == course_id,
                Attendance.date == date,
                Attendance.time_slot == time_slot
            )
        )
    )
    existing_attendances = result.scalars().all()
    student_ids_with_attendance = {a.student_id for a in existing_attendances}
    
    # Create absent records for students who don't have attendance
    new_absents = []
    for enrollment in enrollments:
        if enrollment.student_id not in student_ids_with_attendance:
            db_attendance = Attendance(
                student_id=enrollment.student_id,
                course_id=course_id,
                instructor_id=current_user.id,
                date=date,
                time_slot=time_slot,
                status=AttendanceStatus.ABSENT,
                notes="Auto-marked absent - no attendance request submitted"
            )
            db.add(db_attendance)
            new_absents.append(db_attendance)
    
    await db.commit()
    
    # Refresh to get IDs
    for att in new_absents:
        await db.refresh(att)
    
    # Build response
    results = []
    for att in new_absents:
        result = await db.execute(select(Student).filter(Student.id == att.student_id))
        student = result.scalar_one_or_none()
        result = await db.execute(select(Course).filter(Course.id == att.course_id))
        course = result.scalar_one_or_none()
        result = await db.execute(select(User).filter(User.id == att.instructor_id)) if att.instructor_id else None
        instructor = result.scalar_one_or_none() if result else None
        
        results.append(AttendanceResponse(
            id=att.id,
            student_id=att.student_id,
            course_id=att.course_id,
            instructor_id=att.instructor_id,
            date=att.date,
            time_slot=att.time_slot,
            status=att.status,
            notes=att.notes,
            student_name=await get_student_name(student, db) if student else None,
            course_name=await get_course_name(course) if course else None,
            instructor_name=instructor.full_name if instructor else None,
            created_at=att.created_at,
            updated_at=att.updated_at
        ))
    
    return AttendanceList(attendances=results, total=len(results))


# Student endpoint: Get available schedules for enrolled courses
@router.get("/student/schedules", response_model=InstructorScheduleList)
async def get_student_schedules(
    course_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get available schedules for student's enrolled courses"""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Only students can access this endpoint")
    
    result = await db.execute(select(Student).filter(Student.user_id == current_user.id))
    student = result.scalar_one_or_none()
    
    if not student:
        return InstructorScheduleList(schedules=[], total=0)
    
    result = await db.execute(select(Enrollment).filter(
        and_(
            Enrollment.student_id == student.id,
            Enrollment.status == CourseEnrollmentStatus.ACTIVE
        )
    ))
    enrollments = result.scalars().all()
    enrolled_course_ids = [e.course_id for e in enrollments]
    
    if not enrolled_course_ids:
        return InstructorScheduleList(schedules=[], total=0)
    
    query = select(InstructorSchedule).filter(
        and_(
            InstructorSchedule.course_id.in_(enrolled_course_ids),
            InstructorSchedule.is_active == True
        )
    )
    
    if course_id:
        query = query.filter(InstructorSchedule.course_id == course_id)
    if start_date:
        try:
            parsed_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(InstructorSchedule.date >= parsed_date)
        except ValueError:
            pass
    if end_date:
        try:
            parsed_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(InstructorSchedule.date <= parsed_date)
        except ValueError:
            pass
    
    query = query.order_by(InstructorSchedule.date, InstructorSchedule.start_time)
    result = await db.execute(query)
    schedules = result.scalars().all()
    
    results = []
    for schedule in schedules:
        result = await db.execute(select(Course).filter(Course.id == schedule.course_id)) if schedule.course_id else None
        course = result.scalar_one_or_none() if result else None
        result = await db.execute(select(User).filter(User.id == schedule.instructor_id))
        instructor = result.scalar_one_or_none()
        
        results.append(InstructorScheduleResponse(
            id=schedule.id,
            instructor_id=schedule.instructor_id,
            course_id=schedule.course_id,
            date=schedule.date,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            notes=schedule.notes,
            is_active=schedule.is_active,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            course_name=course.name if course else None,
            instructor_name=instructor.full_name if instructor else None
        ))
    
    return InstructorScheduleList(schedules=results, total=len(results))


# ==============================================================================
# PATH PARAMETER ROUTES - Must come AFTER specific paths
# ==============================================================================

@router.get("/{attendance_id}", response_model=AttendanceResponse)
async def get_attendance(
    attendance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific attendance record"""
    result = await db.execute(select(Attendance).filter(Attendance.id == attendance_id))
    attendance = result.scalar_one_or_none()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance not found")
    
    result = await db.execute(select(Student).filter(Student.id == attendance.student_id))
    student = result.scalar_one_or_none()
    result = await db.execute(select(Course).filter(Course.id == attendance.course_id))
    course = result.scalar_one_or_none()
    result = await db.execute(select(User).filter(User.id == attendance.instructor_id)) if attendance.instructor_id else None
    instructor = result.scalar_one_or_none() if result else None
    
    return AttendanceResponse(
        id=attendance.id,
        student_id=attendance.student_id,
        course_id=attendance.course_id,
        instructor_id=attendance.instructor_id,
        date=attendance.date,
        time_slot=attendance.time_slot,
        status=attendance.status,
        notes=attendance.notes,
        student_name=await get_student_name(student, db) if student else None,
        course_name=await get_course_name(course) if course else None,
        instructor_name=instructor.full_name if instructor else None,
        created_at=attendance.created_at,
        updated_at=attendance.updated_at
    )


@router.patch("/{attendance_id}", response_model=AttendanceResponse)
async def update_attendance(
    attendance_id: int,
    attendance_update: AttendanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update an attendance record (approve/reject)"""
    result = await db.execute(select(Attendance).filter(Attendance.id == attendance_id))
    attendance = result.scalar_one_or_none()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance not found")
    
    # Check if instructor can update this attendance (must be for their course)
    if current_user.role == UserRole.INSTRUCTOR:
        result = await db.execute(
            select(InstructorCourse).where(
                and_(
                    InstructorCourse.instructor_id == current_user.id,
                    InstructorCourse.course_id == attendance.course_id,
                    InstructorCourse.is_active == True
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=403, detail="You can only manage attendance for your assigned courses")
    
    if attendance_update.status is not None:
        attendance.status = attendance_update.status
    if attendance_update.notes is not None:
        attendance.notes = attendance_update.notes
    
    if current_user.role in [UserRole.INSTRUCTOR, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        if not attendance.instructor_id:
            attendance.instructor_id = current_user.id
    
    attendance.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(attendance)
    
    result = await db.execute(select(Student).filter(Student.id == attendance.student_id))
    student = result.scalar_one_or_none()
    result = await db.execute(select(Course).filter(Course.id == attendance.course_id))
    course = result.scalar_one_or_none()
    result = await db.execute(select(User).filter(User.id == attendance.instructor_id)) if attendance.instructor_id else None
    instructor = result.scalar_one_or_none() if result else None
    
    return AttendanceResponse(
        id=attendance.id,
        student_id=attendance.student_id,
        course_id=attendance.course_id,
        instructor_id=attendance.instructor_id,
        date=attendance.date,
        time_slot=attendance.time_slot,
        status=attendance.status,
        notes=attendance.notes,
        student_name=await get_student_name(student, db) if student else None,
        course_name=await get_course_name(course) if course else None,
        instructor_name=instructor.full_name if instructor else None,
        created_at=attendance.created_at,
        updated_at=attendance.updated_at
    )


@router.delete("/{attendance_id}")
async def delete_attendance(
    attendance_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete an attendance record"""
    result = await db.execute(select(Attendance).filter(Attendance.id == attendance_id))
    attendance = result.scalar_one_or_none()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance not found")
    
    await db.delete(attendance)
    await db.commit()
    
    return {"message": "Attendance deleted successfully"}


@router.get("/schedules/{schedule_id}", response_model=InstructorScheduleResponse)
async def get_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific instructor schedule"""
    result = await db.execute(select(InstructorSchedule).filter(
        and_(
            InstructorSchedule.id == schedule_id,
            InstructorSchedule.instructor_id == current_user.id
        )
    ))
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    result = await db.execute(select(Course).filter(Course.id == schedule.course_id)) if schedule.course_id else None
    course = result.scalar_one_or_none() if result else None
    result = await db.execute(select(User).filter(User.id == schedule.instructor_id))
    instructor = result.scalar_one_or_none()
    
    return InstructorScheduleResponse(
        id=schedule.id,
        instructor_id=schedule.instructor_id,
        course_id=schedule.course_id,
        date=schedule.date,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        notes=schedule.notes,
        is_active=schedule.is_active,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
        course_name=course.name if course else None,
        instructor_name=instructor.full_name if instructor else None
    )


@router.patch("/schedules/{schedule_id}", response_model=InstructorScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule_update: InstructorScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update an instructor schedule"""
    result = await db.execute(select(InstructorSchedule).filter(
        and_(
            InstructorSchedule.id == schedule_id,
            InstructorSchedule.instructor_id == current_user.id
        )
    ))
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    if schedule_update.course_id is not None:
        schedule.course_id = schedule_update.course_id
    if schedule_update.date is not None:
        schedule.date = schedule_update.date
    if schedule_update.start_time is not None:
        schedule.start_time = schedule_update.start_time
    if schedule_update.end_time is not None:
        schedule.end_time = schedule_update.end_time
    if schedule_update.notes is not None:
        schedule.notes = schedule_update.notes
    if schedule_update.is_active is not None:
        schedule.is_active = schedule_update.is_active
    
    schedule.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(schedule)
    
    result = await db.execute(select(Course).filter(Course.id == schedule.course_id)) if schedule.course_id else None
    course = result.scalar_one_or_none() if result else None
    result = await db.execute(select(User).filter(User.id == schedule.instructor_id))
    instructor = result.scalar_one_or_none()
    
    return InstructorScheduleResponse(
        id=schedule.id,
        instructor_id=schedule.instructor_id,
        course_id=schedule.course_id,
        date=schedule.date,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        notes=schedule.notes,
        is_active=schedule.is_active,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
        course_name=course.name if course else None,
        instructor_name=instructor.full_name if instructor else None
    )


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete an instructor schedule"""
    result = await db.execute(select(InstructorSchedule).filter(
        and_(
            InstructorSchedule.id == schedule_id,
            InstructorSchedule.instructor_id == current_user.id
        )
    ))
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    await db.delete(schedule)
    await db.commit()
    
    return {"message": "Schedule deleted successfully"}
