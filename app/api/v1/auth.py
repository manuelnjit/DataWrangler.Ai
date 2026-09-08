"""DataWrangler.AI - Authentication & Session API Endpoints.

This module implements user registration, credential login, secure logout, and user
session profile checks.

Session Management Architecture:
- Cookies: Authenticated sessions set a `HttpOnly`, `SameSite=Lax` cookie named `session_token`.
- Browser Protection: `HttpOnly` prevents client-side XSS scripts from accessing the session token.
- Dashboard Access: The `/dashboard` software interface requires a valid `session_token` cookie.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.users import User
from app.schemas.auth import UserRegister, UserLogin, UserOut, AuthStatusResponse
from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

COOKIE_NAME = "session_token"


def get_current_user_from_request(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Dependency helper extracting the authenticated user from HttpOnly session cookie or Bearer token.

    Returns:
        User: Authenticated SQLAlchemy User model instance, or None if unauthenticated.
    """
    # 1. Check HttpOnly cookie
    token = request.cookies.get(COOKIE_NAME)

    # 2. Fallback to Authorization Header (Bearer <token>)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    user = db.query(User).filter(User.email == payload["sub"]).first()
    return user


def require_current_user(user: Optional[User] = Depends(get_current_user_from_request)) -> User:
    """Dependency enforcing that an HTTP request originates from a valid logged-in user.

    Raises:
        HTTPException(401): If no valid session cookie/token is present.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in to access the software terminal.",
        )
    return user


@router.post("/register", response_model=AuthStatusResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegister,
    response: Response,
    db: Session = Depends(get_db)
):
    """Registers a new user account, creates the session, and sets the HttpOnly cookie."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please log in.",
        )

    # Create new User model with hashed password
    new_user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        subscription_status="active",  # Free tier default for MVP
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate JWT session token
    token = create_access_token({"sub": new_user.email, "user_id": new_user.id})

    # Set HttpOnly Cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in HTTPS production
        max_age=7 * 24 * 3600,  # 7 days
        path="/",
    )

    return AuthStatusResponse(
        status="success",
        message="Account created successfully!",
        user=UserOut.model_validate(new_user),
    )


@router.post("/login", response_model=AuthStatusResponse)
async def login_user(
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db)
):
    """Authenticates user credentials, creates session token, and sets the HttpOnly cookie."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials and try again.",
        )

    # Generate JWT session token
    token = create_access_token({"sub": user.email, "user_id": user.id})

    # Set HttpOnly Cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in HTTPS production
        max_age=7 * 24 * 3600,  # 7 days
        path="/",
    )

    return AuthStatusResponse(
        status="success",
        message="Logged in successfully!",
        user=UserOut.model_validate(user),
    )


@router.post("/logout")
async def logout_user(response: Response):
    """Logs out the current user by clearing the HttpOnly session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"status": "success", "message": "Logged out successfully."}


@router.get("/me", response_model=UserOut)
async def get_current_user_profile(user: User = Depends(require_current_user)):
    """Returns the profile metadata of the currently authenticated user session."""
    return UserOut.model_validate(user)
