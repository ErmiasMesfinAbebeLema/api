#!/usr/bin/env python3
"""
Create Admin User Script
=======================
Run this script to create an admin user in the database.
Usage: docker exec api python /api/create_admin.py
"""

import asyncio
import sys

# Add the api directory to path for imports
sys.path.insert(0, '/api')

from api.database import get_db
from api.models import User, AdminPermission, UserRole
from api.auth import get_password_hash


async def create_admin():
    """Create admin user"""
    
    # Default admin credentials
    email = "admin@ymacademy.com"
    password = "admin123"
    full_name = "Super Admin"
    
    async for db in get_db():
        try:
            # Check if user already exists
            from sqlalchemy import select
            stmt = select(User).where(User.email == email)
            result = await db.execute(stmt)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"User with email {email} already exists!")
                return
            
            # Create admin user
            admin_user = User(
                email=email,
                full_name=full_name,
                password_hash=get_password_hash(password),
                role=UserRole.ADMIN,
                is_active=True,
                is_email_verified=True
            )
            
            db.add(admin_user)
            await db.flush()  # Get the user ID
            
            # Create admin permissions
            admin_permissions = AdminPermission(
                admin_id=admin_user.id,
                can_manage_users=True,
                can_manage_courses=True,
                can_manage_students=True,
                can_manage_enrollments=True,
                can_manage_payments=True,
                can_manage_certificates=True,
                can_manage_settings=True,
                can_view_reports=True,
                can_send_notifications=True,
                can_manage_instructors=True
            )
            
            db.add(admin_permissions)
            await db.commit()
            
            print(f"Admin user created successfully!")
            print(f"Email: {email}")
            print(f"Password: {password}")
            print(f"Full Name: {full_name}")
            print(f"User ID: {admin_user.id}")
            
        except Exception as e:
            print(f"Error creating admin user: {e}")
            await db.rollback()
            raise
    
    return


if __name__ == "__main__":
    asyncio.run(create_admin())
