"""DataWrangler.AI - User Account Database Model.

This module defines the `User` ORM schema for software subscribers, storing credentials
with bcrypt password hashes and tracking billing & subscription metadata.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    """SQLAlchemy ORM Model representing a registered DataWrangler.AI subscriber.

    Table Name:
        `users`
    """

    __tablename__ = "users"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # User Profile & Identity
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=False)

    # Bcrypt Hashed Password (NEVER store plaintext passwords)
    hashed_password = Column(String(255), nullable=False)

    # Stripe Customer & Billing Metadata
    stripe_customer_id = Column(String(100), unique=True, index=True, nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)

    # Account Status ('active', 'canceled', 'past_due', 'unpaid')
    subscription_status = Column(String(50), default="active", nullable=False)

    # System Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # ORM Relationships
    api_keys = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, email='{self.email}', name='{self.full_name}', "
            f"status='{self.subscription_status}')>"
        )
