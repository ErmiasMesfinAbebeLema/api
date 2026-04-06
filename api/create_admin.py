#!/usr/bin/env python3
"""
Create Admin User Script
=======================
Run this script to create an admin user in the database.
Usage: docker exec api python /api/api/create_admin.py
"""

import asyncio
import sys

# Set path to include api directory
sys.path.insert(0, '/')

from database import get_db
from models import User, UserRole
from auth import get_password_hash


async def create_admin():
    """Create admin user"""
    
    # Default admin credentials
    email = "admin@ymacademy.com"
    password = "@337034"
    full_name = "Super Admin"
    
    async for db in get_db():
        try:
            # Check if user already exists
            from sqlalchemy import select
            stmt = select(User).where(User.email == email)
            result = await db.execute(stmt)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                # Update role to SUPER_ADMIN if user exists
                existing_user.role = UserRole.SUPER_ADMIN
                existing_user.is_active = True
                existing_user.is_email_verified = True
                await db.commit()
                print(f"User {email} updated to SUPER_ADMIN role!")
                return
            
            # Create super admin user
            admin_user = User(
                email=email,
                full_name=full_name,
                password_hash=get_password_hash(password),
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                is_email_verified=True
            )
            
            db.add(admin_user)
            await db.commit()
            
            print(f"Super Admin user created successfully!")
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
