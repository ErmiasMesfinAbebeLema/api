"""Script to create an admin user"""
import asyncio
from passlib.context import CryptContext
from sqlalchemy import select
from api.database import engine, async_session_maker
from api.models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_admin():
    email = "ermias@mulat.com"
    password = "admin123"
    full_name = "Ermias Admin"
    
    async with async_session_maker() as session:
        # Check if user exists
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"User with email {email} already exists!")
            return
        
        # Create admin user
        hashed_password = pwd_context.hash(password)
        admin_user = User(
            email=email,
            password_hash=hashed_password,
            full_name=full_name,
            role=UserRole.ADMIN,
            is_active=True
        )
        
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)
        
        print(f"Admin user created successfully!")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Role: {admin_user.role.value}")


if __name__ == "__main__":
    asyncio.run(create_admin())
