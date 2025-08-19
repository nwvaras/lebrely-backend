from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr


class UserSignUp(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UserSignIn(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    id: str
    email: str
    email_confirmed_at: Optional[str]
    user_metadata: Optional[Dict[str, Any]]
    app_metadata: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    message: str


class SignUpResponse(BaseModel):
    message: str
    user: Dict[str, Any]
    email_confirmation_required: bool = False
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
