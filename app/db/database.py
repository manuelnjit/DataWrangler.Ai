"""EPL Quant API - Database Engine, Session Management & ORM Base.

This module initializes the SQLAlchemy database engine, sets up thread-safe session
factories (`SessionLocal`), defines the declarative base for all database models (`Base`),
and provides a FastAPI dependency function (`get_db`) to manage connection lifecycles per request.

Troubleshooting & Diagnostics:
------------------------------
1. Inspecting SQL Statements in Console:
   Set `DEBUG_SQL = True` in `.env` or set `echo=True` on `create_engine`. This will echo every
   `SELECT`, `INSERT`, `UPDATE`, and `DELETE` query to stdout/stderr with exact parameter values.

2. SQLite Locking & Threading (`check_same_thread`):
   SQLite defaults to restricting connection use to the thread that opened it.
   Since FastAPI handles incoming HTTP requests across a thread pool, `connect_args={"check_same_thread": False}`
   is required for SQLite to prevent `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.

3. Connection Leaks & Session Cleanups:
   `get_db()` uses Python's `yield` pattern within a `try...finally` block. This guarantees that
   `db.close()` is executed at the end of every HTTP request, preventing connection pool starvation.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

# ------------------------------------------------------------------------------
# Engine Construction
# ------------------------------------------------------------------------------
# Configure engine options conditionally based on dialect (SQLite vs PostgreSQL)
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite-specific flag: Allows multi-threaded async request handlers to share connections safely
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 15.0

# Create the primary database engine.
# `echo=settings.DEBUG_SQL`: Enables real-time SQL execution logging when DEBUG_SQL=True.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG_SQL,
)

# ------------------------------------------------------------------------------
# Session Factory & Declarative Base
# ------------------------------------------------------------------------------
# `SessionLocal` is a configurable factory class that creates database sessions.
# `autocommit=False`: Operations require explicit `db.commit()` calls for atomic transactions.
# `autoflush=False`: Prevents automatic SQL flushes before queries until explicitly triggered.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# `Base`: Declarative class from which all ORM models (Matches, Users, APIKeys) inherit.
Base = declarative_base()


# ------------------------------------------------------------------------------
# FastAPI Dependency Injection Function
# ------------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """Provides a transactional database session scope for FastAPI endpoints.

    Yields:
        Session: Active SQLAlchemy database session.

    Lifecycle:
        1. Instantiates a new `SessionLocal()` at the start of an HTTP request.
        2. Passes (`yield`s) the session instance to the route dependency stack.
        3. Executes the `finally:` block after the endpoint responds, calling `db.close()`
           to return the connection to the engine pool.

    How to Troubleshoot database issues using `get_db`:
        If an endpoint crashes mid-transaction, SQLAlchemy uncommitted changes are rolled
        back automatically when the session closes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
