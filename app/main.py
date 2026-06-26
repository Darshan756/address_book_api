"""
Application Entry Point
────────────────────────
Creates the FastAPI app, registers all routers,
attaches middleware, and configures lifespan events.

Run locally:
    uv run uvicorn app.main:app --reload

Run in production:
    gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 4
"""

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.v1.routes import addresses, entity_types


# ─────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            # format: 2024-01-01 12:00:00 | INFO | app.main | message
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "handlers": ["console"],
        # DEBUG when settings.DEBUG=True, INFO otherwise
        "level": "DEBUG" if settings.DEBUG else "INFO",
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# LIFESPAN
# ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before yield  → runs on startup.
    Code after yield   → runs on shutdown.

    We keep this clean — no DB setup here.
    Tables and seed data are handled by Alembic migrations.
    Just run: uv run alembic upgrade head
    """
    logger.info(f"Starting {settings.APP_NAME}")
    logger.info(f"Debug mode  : {settings.DEBUG}")
    logger.info(f"Distance unit: {settings.DEFAULT_DISTANCE_UNIT}")
    logger.info("Visit http://localhost:8000/docs for Swagger UI")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


# ─────────────────────────────────────────
# APP INSTANCE
# ─────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "## Address Book API\n\n"
        "Create, update, delete and search addresses.\n\n"
        "### Key features\n"
        "- Full CRUD for addresses\n"
        "- Distance-based search using the **Haversine formula**\n"
        "- Fuzzy entity type matching — type `resto` to find restaurants\n"
        "- Partial name search — type `john` to find all Johns\n"
        "- Combine any filters freely with pagination\n\n"
        "### Distance unit\n"
        "Configured via `DEFAULT_DISTANCE_UNIT` in `.env` (`km`)"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    # allows any frontend origin to call this API
    # in production restrict to your actual frontend domain:
    # allow_origins=["https://myapp.com"]
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────
# GLOBAL EXCEPTION HANDLER
# ─────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches any unhandled exception and returns a
    clean JSON error instead of a raw Python traceback.

    FastAPI handles HTTPException automatically —
    this catches everything else (bugs, unexpected errors).
    """
    logger.error(
        f"Unhandled exception on {request.method} {request.url} "
        f"— {type(exc).__name__}: {exc}",
        exc_info=True,      # prints full traceback in the console
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Please try again later."
        },
    )


# ─────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────

# versioned prefix keeps the API future-proof
# if you add v2 later, existing clients still use v1
API_V1_PREFIX = "/api/v1"

app.include_router(addresses.router, prefix=API_V1_PREFIX)
app.include_router(entity_types.router, prefix=API_V1_PREFIX)


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────

@app.get(
    "/",
    tags=["Health"],
    summary="Health check",
    description="Confirms the API is running. Used by monitoring tools.",
)
async def health_check():
    """Returns app status and version."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
    }