"""EPL Quant API - API Key Security Model.

This module defines the `APIKey` SQLAlchemy ORM table schema used to authenticate
incoming HTTP requests securely.

Security Architecture & Hashing Standard:
----------------------------------------
1. Never Store Plaintext Keys:
   Plaintext keys (e.g. `epl_live_8f9b2c3a...`) are generated once upon purchase and shown
   to the user ONCE. Only the SHA-256 hash digest is stored in the database (`hashed_key`).

2. Authentication Lookup Flow:
   - Request arrives with header: `X-API-Key: epl_live_8f9b2c3a...`
   - Server computes `hashlib.sha256(raw_key.encode()).hexdigest()`
   - Server queries: `SELECT * FROM api_keys WHERE hashed_key = :digest AND is_active = True`
   - Constant-time database lookup ensures defense against timing attacks.

3. Key Prefix Storage (`key_prefix`):
   Storing a short prefix (e.g., `epl_live_8f9b`) allows customer support to identify
   a user's key in admin consoles without exposing the full key hash.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class APIKey(Base):
    """SQLAlchemy ORM Model representing an issued API key credential.

    Table Name:
        `api_keys`
    """

    __tablename__ = "api_keys"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign Key Linking Key to Account Owner
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Non-sensitive Display Prefix (e.g., 'epl_live_a1b2')
    key_prefix = Column(String(16), nullable=False)

    # SHA-256 Hashed Secret Key Digest
    hashed_key = Column(String(64), unique=True, index=True, nullable=False)

    # Key Status Flag
    is_active = Column(Boolean, default=True, nullable=False)

    # Key Telemetry Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    # ORM Relationship
    user = relationship("User", back_populates="api_keys")

    def __repr__(self) -> str:
        return (
            f"<APIKey(id={self.id}, user_id={self.user_id}, prefix='{self.key_prefix}', "
            f"active={self.is_active}, last_used={self.last_used_at})>"
        )
