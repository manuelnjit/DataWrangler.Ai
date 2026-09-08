"""DataWrangler.AI - Authentication Pydantic Schemas.

Defines request body validation contracts for user registration, user login,
and structured user profile response payloads.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class UserRegister(BaseModel):
    """Payload schema for registering a new account."""
    full_name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Payload schema for user login credentials."""
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Safe user profile response model (excludes sensitive password hashes)."""
    id: int
    full_name: Optional[str] = None
    email: EmailStr
    subscription_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthStatusResponse(BaseModel):
    """Standardized response returned upon successful authentication."""
    status: str
    message: str
    user: UserOut
