from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.config import settings
from api.database import get_db
from api.models import User


# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.secret_key, 
        algorithm=settings.algorithm
    )
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.secret_key, 
            algorithms=[settings.algorithm]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


def require_role(allowed_roles: list[str], required_permission: str = None, require_create: bool = False, require_update: bool = False, require_delete: bool = False, require_view: bool = False):
    """Dependency to check user role and optionally permissions"""
    async def role_checker(
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        # Convert user role to lowercase for comparison
        user_role = user.role.value.lower()
        allowed_roles_lower = [role.lower() for role in allowed_roles]
        
        # Super admin has access to everything
        if user_role == 'super_admin':
            return user
        
        if user_role not in allowed_roles_lower:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        
        # If no specific permission required, allow access
        if not required_permission:
            return user
        
        # Check permissions from admin_permissions table
        # Map permission names to database column names
        permission_map = {
            'manage_users': 'can_manage_users',
            'create_users': 'can_create_users',
            'edit_users': 'can_edit_users',
            'delete_users': 'can_delete_users',
            'manage_students': 'can_manage_students',
            'view_students': 'can_view_students',
            'create_students': 'can_create_students',
            'edit_students': 'can_edit_students',
            'delete_students': 'can_delete_students',
            'manage_courses': 'can_manage_courses',
            'create_courses': 'can_create_courses',
            'edit_courses': 'can_edit_courses',
            'delete_courses': 'can_delete_courses',
            'manage_certificates': 'can_manage_certificates',
            'create_certificates': 'can_create_certificates',
            'edit_certificates': 'can_edit_certificates',
            'delete_certificates': 'can_delete_certificates',
            'revoke_certificates': 'can_revoke_certificates',
            'manage_enrollments': 'can_manage_enrollments',
            'create_enrollments': 'can_create_enrollments',
            'edit_enrollments': 'can_edit_enrollments',
            'delete_enrollments': 'can_delete_enrollments',
            'manage_payments': 'can_manage_payments',
            'view_payments': 'can_view_payments',
            'create_payments': 'can_create_payments',
            'manage_invoices': 'can_manage_invoices',
            'create_invoices': 'can_create_invoices',
            'edit_invoices': 'can_edit_invoices',
            'delete_invoices': 'can_delete_invoices',
            'manage_documents': 'can_manage_documents',
            'view_documents': 'can_view_documents',
            'upload_documents': 'can_upload_documents',
            'delete_documents': 'can_delete_documents',
            'view_reports': 'can_view_reports',
            'export_reports': 'can_export_reports',
            'manage_instructors': 'can_manage_instructors',
            'manage_settings': 'can_manage_settings',
        }
        
        # Get the database column name for the permission
        db_column = permission_map.get(required_permission)
        if not db_column:
            # Unknown permission, allow access (fail open for backwards compatibility)
            return user
        
        # Query the admin_permissions table
        from api.models import AdminPermission
        stmt = select(AdminPermission).where(AdminPermission.admin_id == user.id)
        result = await db.execute(stmt)
        admin_perm = result.scalar_one_or_none()
        
        if not admin_perm:
            # No permissions set yet - fail open (allow for backward compatibility)
            # The super_admin should configure permissions for this admin
            return user
        
        # Check the appropriate permission
        has_permission = getattr(admin_perm, db_column, False)
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. You don't have permission to {required_permission}."
            )
        
        return user
    return role_checker
