from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
import os
import shutil
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from api.database import get_db
from api.models import StudentDocument, Student, User, DocumentType, UserRole
from api.schemas import (
    StudentDocumentCreate,
    StudentDocumentResponse,
    StudentDocumentUpdate,
    StudentDocumentList
)
from api.auth import require_role, get_current_active_user
from api.services.notifications import NotificationService

router = APIRouter(prefix="/students/{student_id}/documents", tags=["Student Documents"])

# Upload directory
UPLOAD_DIR = Path("uploads/students")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file types
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def get_file_path(student_id: int, document_type: str, filename: str) -> Path:
    """Generate file path for document"""
    student_dir = UPLOAD_DIR / str(student_id) / document_type
    student_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{filename}"
    return student_dir / safe_filename


@router.post("", response_model=StudentDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    student_id: int,
    document_type: DocumentType,
    description: Optional[str] = None,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="create_student_documents"))
):
    # Check if student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed"
        )
    
    # Validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit"
        )
    
    # Save file
    file_path = get_file_path(student_id, document_type.value, file.filename)
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Create document record
    document = StudentDocument(
        student_id=student_id,
        document_type=document_type,
        file_name=file.filename,
        file_path=str(file_path),
        file_size=len(contents),
        mime_type=file.content_type,
        description=description,
        uploaded_by=current_user.id,
        is_active=True
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # Create notification
    try:
        await NotificationService.notify_document_uploaded(db, document.id, current_user.id)
    except Exception as e:
        logger.error(f"Failed to create document upload notification: {str(e)}")
    
    return document


@router.get("", response_model=StudentDocumentList)
async def list_documents(
    student_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Check if user is admin
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        # Admin can view any student's documents
        pass
    elif current_user.role == UserRole.STUDENT:
        # Students can only view their own documents
        result = await db.execute(select(Student).where(Student.id == student_id))
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
                detail="You can only view your own documents"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get documents
    result = await db.execute(
        select(StudentDocument)
        .where(StudentDocument.student_id == student_id)
        .order_by(StudentDocument.uploaded_at.desc())
        .offset(skip)
        .limit(limit)
    )
    documents = result.scalars().all()
    
    # Get total count
    count_result = await db.execute(
        select(StudentDocument).where(StudentDocument.student_id == student_id)
    )
    total = len(count_result.scalars().all())
    
    return {"documents": documents, "total": total}


@router.get("/{document_id}", response_model=StudentDocumentResponse)
async def get_document(
    student_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Check if user is admin
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        pass
    elif current_user.role == UserRole.STUDENT:
        result = await db.execute(select(Student).where(Student.id == student_id))
        student = result.scalar_one_or_none()
        if not student or student.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own documents"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get document
    result = await db.execute(
        select(StudentDocument).where(
            StudentDocument.id == document_id,
            StudentDocument.student_id == student_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return document


@router.get("/{document_id}/download")
async def download_document(
    student_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Check if user is admin
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        pass
    elif current_user.role == UserRole.STUDENT:
        result = await db.execute(select(Student).where(Student.id == student_id))
        student = result.scalar_one_or_none()
        if not student or student.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only download your own documents"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get document
    result = await db.execute(
        select(StudentDocument).where(
            StudentDocument.id == document_id,
            StudentDocument.student_id == student_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check if file exists
    if not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on server"
        )
    
    return FileResponse(
        path=document.file_path,
        filename=document.file_name,
        media_type=document.mime_type
    )


@router.get("/{document_id}/view")
async def view_document(
    student_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """View document file - returns the file for embedding in img tags"""
    # Check if student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Get document
    result = await db.execute(
        select(StudentDocument).where(
            StudentDocument.id == document_id,
            StudentDocument.student_id == student_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check if file exists
    if not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on server"
        )
    
    return FileResponse(
        path=document.file_path,
        filename=document.file_name,
        media_type=document.mime_type
    )


@router.put("/{document_id}", response_model=StudentDocumentResponse)
async def update_document(
    student_id: int,
    document_id: int,
    document_update: StudentDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_student_documents"))
):
    # Check if student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Get document
    result = await db.execute(
        select(StudentDocument).where(
            StudentDocument.id == document_id,
            StudentDocument.student_id == student_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Update fields
    if document_update.description is not None:
        document.description = document_update.description
    if document_update.is_active is not None:
        document.is_active = document_update.is_active
    
    await db.commit()
    await db.refresh(document)
    
    # Create notification
    try:
        await NotificationService.notify_document_updated(db, document.id, current_user.id)
    except Exception as e:
        logger.error(f"Failed to create document update notification: {str(e)}")
    
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    student_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="delete_student_documents"))
):
    # Check if student exists (with user relationship)
    result = await db.execute(select(Student).options(selectinload(Student.user)).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Get document
    result = await db.execute(
        select(StudentDocument).where(
            StudentDocument.id == document_id,
            StudentDocument.student_id == student_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Delete file if exists
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    # Store info for notification before deleting
    document_type = document.document_type
    student_name = "Unknown"
    if student and student.user:
        student_name = student.user.full_name if student.user.full_name else f"{student.user.first_name} {student.user.last_name}"
    
    # Delete record
    await db.delete(document)
    await db.commit()
    
    # Create notification
    try:
        await NotificationService.notify_document_deleted(db, student_id, document_type, student_name, current_user.id)
    except Exception as e:
        logger.error(f"Failed to create document delete notification: {str(e)}")
    
    return None


# ─────────────────────────────────────────────────────────
# Student Document Upload (for students to upload their own documents)
# ─────────────────────────────────────────────────────────

student_router = APIRouter(prefix="/student/{student_id}/documents", tags=["Student Documents"])


@student_router.get("", response_model=StudentDocumentList)
async def list_student_documents(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List student's own documents"""
    # Verify the student belongs to the current user
    result = await db.execute(
        select(Student).where(Student.id == student_id)
    )
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if this student belongs to the current user
    if student.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own documents"
        )
    
    # Get documents
    stmt = select(StudentDocument).where(
        StudentDocument.student_id == student_id,
        StudentDocument.is_active == True
    ).order_by(StudentDocument.uploaded_at.desc())
    
    result = await db.execute(stmt)
    documents = result.scalars().all()
    
    return {"documents": list(documents), "total": len(documents)}

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def get_student_file_path(student_id: int, document_type: str, filename: str) -> Path:
    """Generate file path for student document"""
    student_dir = UPLOAD_DIR / str(student_id) / document_type
    student_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{filename}"
    return student_dir / safe_filename


@student_router.post("", response_model=StudentDocumentResponse, status_code=status.HTTP_201_CREATED)
async def student_upload_document(
    student_id: int,
    document_type: DocumentType = Query(DocumentType.PROFILE_PHOTO),
    description: Optional[str] = None,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Student uploads their own document - only allows profile_photo for now"""
    # Check if document_type is allowed for students (only profile_photo)
    if document_type != DocumentType.PROFILE_PHOTO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only upload profile photos"
        )
    
    # Verify the student belongs to the current user
    result = await db.execute(
        select(Student).options(selectinload(Student.user)).where(Student.id == student_id)
    )
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Check if this student belongs to the current user
    if student.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only upload documents for yourself"
        )
    
    # For profile_photo, delete any existing photo first
    if document_type == DocumentType.PROFILE_PHOTO:
        # Find existing profile photo
        existing_stmt = select(StudentDocument).where(
            StudentDocument.student_id == student_id,
            StudentDocument.document_type == DocumentType.PROFILE_PHOTO,
            StudentDocument.is_active == True
        )
        existing_result = await db.execute(existing_stmt)
        existing_doc = existing_result.scalar_one_or_none()
        
        if existing_doc:
            # Delete the old file
            if existing_doc.file_path and os.path.exists(existing_doc.file_path):
                try:
                    os.remove(existing_doc.file_path)
                except Exception:
                    pass  # Ignore file deletion errors
            # Mark old document as inactive
            existing_doc.is_active = False
            await db.commit()
    
    # Validate file type (only images for profile photo)
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed. Only JPEG, PNG, GIF, and WebP are allowed."
        )
    
    # Validate file size
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size must be less than {MAX_FILE_SIZE / (1024 * 1024)}MB"
        )
    
    # Save file
    file_path = get_student_file_path(student_id, document_type.value, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Create document record
    document = StudentDocument(
        student_id=student_id,
        document_type=document_type,
        file_name=file.filename,
        file_path=str(file_path),
        file_size=file_size,
        mime_type=file.content_type,
        description=description,
        uploaded_by=current_user.id,
        is_active=True
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    return document


@student_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def student_delete_document(
    student_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Student deletes their own document - only allows profile_photo deletion"""
    # Get the document
    result = await db.execute(
        select(StudentDocument).where(
            StudentDocument.id == document_id,
            StudentDocument.student_id == student_id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check if document is profile_photo
    if document.document_type != DocumentType.PROFILE_PHOTO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can only delete profile photos"
        )
    
    # Verify the student belongs to the current user
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student or student.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own documents"
        )
    
    # Delete file
    if document.file_path:
        file_path = Path(document.file_path)
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Failed to delete file: {e}")
    
    # Delete from database
    await db.delete(document)
    await db.commit()
    
    return None
