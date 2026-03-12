"""Script to add SUPER_ADMIN to userrole enum"""
import asyncio
from pathlib import Path
import sys

# Add parent directory to sys.path for docker container
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from api.database import async_session_maker


async def add_super_admin():
    async with async_session_maker() as session:
        try:
            # First check if the value already exists (uppercase)
            result = await session.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole') AND enumlabel = 'SUPER_ADMIN'")
            )
            existing = result.fetchone()
            
            if not existing:
                # Add the uppercase value
                await session.execute(text("ALTER TYPE userrole ADD VALUE 'SUPER_ADMIN'"))
                await session.commit()
                print("SUPER_ADMIN added to userrole enum!")
            else:
                print("SUPER_ADMIN already exists in userrole enum!")
                
            # Verify the enum values
            result = await session.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole') ORDER BY enumsortorder")
            )
            values = result.fetchall()
            print("Current userrole enum values:")
            for v in values:
                print(f"  - {v[0]}")
                
        except Exception as e:
            print(f"Error: {e}")
            # Try to show current enum values
            try:
                result = await session.execute(
                    text("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole') ORDER BY enumsortorder")
                )
                values = result.fetchall()
                print("Current userrole enum values:")
                for v in values:
                    print(f"  - {v[0]}")
            except:
                pass


if __name__ == "__main__":
    asyncio.run(add_super_admin())
