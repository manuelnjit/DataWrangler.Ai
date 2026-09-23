"""EPL Quant API - System Configuration & Environment Settings.

This module encapsulates all application configuration using Pydantic Settings.
It automatically parses and validates environment variables from the host process
or an optional `.env` file, guaranteeing type-safety across environments (local, dev, prod).

Troubleshooting & Diagnostics:
------------------------------
1. Inspecting loaded settings:
   Run `python3 -c "from app.core.config import settings; print(settings.model_dump())"`
2. Environment Variable Overrides:
   To override settings without changing code, pass them directly via environment variables:
   `DATABASE_URL=sqlite:///./custom.db python3 -m uvicorn app.main:app`
3. Troubleshooting Missing Secrets:
   If `STRIPE_SECRET_KEY` is missing in production, Pydantic will raise a `ValidationError`
   at application boot time, preventing broken deployments from starting up.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings Schema and Environment Resolver.

    Attributes:
        PROJECT_NAME: Human-readable name of the service.
        ENVIRONMENT: Operating mode ('development', 'staging', 'production').
        DATABASE_URL: Database connection string (defaults to local SQLite file database).
        STRIPE_SECRET_KEY: Stripe API secret key for payment processing.
        STRIPE_WEBHOOK_SECRET: Secret for validating incoming Stripe Webhook HTTP signatures.
        STRIPE_PRICE_ID: Stripe Price ID corresponding to the $29/mo Quant subscription.
        API_KEY_PREFIX: Security prefix prepended to all issued API keys (e.g. 'epl_live_').
        DEBUG_SQL: If True, SQLAlchemy logs all raw generated SQL statements to stderr.
    """

    PROJECT_NAME: str = "EPL Quant API"
    ENVIRONMENT: str = "development"

    # Default to a local SQLite database file in the project root (`./data/epl_quant.db`).
    # For production (Render/PostgreSQL), replace with: `postgresql://user:pass@host:5432/dbname`
    DATABASE_URL: str = "sqlite:///./data/epl_quant.db"

    # Stripe Payment Integration Credentials (Optional in dev, required for payments)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_ID: Optional[str] = None

    # Security Configuration
    API_KEY_PREFIX: str = "epl_live_"

    # Development & Debugging Controls
    DEBUG_SQL: bool = False

    # Configuration for Pydantic Settings reader
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Instantiate a singleton settings object accessible system-wide via:
# `from app.core.config import settings`
settings = Settings()
