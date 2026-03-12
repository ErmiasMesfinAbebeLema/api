"""Script to create an admin user"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to sys.path for docker container
sys.path.insert(0, str(Path(__file__).parent.parent))

from passlib.context import CryptContext
from sqlalchemy import select, text
from api.database import async_session_maker
from api.models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_admin(role: str = "admin"):
    email = "ermias@mulat.com"
    password = "admin123"
    full_name = "Ermias Admin"
    
    # Map role string to UserRole enum
    role_map = {
        "super_admin": UserRole.SUPER_ADMIN,
        "admin": UserRole.ADMIN,
        "instructor": UserRole.INSTRUCTOR,
        "student": UserRole.STUDENT,
    }
    
    user_role = role_map.get(role.lower(), UserRole.ADMIN)
    
    async with async_session_maker() as session:
        # First, let's verify the enum values in the database
        try:
            result = await session.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole') ORDER BY enumsortorder")
            )
            values = result.fetchall()
            print("Current userrole enum values in database:")
            for v in values:
                print(f"  - {v[0]}")
            
            # Check if super_admin exists
            super_admin_exists = any(v[0] == 'super_admin' for v in values)
            if not super_admin_exists:
                print("\nERROR: super_admin does not exist in database enum!")
                print("Please run add_super_admin.py first to add the enum value.")
                return
        except Exception as e:
            print(f"Error checking enum: {e}")
        
        # Check if user exists
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # Update role if user exists
            existing_user.role = user_role
            await session.commit()
            print(f"\nUser {email} role updated to {user_role.value}!")
            return
        
        # Create admin user
        hashed_password = pwd_context.hash(password)
        admin_user = User(
            email=email,
            password_hash=hashed_password,
            full_name=full_name,
            role=user_role,
            is_active=True
        )
        
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
        
        print(f"\nAdmin user created successfully!")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Role: {admin_user.role.value}")


if __name__ == "__main__":
    # Get role from command line argument
    role = sys.argv[1] if len(sys.argv) > 1 else "admin"
    asyncio.run(create_admin(role))
