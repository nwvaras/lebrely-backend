from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, user_create: UserCreate, supabase_user_id: str) -> User:
        """Create a new user linked to Supabase user"""
        # Check if user with this email already exists
        existing_user = await self.get_user_by_email(user_create.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        # Check if user with this Supabase ID already exists
        existing_supabase_user = await self.get_user_by_supabase_id(supabase_user_id)
        if existing_supabase_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this Supabase ID already exists",
            )

        db_user = User(
            supabase_user_id=supabase_user_id,
            name=user_create.name,
            email=user_create.email,
            is_active=True,
        )

        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by internal ID"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_supabase_id(self, supabase_user_id: str) -> Optional[User]:
        """Get user by Supabase user ID"""
        result = await self.db.execute(
            select(User).where(User.supabase_user_id == supabase_user_id)
        )
        return result.scalar_one_or_none()

    async def update_user(
        self, user_id: int, user_update: UserUpdate
    ) -> Optional[User]:
        """Update user information"""
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            return None

        update_data = user_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)

        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def delete_user(self, user_id: int) -> bool:
        """Delete user (soft delete by setting is_active to False)"""
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            return False

        db_user.is_active = False
        await self.db.commit()
        return True

    async def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get list of users with pagination"""
        result = await self.db.execute(
            select(User).where(User.is_active is True).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def link_supabase_user(
        self, email: str, supabase_user_id: str
    ) -> Optional[User]:
        """Link existing user to Supabase user ID"""
        db_user = await self.get_user_by_email(email)
        if not db_user:
            return None

        db_user.supabase_user_id = supabase_user_id
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user
