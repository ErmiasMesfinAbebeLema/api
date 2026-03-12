from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from pathlib import Path
import os
import shutil

from api.database import get_db
from api.models import User, AdminPermission, UserRole
from api.schemas import (
    UserCreate, 
    UserResponse, 
    LoginRequest, 
    LoginResponse,
    UserUpdate,
    get_permissions,
    Permission
)
from api.auth import (
    verify_password, 
    get_password_hash, 
    create_access_token,
    get_current_active_user,
    require_role
)


router = APIRouter(prefix="/auth", tags=["Authentication"])

# Upload directory for profile photos
UPLOAD_DIR = Path("uploads/users")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file types for profile photos
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def get_profile_photo_path(user_id: int, filename: str) -> Path:
    """Generate file path for profile photo"""
    user_dir = UPLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{filename}"
    return user_dir / safe_filename


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user - requires either email or phone"""
    # Validate that at least email or phone is provided
    if not user_data.email and not user_data.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or phone number is required"
        )
    
    # Check if email already exists
    if user_data.email:
        stmt = select(User).where(User.email == user_data.email)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Check if phone already exists
    if user_data.phone:
        stmt = select(User).where(User.phone == user_data.phone)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        phone=user_data.phone,
        role=user_data.role,
        profile_photo_url=user_data.profile_photo_url,
        bio=user_data.bio,
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login with email or phone and password"""
    # Determine if identifier is email or phone
    identifier = login_data.identifier.strip()
    
    # Check if identifier looks like email (contains @)
    if '@' in identifier:
        stmt = select(User).where(User.email == identifier)
    else:
        # Treat as phone number - normalize and search
        # Remove any spaces or dashes
        normalized_phone = identifier.replace(' ', '').replace('-', '').replace('+', '')
        stmt = select(User).where(User.phone.contains(normalized_phone))
    
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/phone or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.email or user.phone, "user_id": user.id}
    )
    
    return LoginResponse(
        access_token=access_token,
        user=user
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user info"""
    return current_user


@router.get("/me/permissions", response_model=Permission)
async def get_current_user_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get current user permissions based on role"""
    # For admins, check if there are custom permissions
    admin_permission = None
    if current_user.role == UserRole.ADMIN:
        stmt = select(AdminPermission).where(AdminPermission.admin_id == current_user.id)
        result = await db.execute(stmt)
        admin_permission = result.scalar_one_or_none()
    
    return get_permissions(current_user.role, admin_permission)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update current user profile"""
    # Update fields (only allow certain fields for self-update)
    update_data = user_data.model_dump(exclude_unset=True)
    
    # Don't allow role change through self-update
    update_data.pop('role', None)
    
    # Check email uniqueness if email is being updated
    if 'email' in update_data and update_data['email']:
        stmt = select(User).where(
            User.email == update_data['email'],
            User.id != current_user.id
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another user"
            )
    
    # Check phone uniqueness if phone is being updated
    if 'phone' in update_data and update_data['phone']:
        stmt = select(User).where(
            User.phone == update_data['phone'],
            User.id != current_user.id
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already in use by another user"
            )
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.post("/me/password")
async def change_password(
    password_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Change current user password"""
    old_password = password_data.get('old_password')
    new_password = password_data.get('new_password')
    
    if not old_password or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both old and new password are required"
        )
    
    # Verify old password
    from api.auth import verify_password
    if not verify_password(old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash and set new password
    from api.auth import get_password_hash
    current_user.password_hash = get_password_hash(new_password)
    
    await db.commit()
    
    return {"message": "Password changed successfully"}


@router.post("/me/profile-photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Upload profile photo for current user"""
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: jpeg, png, gif, webp"
        )
    
    # Validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 5MB limit"
        )
    
    # Delete old photo if exists
    if current_user.profile_photo_url:
        old_path = Path(current_user.profile_photo_url.replace("/uploads/users/", "uploads/users/"))
        if old_path.exists():
            try:
                old_path.unlink()
            except:
                pass
    
    # Save new file
    file_path = get_profile_photo_path(current_user.id, file.filename)
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Update user profile
    current_user.profile_photo_url = f"/uploads/users/{current_user.id}/{file_path.name}"
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "message": "Profile photo uploaded successfully",
        "profile_photo_url": current_user.profile_photo_url
    }


@router.delete("/me/profile-photo")
async def delete_profile_photo(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete profile photo for current user"""
    # Delete file if exists
    if current_user.profile_photo_url:
        old_path = Path(current_user.profile_photo_url.replace("/uploads/users/", "uploads/users/"))
        if old_path.exists():
            try:
                old_path.unlink()
            except:
                pass
    
    # Update user profile with URL
    current_user.profile_photo_url = photo_url
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "message": "Profile photo URL set successfully",
        "profile_photo_url": current_user.profile_photo_url
    }


# ─────────────────────────────────────────────────────────
# User Management (Admin only)
# ─────────────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="create_users"))
):
    """Create new user (Admin only)"""
    # Check if email already exists
    if user_data.email:
        stmt = select(User).where(User.email == user_data.email)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Check if phone already exists
    if user_data.phone:
        stmt = select(User).where(User.phone == user_data.phone)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone already registered"
            )
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Create user
    new_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        phone=user_data.phone,
        password_hash=hashed_password,
        role=user_data.role,
        is_active=True
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """List all users (Admin only)"""
    stmt = select(User).offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Get user by ID (Admin only)"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_users"))
):
    """Update user (Admin only)"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    update_data = user_data.model_dump(exclude_unset=True)
    
    # Check email uniqueness if email is being updated
    if 'email' in update_data and update_data['email']:
        stmt = select(User).where(
            User.email == update_data['email'],
            User.id != user_id
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another user"
            )
    
    # Check phone uniqueness if phone is being updated
    if 'phone' in update_data and update_data['phone']:
        stmt = select(User).where(
            User.phone == update_data['phone'],
            User.id != user_id
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already in use by another user"
            )
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="delete_users"))
):
    """Delete user (Admin only)"""
    # Cannot delete yourself
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await db.delete(user)
    await db.commit()
    
    return None


@router.post("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_users"))
):
    """Activate user account (Admin only)"""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"], required_permission="edit_users"))
):
    """Deactivate user account (Admin only)"""
    # Cannot deactivate yourself
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    
    return user
