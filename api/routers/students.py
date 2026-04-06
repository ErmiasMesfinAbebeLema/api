from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from typing import List
import bcrypt
import logging

logger = logging.getLogger(__name__)

from api.database import get_db
from api.models import User, Student, UserRole
from api.schemas import (
    StudentCreate,
    StudentUpdate,
    StudentUpdateWithUser,
    StudentResponse,
    StudentResponseWithUser,
    StudentWithUserCreate,
    UserResponse
)
from api.auth import get_current_active_user, require_role
from api.services.notifications import NotificationService


router = APIRouter(prefix="/students", tags=["Students"])

# Password hashing
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def student_to_response(student: Student, include_user: bool = False) -> dict:
    """Convert student model to response dict"""
    data = {
        "id": student.id,
        "user_id": student.user_id,
        "date_of_birth": student.date_of_birth,
        "gender": student.gender,
        "emergency_contact_name": student.emergency_contact_name,
        "emergency_contact_phone": student.emergency_contact_phone,
        "emergency_contact_relation": student.emergency_contact_relation,
        "address_line1": student.address_line1,
        "address_line2": student.address_line2,
        "city": student.city,
        "state": student.state,
        "postal_code": student.postal_code,
        "country": student.country,
        "enrollment_status": student.enrollment_status,
        "enrollment_date": student.enrollment_date,
        "graduation_date": student.graduation_date,
        "program_type": student.program_type,
        "referral_source": student.referral_source,
        "notes": student.notes,
        "created_at": student.created_at,
        "updated_at": student.updated_at,
    }
    
    if include_user and student.user:
        data["user"] = UserResponse(
            id=student.user.id,
            email=student.user.email,
            full_name=student.user.full_name,
            phone=student.user.phone,
            profile_photo_url=student.user.profile_photo_url,
            bio=student.user.bio,
            role=student.user.role,
            is_active=student.user.is_active,
            last_login=student.user.last_login,
            created_at=student.user.created_at,
            updated_at=student.user.updated_at
        )
    
    return data


@router.get("", response_model=List[StudentResponseWithUser])
async def get_students(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="view_students"))
):
    """
    Get all students (Admin and Instructor only)
    Returns list of all students with user information
    """
    # Both admin and instructor can view students
    stmt = select(Student).options(selectinload(Student.user)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    students = result.scalars().all()
    
    return [student_to_response(s, include_user=True) for s in students]


@router.get("/{student_id}", response_model=StudentResponseWithUser)
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific student by ID (Admin and Instructor only)
    """
    stmt = select(Student).options(selectinload(Student.user)).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    return student_to_response(student, include_user=True)


@router.post("", response_model=StudentResponseWithUser, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="create_students"))
):
    """
    Create a new student (Admin and Instructor only)
    
    Note: Instructors can only CREATE, cannot UPDATE or DELETE
    """
    # Check if user exists
    stmt = select(User).where(User.id == student_data.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if student profile already exists
    stmt = select(Student).options(selectinload(Student.user)).where(Student.user_id == student_data.user_id)
    result = await db.execute(stmt)
    existing_student = result.scalar_one_or_none()
    
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile already exists for this user"
        )
    
    # Create student
    student = Student(**student_data.model_dump())
    db.add(student)
    await db.commit()
    await db.refresh(student)
    
    return student_to_response(student, include_user=True)


@router.post("/with-user", response_model=StudentResponseWithUser, status_code=status.HTTP_201_CREATED)
async def create_student_with_user(
    student_data: StudentWithUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "instructor"], required_permission="create_students"))
):
    """
    Create a new student with user account in one request (Admin and Instructor only)
    
    This endpoint creates both the User and Student records simultaneously.
    """
    # Check if phone already exists (if provided)
    if student_data.phone:
        stmt = select(User).where(User.phone == student_data.phone)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone number already exists"
            )
    
    # Check if email already exists (if provided)
    if student_data.email:
        stmt = select(User).where(User.email == student_data.email)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists"
            )
    
    # Hash password
    hashed_password = hash_password(student_data.password)
    
    # Create user
    user = User(
        full_name=student_data.full_name,
        phone=student_data.phone,
        email=student_data.email,
        password_hash=hashed_password,
        role=UserRole.STUDENT,
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create student profile
    student = Student(
        user_id=user.id,
        date_of_birth=student_data.date_of_birth,
        gender=student_data.gender,
        emergency_contact_name=student_data.emergency_contact_name,
        emergency_contact_phone=student_data.emergency_contact_phone,
        emergency_contact_relation=student_data.emergency_contact_relation,
        address_line1=student_data.address_line1,
        address_line2=student_data.address_line2,
        city=student_data.city,
        state=student_data.state,
        postal_code=student_data.postal_code,
        country=student_data.country,
        enrollment_status=student_data.enrollment_status,
        enrollment_date=student_data.enrollment_date,
        graduation_date=student_data.graduation_date,
        program_type=student_data.program_type,
        referral_source=student_data.referral_source,
        notes=student_data.notes
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    
    # Create notification for new student created
    try:
        await NotificationService.notify_student_created(
            db=db,
            student_id=student.id,
            created_by=current_user.id
        )
    except Exception as e:
        logger.error(f"Failed to create student notification: {str(e)}")
    
    return student_to_response(student, include_user=True)


@router.put("/{student_id}", response_model=StudentResponseWithUser)
async def update_student(
    student_id: int,
    student_data: StudentUpdateWithUser,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_students"))
):
    """
    Update a student (Admin only)
    
    Note: Instructors CANNOT update students
    """
    # Get student with user relationship
    stmt = select(Student).options(selectinload(Student.user)).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Track which fields were updated for notification
    updated_fields = []
    
    # Update user fields if provided
    if student_data.full_name is not None:
        student.user.full_name = student_data.full_name
        updated_fields.append('full_name')
    if student_data.phone is not None:
        # Check if phone is already taken by another user
        stmt = select(User).where(User.phone == student_data.phone, User.id != student.user_id)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone number already exists"
            )
        student.user.phone = student_data.phone
        updated_fields.append('phone')
    if student_data.email is not None:
        # Check if email is already taken by another user
        stmt = select(User).where(User.email == student_data.email, User.id != student.user_id)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists"
            )
        student.user.email = student_data.email
        updated_fields.append('email')
    
    # Update student fields
    update_data = student_data.model_dump(exclude_unset=True, exclude={'full_name', 'phone', 'email'})
    for field, value in update_data.items():
        setattr(student, field, value)
        updated_fields.append(field)
    
    await db.commit()
    await db.refresh(student)
    await db.refresh(student.user)
    
    # Reload with user relationship
    stmt = select(Student).options(selectinload(Student.user)).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalar_one()
    
    # Create notification for student update
    try:
        await NotificationService.notify_student_updated(
            db=db,
            student_id=student.id,
            updated_fields=updated_fields,
            created_by=current_user.id
        )
    except Exception as e:
        logger.error(f"Failed to create student update notification: {str(e)}")
    
    return student_to_response(student, include_user=True)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="delete_students"))
):
    """
    Delete a student (Admin only)
    
    Note: Instructors CANNOT delete students
    """
    # Load student with user relationship
    stmt = select(Student).options(joinedload(Student.user)).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Store info for notification before deleting
    student_name = student.user.full_name if student and student.user else "Unknown"
    
    await db.delete(student)
    await db.commit()
    
    # Create notification
    try:
        await NotificationService.notify_student_deleted(db, student_id, student_name, current_user.id)
    except Exception as e:
        logger.error(f"Failed to create student delete notification: {str(e)}")
    
    return None


@router.get("/by-user/{user_id}", response_model=StudentResponseWithUser)
async def get_student_by_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get student profile by user ID
    """
    stmt = select(Student).where(Student.user_id == user_id)
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    return student_to_response(student, include_user=True)
