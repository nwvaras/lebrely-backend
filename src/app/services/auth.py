from typing import Optional, Dict, Any
from supabase import create_client
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.user import UserService
from app.schemas.user import UserCreate
from app.models.user import User

# Initialize Supabase client

security = HTTPBearer()


class AuthService:
    def __init__(self, db: Optional[AsyncSession] = None):
        self.supabase_client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_KEY
        )
        self.db = db

    async def sign_up(
        self,
        email: str,
        password: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a new user with Supabase and create local User record"""
        if not self.db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session not available",
            )

        try:
            user_create = UserCreate(name=name, email=email)

            local_user = User(
                name=user_create.name, email=user_create.email, is_active=True
            )

            self.db.add(local_user)
            await self.db.flush()
            await self.db.refresh(local_user)

            supabase_metadata = metadata or {}
            supabase_metadata.update({"name": name, "local_user_id": local_user.id})

            # Create user in Supabase with local ID as metadata
            response = self.supabase_client.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"data": supabase_metadata},
                }
            )
            print(response)
            if not response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create user in Supabase",
                )

            # Update local user with Supabase ID
            local_user.supabase_user_id = response.user.id
            await self.db.commit()
            await self.db.refresh(local_user)

            return {
                "user": local_user,
                "session": response.session,
                "supabase_user": response.user,
                "message": "User created successfully",
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration failed: {str(e)}",
            )

    async def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in user with email and password"""
        if not self.db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session not available",
            )

        try:
            response = self.supabase_client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )

            if not (response.user and response.session):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                )

            # Get local user record
            user_service = UserService(self.db)
            local_user = await user_service.get_user_by_supabase_id(response.user.id)

            # If not found, try to get by local_user_id from metadata
            if not local_user and response.user.user_metadata:
                local_user_id = response.user.user_metadata.get("local_user_id")
                if local_user_id:
                    local_user = await user_service.get_user_by_id(local_user_id)
                    if local_user:
                        local_user.supabase_user_id = response.user.id
                        await self.db.commit()

            if not local_user:
                # If local user doesn't exist, try to find by email and link
                local_user = await user_service.get_user_by_email(email)
                if local_user:
                    # Link existing user to Supabase ID
                    local_user = await user_service.link_supabase_user(
                        email, response.user.id
                    )
                else:
                    # Create local user if it doesn't exist
                    user_create = UserCreate(
                        name=response.user.user_metadata.get("name", "Unknown"),
                        email=email,
                    )
                    local_user = await user_service.create_user(
                        user_create, response.user.id
                    )

            return {
                "user": local_user,
                "session": response.session,
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "token_type": "bearer",
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Login failed: {str(e)}",
            )

    async def sign_out(self, access_token: str) -> Dict[str, str]:
        """Sign out user"""
        try:
            self.supabase_client.auth.set_session(access_token, "")
            self.supabase_client.auth.sign_out()
            return {"message": "Successfully signed out"}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sign out failed: {str(e)}",
            )

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token"""
        try:
            response = self.supabase_client.auth.refresh_session(refresh_token)
            if response.session:
                return {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "token_type": "bearer",
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token refresh failed: {str(e)}",
            )

    async def get_current_user(self, access_token: str) -> User:
        """Get current local user from access token"""
        if not self.db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session not available",
            )

        try:
            # Set the session with the access token
            self.supabase_client.auth.set_session(access_token, "")

            # Get user from Supabase
            supabase_response = self.supabase_client.auth.get_user(access_token)

            if not supabase_response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
                )

            # Get local user record
            user_service = UserService(self.db)
            local_user = None

            # First try to get user by Supabase ID
            local_user = await user_service.get_user_by_supabase_id(
                supabase_response.user.id
            )

            # If not found, try to get by local_user_id from metadata
            if not local_user and supabase_response.user.user_metadata:
                local_user_id = supabase_response.user.user_metadata.get(
                    "local_user_id"
                )
                if local_user_id:
                    local_user = await user_service.get_user_by_id(int(local_user_id))
                    if local_user:
                        # Update with Supabase ID if found
                        local_user.supabase_user_id = supabase_response.user.id
                        await self.db.commit()

            if not local_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found in local database",
                )

            return local_user

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}",
            )

    async def reset_password(self, email: str) -> Dict[str, str]:
        """Send password reset email"""
        try:
            self.supabase_client.auth.reset_password_email(email)
            return {"message": "Password reset email sent"}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password reset failed: {str(e)}",
            )


# AuthService is now instantiated per request with database session
