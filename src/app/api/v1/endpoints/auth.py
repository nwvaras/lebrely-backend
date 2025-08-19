from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import (
    UserSignUp,
    UserSignIn,
    TokenResponse,
    RefreshTokenRequest,
    PasswordResetRequest,
    MessageResponse,
    SignUpResponse,
)
from app.schemas.user import UserResponse
from app.services.auth import AuthService
from app.core.auth import get_current_user, get_current_active_user, security
from app.models.user import User
from app.db.database import get_db

router = APIRouter()


@router.post(
    "/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED
)
async def sign_up(user_data: UserSignUp, db: AsyncSession = Depends(get_db)):
    """
    Register a new user with Supabase Auth and create local User record
    """
    auth_service = AuthService(db)

    result = await auth_service.sign_up(
        email=user_data.email,
        password=user_data.password,
        name=user_data.name,
        metadata=user_data.metadata,
    )
    user_data = {
        "id": result["user"].id,
        "email": result["user"].email,
        "name": result["user"].name,
        "is_active": result["user"].is_active,
        "created_at": result["user"].created_at.isoformat(),
        "updated_at": result["user"].updated_at.isoformat(),
    }

    # Check if session exists (email confirmed) or if confirmation is required
    if result["session"]:
        return SignUpResponse(
            message="User created and signed in successfully",
            user=user_data,
            email_confirmation_required=False,
            access_token=result["session"]["access_token"],
            refresh_token=result["session"]["refresh_token"],
        )
    else:
        return SignUpResponse(
            message="User created successfully. Please check your email to confirm your account.",
            user=user_data,
            email_confirmation_required=True,
        )


@router.post("/signin", response_model=TokenResponse)
async def sign_in(credentials: UserSignIn, db: AsyncSession = Depends(get_db)):
    """
    Sign in with email and password
    """
    auth_service = AuthService(db)

    result = await auth_service.sign_in(
        email=credentials.email, password=credentials.password
    )

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user={
            "id": result["user"].id,
            "email": result["user"].email,
            "name": result["user"].name,
            "is_active": result["user"].is_active,
            "created_at": result["user"].created_at.isoformat(),
            "updated_at": result["user"].updated_at.isoformat(),
        },
    )


@router.post("/signout", response_model=MessageResponse)
async def sign_out(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """
    Sign out current user
    """
    auth_service = AuthService(db)
    result = await auth_service.sign_out(credentials.credentials)
    return MessageResponse(message=result["message"])


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    """
    auth_service = AuthService(db)
    result = await auth_service.refresh_token(token_data.refresh_token)

    # Get user info with new token
    user = await auth_service.get_current_user(result["access_token"])

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        },
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    reset_data: PasswordResetRequest, db: AsyncSession = Depends(get_db)
):
    """
    Send password reset email
    """
    auth_service = AuthService(db)
    result = await auth_service.reset_password(reset_data.email)
    return MessageResponse(message=result["message"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    """
    return UserResponse.model_validate(current_user)


@router.get("/me/profile", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get current user profile (requires active account)
    """
    return UserResponse.model_validate(current_user)
