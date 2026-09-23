"""DataWrangler.AI - Main FastAPI Server & Router Configuration.

Sets up application lifecycle hooks, mounts static directory assets, includes authentication
and API routers, and defines top-level HTML route handlers (`/` landing page, `/dashboard` terminal).
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.database import engine, Base
from app.api.v1 import auth, terminal
import app.models  # noqa: F401


# ------------------------------------------------------------------------------
# Application Lifespan Context Manager
# ------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Executes boot-time tasks (database table auto-creation) on server startup."""
    Base.metadata.create_all(bind=engine)
    yield


# ------------------------------------------------------------------------------
# Application Instance
# ------------------------------------------------------------------------------
app = FastAPI(
    title="DataWrangler.AI",
    description="Bloomberg Terminal for Sports Betting & Premier League HT/FT Scenario Modeling",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ------------------------------------------------------------------------------
# Mount API Routers
# ------------------------------------------------------------------------------
app.include_router(auth.router, prefix="/api/v1")
app.include_router(terminal.router, prefix="/api/v1")

# ------------------------------------------------------------------------------
# Mount Static File Assets
# ------------------------------------------------------------------------------
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ------------------------------------------------------------------------------
# Page Route Handlers
# ------------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def serve_landing_page():
    """Serves the public DataWrangler.AI landing page with interactive demo & auth modal."""
    index_path = os.path.join(static_dir, "index.html")
    return FileResponse(index_path)


@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard_page():
    """Serves the protected DataWrangler.AI software terminal workspace."""
    dashboard_path = os.path.join(static_dir, "dashboard.html")
    return FileResponse(dashboard_path)


# ------------------------------------------------------------------------------
# System Telemetry & Health Probe
# ------------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
async def health_check():
    """System uptime and health check endpoint."""
    return {
        "status": "healthy",
        "service": "DataWrangler.AI",
        "environment": settings.ENVIRONMENT,
        "database": settings.DATABASE_URL.split("://")[0],
    }
