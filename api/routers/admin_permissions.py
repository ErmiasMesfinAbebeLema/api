from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from api.database import get_db
from api.models import User, AdminPermission, UserRole
from api.schemas import (
    AdminPermissionSchema,
    AdminPermissionUpdate,
    AdminPermissionResponse,
    Permission,
    get_permissions,
    get_detailed_permissions,
)
from api.auth import get_current_active_user

router = APIRouter(prefix="/admin-permissions", tags=["Admin Permissions"])


def require_super_admin():
    """Dependency to require super_admin role"""
    async def checker(user: User = Depends(get_current_active_user)) -> User:
        if user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Super admin privileges required."
            )
        return user
    return checker


@router.get("", response_model=List[AdminPermissionResponse])
async def list_admin_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin()),
    skip: int = 0,
    limit: int = 100,
):
    """List all admin permissions (super_admin only)"""
    # Get all admins (excluding super_admin)
    stmt = select(AdminPermission).offset(skip).limit(limit)
    result = await db.execute(stmt)
    permissions = result.scalars().all()
    return permissions


@router.get("/{admin_id}", response_model=AdminPermissionResponse)
async def get_admin_permission(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin()),
):
    """Get permissions for a specific admin (super_admin only)"""
    # Check if admin exists
    stmt = select(User).where(User.id == admin_id)
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )
    
    if admin.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not an admin"
        )
    
    # Get or create permissions
    stmt = select(AdminPermission).where(AdminPermission.admin_id == admin_id)
    result = await db.execute(stmt)
    permission = result.scalar_one_or_none()
    
    if not permission:
        # Create default permissions if not exist
        permission = AdminPermission(admin_id=admin_id)
        db.add(permission)
        await db.commit()
        await db.refresh(permission)
    
    return permission


@router.post("/{admin_id}", response_model=AdminPermissionResponse)
async def create_admin_permission(
    admin_id: int,
    permission_data: AdminPermissionSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin()),
):
    """Create permissions for an admin (super_admin only)"""
    # Check if admin exists
    stmt = select(User).where(User.id == admin_id)
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )
    
    if admin.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not an admin"
        )
    
    # Check if permissions already exist
    stmt = select(AdminPermission).where(AdminPermission.admin_id == admin_id)
    result = await db.execute(stmt)
    existing_permission = result.scalar_one_or_none()
    
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permissions already exist for this admin. Use PUT to update."
        )
    
    # Create new permissions
    permission = AdminPermission(admin_id=admin_id, **permission_data.model_dump())
    permission.updated_by = current_user.id
    
    db.add(permission)
    await db.commit()
    await db.refresh(permission)
    
    return permission


@router.put("/{admin_id}", response_model=AdminPermissionResponse)
async def update_admin_permission(
    admin_id: int,
    permission_update: AdminPermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin()),
):
    """Update permissions for an admin (super_admin only)"""
    # Check if admin exists
    stmt = select(User).where(User.id == admin_id)
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )
    
    if admin.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not an admin"
        )
    
    # Get existing permissions
    stmt = select(AdminPermission).where(AdminPermission.admin_id == admin_id)
    result = await db.execute(stmt)
    permission = result.scalar_one_or_none()
    
    if not permission:
        # Create new permissions if not exist
        permission = AdminPermission(admin_id=admin_id)
        db.add(permission)
    
    # Update only provided fields
    update_data = permission_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(permission, field, value)
    
    permission.updated_by = current_user.id
    permission.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(permission)
    
    return permission


@router.delete("/{admin_id}")
async def delete_admin_permission(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin()),
):
    """Delete custom permissions for an admin, reverting to defaults (super_admin only)"""
    # Check if admin exists
    stmt = select(User).where(User.id == admin_id)
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )
    
    # Get existing permissions
    stmt = select(AdminPermission).where(AdminPermission.admin_id == admin_id)
    result = await db.execute(stmt)
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No custom permissions found for this admin"
        )
    
    await db.delete(permission)
    await db.commit()
    
    return {"message": "Permissions deleted successfully. Admin will now use default permissions."}


@router.get("/me/detailed", response_model=AdminPermissionSchema)
async def get_my_detailed_permissions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed permissions for current user"""
    # Get custom permissions if any
    stmt = select(AdminPermission).where(AdminPermission.admin_id == current_user.id)
    result = await db.execute(stmt)
    permission = result.scalar_one_or_none()
    
    return get_detailed_permissions(current_user.role, permission)


@router.get("/admins/list", response_model=List[dict])
async def list_admins_with_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin()),
):
    """List all admins with their permissions (super_admin only)"""
    # Get all admins
    stmt = select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
    result = await db.execute(stmt)
    admins = result.scalars().all()
    
    # Get permissions for each admin
    admin_list = []
    for admin in admins:
        stmt = select(AdminPermission).where(AdminPermission.admin_id == admin.id)
        result = await db.execute(stmt)
        permission = result.scalar_one_or_none()
        
        detailed_perms = get_detailed_permissions(admin.role, permission)
        
        admin_list.append({
            "admin_id": admin.id,
            "full_name": admin.full_name,
            "email": admin.email,
            "role": admin.role.value,
            "is_active": admin.is_active,
            "permissions": detailed_perms,
        })
    
    return admin_list
