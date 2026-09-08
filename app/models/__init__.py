"""EPL Quant API - Database Models Package.

Exports all SQLAlchemy ORM models so they are registered with `Base.metadata`
upon package import, enabling database schema generation (`Base.metadata.create_all`).
"""

from app.models.matches import Match
from app.models.users import User
from app.models.api_keys import APIKey

__all__ = ["Match", "User", "APIKey"]
