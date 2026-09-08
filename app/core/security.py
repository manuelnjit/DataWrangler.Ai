"""DataWrangler.AI - Password Hashing & JWT Security Core.

This module provides cryptographic utilities for:
1. Passwords: Salting and hashing passwords using `passlib` / `bcrypt`.
2. Session Tokens: Encoding and decoding signed JSON Web Tokens (JWT) for user sessions.

Security Standards:
- Cryptographic Algorithm: HS256 (HMAC-SHA256) signature verification.
- Passwords: Never stored in raw text; verified via constant-time comparison algorithms.
"""

from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from app.core.config import settings

# Initialize Passlib CryptContext using bcrypt algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = getattr(settings, "JWT_SECRET_KEY", "dw_super_secret_jwt_key_2026_change_in_prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a candidate plaintext password against a stored bcrypt hash.

    Args:
        plain_password: User-entered raw password string.
        hashed_password: Stored bcrypt hash string from database.

    Returns:
        bool: True if match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generates a salted bcrypt hash from a plaintext password.

    Args:
        password: Plaintext user password string.

    Returns:
        str: Salted bcrypt hash digest string.
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a signed JWT session token.

    Args:
        data: Payload claims to embed in token (e.g. `{"sub": email, "user_id": id}`).
        expires_delta: Optional custom expiration timedelta. Defaults to 7 days.

    Returns:
        str: Encoded & signed JWT token string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates a signed JWT session token.

    Args:
        token: Incoming JWT token string.

    Returns:
        dict: Payload claims if valid signature & unexpired, None if invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None
