from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import os
import shutil
from pathlib import Path
from datetime import datetime

from api.database import get_db
from api.models import StudentDocument, Student, User, DocumentType
from api.schemas import (
    StudentDocumentCreate,
    StudentDocumentResponse,
    StudentDocumentUpdate,
    StudentDocumentList
)
from api.auth import require_role

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
    
    return document


@router.get("", response_model=StudentDocumentList)
async def list_documents(
    student_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_student_documents"))
):
    # Check if student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
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
    current_user: User = Depends(require_role(["admin"], required_permission="view_student_documents"))
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
    
    return document


@router.get("/{document_id}/download")
async def download_document(
    student_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="view_student_documents"))
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
    
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    student_id: int,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="delete_student_documents"))
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
    
    # Delete file if exists
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    # Delete record
    await db.delete(document)
    await db.commit()
    
    return None
